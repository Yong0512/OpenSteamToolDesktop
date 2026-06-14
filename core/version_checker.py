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

import httpx
import logging

from config import (
    APP_VERSION,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)

logger = logging.getLogger(__name__)

# GitHub API 请求超时（秒）
_REQUEST_TIMEOUT: float = 5.0


@dataclass
class ReleaseInfo:
    """发布版本信息"""
    version: str           # 版本号，如 "1.2.0"
    tag_name: str          # Git 标签名，如 "v1.2.0"
    title: str             # 发布标题
    body: str              # 更新日志（Markdown）
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


def _fetch_latest_release() -> Tuple[dict | None, str | None]:
    """
    直接抓取 GitHub Releases 页面，从 URL 中解析最新版本号。
    不依赖 GitHub API，无需 Token，无频率限制。
    """
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = client.get(
                GITHUB_RELEASES_URL + "/latest",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    ),
                },
            )
            response.raise_for_status()
            html = response.text

        # 从页面中提取最新 release 的 tag URL
        # 匹配形如: /yong0512/OpenSteamToolDesktop/releases/tag/v1.2.3
        match = re.search(
            r"/" + GITHUB_REPO_OWNER + r"/" + GITHUB_REPO_NAME + r'/releases/tag/(v?[\d\.]+)',
            html,
        )
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

        return {
            "tag_name": tag_name,
            "version": version,
            "name": tag_name,
            "body": "",
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
