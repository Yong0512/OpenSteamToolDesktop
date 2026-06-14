"""
统一封面下载模块
=================

提供游戏封面的内存缓存 + 磁盘持久化 + 异步下载功能。
确保 GameCard、SearchPage 和 RecommendCard 共享同一份缓存。

.. code-block:: python

    from utils.download_cover import CoverCache, download_cover

    # 使用全局缓存实例
    CoverCache.instance()

    # 后台线程中下载
    data = download_cover("730")
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from PyQt6.QtGui import QPixmap

from utils.logger import setup_logger
from utils.path_manager import PathManager

logger = setup_logger(__name__)


class CoverCache:
    """游戏封面缓存管理器（单例）

    特性：
    - **内存缓存**：进程内共享，避免重复下载
    - **磁盘持久化**：保存到 ``cache/covers/{app_id}.jpg``，下次启动直接加载
    - **线程安全**：读写均在主线程 QPixmap 操作中使用（QPixmap 非线程安全）
    """

    _instance: CoverCache | None = None

    @classmethod
    def instance(cls) -> CoverCache:
        """获取全局单例"""
        if cls._instance is None:
            cls._instance = CoverCache()
        return cls._instance

    def __init__(self) -> None:
        if CoverCache._instance is not None:
            raise RuntimeError("CoverCache is a singleton, use CoverCache.instance()")
        self._cache: dict[str, QPixmap | None] = {}
        self._preloaded: bool = False

    # ── 公开接口 ──────────────────────────────────────────

    def get(self, app_id: str) -> QPixmap | None:
        """获取缓存的封面 QPixmap（None 表示已知无封面，KeyError 表示未缓存）"""
        if app_id not in self._cache:
            raise KeyError(app_id)
        return self._cache[app_id]

    def has(self, app_id: str) -> bool:
        """检查 app_id 是否已缓存（含标记为无封面的情况）"""
        self._ensure_preloaded()
        return app_id in self._cache

    def get(self, app_id: str) -> QPixmap | None:
        """获取缓存的封面 QPixmap（None 表示已知无封面，KeyError 表示未缓存）"""
        self._ensure_preloaded()
        if app_id not in self._cache:
            raise KeyError(app_id)
        return self._cache[app_id]

    def is_known_missing(self, app_id: str) -> bool:
        """是否已知该游戏无封面"""
        self._ensure_preloaded()
        return app_id in self._cache and self._cache[app_id] is None

    def set(self, app_id: str, pix: QPixmap | None) -> None:
        """设置缓存条目（None = 标记为无封面）"""
        self._cache[app_id] = pix

    def save_to_disk(self, app_id: str, data: bytes) -> None:
        """将原始图片数据写入磁盘缓存

        Args:
            app_id: Steam AppID
            data: 原始 JPEG 图片字节
        """
        try:
            covers_dir = PathManager.covers_dir()
            path = covers_dir / f"{app_id}.jpg"
            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            logger.debug(f"Failed to save cover to disk ({app_id}): {e}")

    # ── 私有方法 ──────────────────────────────────────────

    def _ensure_preloaded(self) -> None:
        """延迟预加载（首次 has/get 调用时触发，确保 QApplication 已就绪）"""
        if self._preloaded:
            return
        self._preloaded = True
        try:
            self._preload_from_disk()
        except Exception as e:
            logger.debug("CoverCache preload skipped: %s", e)

    def _preload_from_disk(self) -> None:
        """启动时从磁盘预加载所有已缓存的封面"""
        covers_dir = PathManager.covers_dir()
        if not covers_dir.exists():
            return
        loaded = 0
        start = time.monotonic()
        for f in covers_dir.glob("*.jpg"):
            app_id = f.stem
            if app_id in self._cache:
                continue
            try:
                pix = QPixmap(str(f))
                if not pix.isNull():
                    self._cache[app_id] = pix
                    loaded += 1
            except Exception:
                pass
        if loaded:
            elapsed = time.monotonic() - start
            logger.debug(f"Preloaded {loaded} covers from disk in {elapsed:.2f}s")


def download_cover(app_id: str) -> bytes | None:
    """下载游戏封面图片（供 AsyncWorker 后台线程调用）

    下载策略（按优先级）：
    1. Steam CDN header.jpg（主 CDN）
    2. 备选 CDN header.jpg（FALLBACK_CDN_HOSTS）
    3. Steam Store API 获取 header_image URL

    Args:
        app_id: Steam AppID

    Returns:
        原始 JPEG 字节数据，失败返回 None
    """
    from utils.http_client import get_bytes, get_json
    from config import STEAM_CDN_BASE, STEAM_STORE_API, HTTP_COVER_TIMEOUT

    # CDN header.jpg
    data = get_bytes(f"{STEAM_CDN_BASE}/{app_id}/header.jpg", timeout=HTTP_COVER_TIMEOUT)
    if data:
        return data

    # Store API 兜底 — 获取 header_image 官方地址
    try:
        info = get_json(STEAM_STORE_API, params={"appids": app_id, "cc": "us"}, timeout=HTTP_COVER_TIMEOUT)
        if info and app_id in info and info[app_id].get("success"):
            header_url = info[app_id]["data"].get("header_image", "")
            if header_url:
                return get_bytes(header_url, timeout=HTTP_COVER_TIMEOUT)
    except Exception as e:
        logger.debug(f"Store API fallback for {app_id}: {e}")

    return None
