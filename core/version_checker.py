"""
版本检测模块 — 通过 GitHub Releases 页面检查最新版本

功能:
- 直接抓取 GitHub Releases 页面，解析版本号（无需 API）
- 无 Token、无频率限制，稳定性高
- 语义化版本比较（支持 v 前缀）
- 5 秒超时，网络异常不影响主流程
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple
import html

import httpx
import logging

from config import (
    APP_VERSION,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# SSL 证书验证配置
# Windows 上 Python SSL 证书验证经常失败，禁用验证以提高兼容性
# 仅针对 GitHub 请求禁用 SSL 验证（GitHub 使用有效证书，风险较低）
_SSL_VERIFY = False
logger.info("SSL verification disabled for Windows compatibility")

# GitHub API 请求超时（秒）
_REQUEST_TIMEOUT: float = 5.0


@dataclass
class ReleaseInfo:
    """发布版本信息"""
    version: str           # 版本号，如 "1.2.0"
    tag_name: str          # Git 标签名，如 "v1.2.0"
    title: str             # 发布标题
    body: str              # 更新日志（纯文本，保留换行）
    html_url: str          # 发布页 URL
    published_at: str      # 发布日期
    is_newer: bool         # 是否比当前版本新


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """
    解析语义化版本字符串，支持 "v" 前缀

    例: "v1.2.3" → (1, 2, 3)
         "1.2.3"  → (1, 2, 3)
         "v2"     → (2, 0, 0)
    """
    v = version.lstrip("v").strip()
    parts = re.split(r"[.\-]", v)[:3]
    nums: list[int] = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def _is_newer(latest: str, current: str) -> bool:
    """判断 latest 版本是否高于 current"""
    try:
        lv = _parse_semver(latest)
        cv = _parse_semver(current)
        return lv > cv
    except Exception:
        return False


def _extract_release_body(html_content: str) -> str:
    """
    从 GitHub Releases 页面 HTML 中提取 release body（更新说明）

    使用 HTMLParser 来正确解析 markdown-body div 的内容。
    保留原始的换行格式。
    如果提取失败，返回空字符串。
    """
    try:
        from html.parser import HTMLParser

        # 定义块级元素（这些元素通常会在渲染时引入换行）
        BLOCK_ELEMENTS = {
            'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'li', 'ul', 'ol', 'blockquote', 'pre', 'hr'
        }

        class MarkdownBodyExtractor(HTMLParser):
            """提取 markdown-body div 中的文本内容，保留换行格式"""

            def __init__(self):
                super().__init__()
                self.in_markdown_body = False
                self.div_depth = 0
                self.capture_text = False
                self.text_parts = []
                self.reached_end = False

            def handle_starttag(self, tag, attrs):
                if self.reached_end:
                    return

                if tag == 'div':
                    attrs_dict = dict(attrs)
                    class_attr = attrs_dict.get('class', '')

                    if 'markdown-body' in class_attr and not self.in_markdown_body:
                        # 找到 markdown-body div
                        self.in_markdown_body = True
                        self.div_depth = 1
                        self.capture_text = True
                    elif self.in_markdown_body:
                        # 在 markdown-body 内部，遇到嵌套的 div
                        self.div_depth += 1

                # 处理换行标签
                if self.capture_text and not self.reached_end:
                    if tag == 'br':
                        # <br> 标签 → 换行
                        self.text_parts.append('\n')
                    elif tag in BLOCK_ELEMENTS:
                        # 块级元素开始 → 添加换行（如果前面有内容）
                        if self.text_parts and not (isinstance(self.text_parts[-1], str) and self.text_parts[-1].endswith('\n')):
                            self.text_parts.append('\n')

            def handle_endtag(self, tag):
                if self.reached_end:
                    return

                if tag == 'div' and self.in_markdown_body:
                    self.div_depth -= 1
                    if self.div_depth == 0:
                        # 找到了 markdown-body 的结束标签
                        self.in_markdown_body = False
                        self.capture_text = False
                        self.reached_end = True
                elif self.capture_text and not self.reached_end:
                    # 块级元素结束 → 添加换行
                    if tag in BLOCK_ELEMENTS:
                        if self.text_parts and not (isinstance(self.text_parts[-1], str) and self.text_parts[-1].endswith('\n')):
                            self.text_parts.append('\n')

            def handle_data(self, data):
                if self.capture_text and not self.reached_end:
                    # 保留文本中的换行符
                    text = data
                    if text:
                        # 如果文本中有换行，需要正确处理
                        lines = text.splitlines(keepends=False)
                        for i, line in enumerate(lines):
                            line = line.strip()
                            if line:
                                self.text_parts.append(line)
                            if i < len(lines) - 1:
                                self.text_parts.append('\n')

        parser = MarkdownBodyExtractor()
        parser.feed(html_content)

        if parser.text_parts:
            # 拼接文本，保留换行格式
            text = ''
            for part in parser.text_parts:
                if part == '\n':
                    # 换行符
                    if not text.endswith('\n'):
                        text += '\n'
                else:
                    # 普通文本
                    if text.endswith('\n'):
                        text += part
                    elif text and not text[-1].isspace():
                        text += ' ' + part
                    else:
                        text += part

            # 清理多余的空行（最多保留一个空行）
            text = re.sub(r'\n{3,}', '\n\n', text)

            text = text.strip()
            logger.info("成功提取更新说明，长度: %d 字符", len(text))
            return text

        logger.warning("未找到 markdown-body 内容或内容为空")
        return ""

    except Exception as e:
        logger.warning("提取更新说明时出错: %s", e)
        return ""


def _fetch_latest_release() -> Tuple[dict | None, str | None]:
    """
    直接抓取 GitHub Releases 页面，从 URL 中解析最新版本号。
    不依赖 GitHub API，无需 Token，无频率限制。
    """
    try:
        with httpx.Client(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            verify=_SSL_VERIFY,  # 已禁用 SSL 验证（Windows 兼容性）
        ) as client:
            response = client.get(
                GITHUB_RELEASES_URL + "/latest",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            response.raise_for_status()
            html_content = response.text

        # 从页面中提取最新 release 的 tag URL
        pattern = rf"/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/tag/(v?[\d\.]+)"
        match = re.search(pattern, html_content)

        if not match:
            # 备选：直接从 URL 路径中提取 tag
            final_url = str(response.url)
            match = re.search(r"/releases/tag/(v?[\d\.]+)", final_url)

        if not match:
            logger.warning("无法从页面中解析出最新版本 tag")
            return None, None

        tag_name = match.group(1)
        version = tag_name.lstrip("v")

        logger.info("从 GitHub 页面解析到最新版本: %s", tag_name)

        # 提取更新说明
        body = _extract_release_body(html_content)

        return {
            "tag_name": tag_name,
            "version": version,
            "name": tag_name,
            "body": body,
            "html_url": GITHUB_RELEASES_URL + "/tag/" + tag_name,
            "published_at": "",
        }, None

    except httpx.TimeoutException:
        return None, "连接 GitHub 超时，请检查网络后重试"
    except httpx.HTTPError as e:
        logger.warning("GitHub 页面请求失败: %s", e)
        return None, "无法连接到更新服务器，请检查网络连接后重试"
    except Exception as e:
        logger.warning("版本检测异常: %s", e)
        return None, "无法访问更新服务器，暂时无法提供服务"


def check_for_updates() -> Tuple[Optional[ReleaseInfo], Optional[str]]:
    """
    检查 GitHub 是否有新版本发布

    每次调用都会请求 GitHub 页面获取最新版本。

    Returns:
        ``(ReleaseInfo, None)`` — 发现新版本
        ``(None, None)``       — 当前已是最新
        ``(None, error_message)`` — 网络/服务器错误
    """
    logger.info("检查版本更新 (当前: v%s)...", APP_VERSION)

    data, error = _fetch_latest_release()
    if error:
        return None, error
    if not data:
        return None, None

    tag_name = data.get("tag_name", "")
    latest_version = tag_name.lstrip("v")

    if not latest_version:
        logger.warning("GitHub release 中未找到版本号")
        return None, None

    logger.info("GitHub 最新版本: v%s", latest_version)

    if not _is_newer(latest_version, APP_VERSION):
        logger.info("当前已是最新版本")
        return None, None

    logger.info("发现新版本: v%s (当前: v%s)", latest_version, APP_VERSION)

    return ReleaseInfo(
        version=latest_version,
        tag_name=tag_name,
        title=data.get("name", tag_name),
        body=data.get("body", ""),
        html_url=data.get("html_url", GITHUB_RELEASES_URL),
        published_at=data.get("published_at", ""),
        is_newer=True,
    ), None
