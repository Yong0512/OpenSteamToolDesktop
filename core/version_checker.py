from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx

from config import (
    APP_VERSION,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT: float = 5.0

@dataclass
class ReleaseInfo:
    version: str
    tag_name: str
    title: str
    body: str
    html_url: str
    published_at: str
    is_newer: bool

def _parse_semver(version: str) -> Tuple[int, int, int]:
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
    try:
        lv = _parse_semver(latest)
        cv = _parse_semver(current)
        return lv > cv
    except Exception:
        return False

def _fetch_latest_release() -> Tuple[dict | None, str | None]:
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

        match = re.search(
            r"/" + GITHUB_REPO_OWNER + r"/" + GITHUB_REPO_NAME + r'/releases/tag/(v?[\d\.]+)',
            html,
        )
        if not match:

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
