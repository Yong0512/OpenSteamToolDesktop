"""
统一 HTTP 客户端
================

所有外部 HTTP 请求的唯一入口。

特性：
- 自动重试（默认 2 次）
- 404 持久化缓存（``cache/http_404_cache.json``）
- 统一 User-Agent
- 结构化异常日志

.. code-block:: python

    from utils.http_client import get, get_json, get_bytes, get_text

    data = get_json("https://store.steampowered.com/api/appdetails?appids=730")
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import httpx

from config import (
    HTTP_DEFAULT_TIMEOUT,
    HTTP_MAX_RETRIES,
    STEAM_USER_AGENT,
    SSL_VERIFY,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)
logger.info(f"SSL verification: {'disabled' if not SSL_VERIFY else 'enabled'} (from config)")

# ── 系统代理配置 ──────────────────────────────────────────
def _get_system_proxy() -> str | None:
    """获取系统代理设置（Windows 自动读取 IE/系统代理配置）

    Returns:
        代理 URL 字符串（如 "http://proxy:port"），如果没有配置代理则返回 None
    """
    try:
        raw_proxies = urllib.request.getproxies()
        if not raw_proxies:
            return None

        # 优先使用 HTTPS 代理，如果没有则使用 HTTP 代理
        proxy_url = raw_proxies.get("https") or raw_proxies.get("http")
        if not proxy_url:
            return None

        # 确保代理 URL 有协议头
        if "://" not in proxy_url:
            proxy_url = f"http://{proxy_url}"

        logger.info("系统代理已启用: %s", proxy_url)
        return proxy_url
    except Exception as e:
        logger.warning("读取系统代理失败: %s", e)
    return None


_system_proxy = _get_system_proxy()

# ── 模块级常量 ──────────────────────────────────────────────
_DEFAULT_TIMEOUT: float = HTTP_DEFAULT_TIMEOUT
_MAX_RETRIES: int = HTTP_MAX_RETRIES

# ── 404 持久化缓存 ──────────────────────────────────────────
from utils.path_manager import PathManager

_404_cache: dict[str, bool] = {}


def _get_404_cache_path() -> Path:
    return PathManager.http_404_cache_path()


def _load_404_cache() -> dict[str, bool]:
    path = _get_404_cache_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as _f:
                return json.load(_f)
        except Exception:
            pass
    return {}


_404_cache = _load_404_cache()
if _404_cache:
    logger.debug("Loaded %d entries from 404 cache", len(_404_cache))


def _save_404_cache() -> None:
    """将 404 缓存写入文件"""
    try:
        with open(_get_404_cache_path(), "w", encoding="utf-8") as _f:
            json.dump(_404_cache, _f, ensure_ascii=False)
    except OSError:
        pass  # 磁盘写入失败不影响功能


def is_404_cached(url: str) -> bool:
    """检查 URL 是否已知返回 404 并已缓存

    Args:
        url: 要检查的 URL

    Returns:
        ``True`` 如果该 URL 已知为 404
    """
    return _404_cache.get(url, False)


def add_404_cache(url: str) -> None:
    """将 URL 标记为已知返回 404

    Args:
        url: 返回了 404 的 URL
    """
    _404_cache[url] = True
    if len(_404_cache) % 10 == 0:
        _save_404_cache()


def save_404_cache_now() -> None:
    """立即刷新 404 缓存到磁盘（应用退出时调用）"""
    _save_404_cache()


# ── 公开 HTTP 函数 ─────────────────────────────────────────

def get(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response | None:
    """发送 GET 请求，支持自动重试与 404 缓存

    Args:
        url: 请求 URL
        timeout: 超时秒数
        headers: 额外请求头（自动附加 User-Agent）
        params: URL 查询参数
        follow_redirects: 是否跟随重定向

    Returns:
        :class:`httpx.Response` 或 ``None``（失败时）
    """
    if is_404_cached(url):
        logger.debug("404 cache hit, skipping: %s", url)
        return None

    _headers: dict[str, str] = {"User-Agent": STEAM_USER_AGENT}
    if headers:
        _headers.update(headers)

    last_error: str | None = None
    for attempt in range(1 + _MAX_RETRIES):
        try:
            with httpx.Client(
                timeout=timeout,
                headers=_headers,
                follow_redirects=follow_redirects,
                proxy=_system_proxy,  # 使用系统代理（单个 URL）
                verify=SSL_VERIFY,  # 使用 config 中的 SSL 配置
            ) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            last_error = f"HTTP {status}"
            if status == 404:
                logger.debug("404 for %s, adding to cache", url)
                add_404_cache(url)
                return None
        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.ConnectError:
            last_error = "connection refused"
        except Exception as e:
            last_error = str(e)

        if attempt < _MAX_RETRIES:
            logger.debug("Retry %d/%d for %s: %s", attempt + 1, _MAX_RETRIES, url, last_error)

    logger.warning("HTTP GET failed after %d attempts: %s (%s)", _MAX_RETRIES + 1, url, last_error)
    return None


def get_json(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """GET 请求并解析 JSON

    Returns:
        解析后的字典，或 ``None``（失败时）
    """
    resp = get(url, timeout=timeout, headers=headers, params=params)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError as e:
        logger.warning("JSON parse failed for %s: %s", url, e)
        return None


def get_bytes(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> bytes | None:
    """GET 请求获取二进制内容

    Returns:
        原始字节数据，或 ``None``（失败时）
    """
    resp = get(url, timeout=timeout, headers=headers)
    if resp is None:
        return None
    return resp.content


def get_text(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> str | None:
    """GET 请求获取文本内容

    Returns:
        响应文本，或 ``None``（失败时）
    """
    resp = get(url, timeout=timeout, headers=headers, params=params)
    if resp is None:
        return None
    return resp.text
