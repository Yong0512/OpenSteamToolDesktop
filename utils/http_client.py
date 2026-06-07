from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from config import (
    HTTP_DEFAULT_TIMEOUT,
    HTTP_MAX_RETRIES,
    STEAM_USER_AGENT,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

_DEFAULT_TIMEOUT: float = HTTP_DEFAULT_TIMEOUT
_MAX_RETRIES: int = HTTP_MAX_RETRIES

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
    try:
        with open(_get_404_cache_path(), "w", encoding="utf-8") as _f:
            json.dump(_404_cache, _f, ensure_ascii=False)
    except OSError:
        pass

def is_404_cached(url: str) -> bool:
    return _404_cache.get(url, False)

def add_404_cache(url: str) -> None:
    _404_cache[url] = True
    if len(_404_cache) % 10 == 0:
        _save_404_cache()

def save_404_cache_now() -> None:
    _save_404_cache()

def get(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response | None:
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
    resp = get(url, timeout=timeout, headers=headers, params=params)
    if resp is None:
        return None
    return resp.text
