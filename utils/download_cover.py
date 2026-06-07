from __future__ import annotations

import time

from PyQt6.QtGui import QPixmap

from utils.logger import setup_logger
from utils.path_manager import PathManager

logger = setup_logger(__name__)

class CoverCache:

    _instance: CoverCache | None = None

    @classmethod
    def instance(cls) -> CoverCache:
        if cls._instance is None:
            cls._instance = CoverCache()
        return cls._instance

    def __init__(self) -> None:
        if CoverCache._instance is not None:
            raise RuntimeError("CoverCache is a singleton, use CoverCache.instance()")
        self._cache: dict[str, QPixmap | None] = {}
        self._preloaded: bool = False

    def get(self, app_id: str) -> QPixmap | None:
        if app_id not in self._cache:
            raise KeyError(app_id)
        return self._cache[app_id]

    def has(self, app_id: str) -> bool:
        self._ensure_preloaded()
        return app_id in self._cache

    def get(self, app_id: str) -> QPixmap | None:
        self._ensure_preloaded()
        if app_id not in self._cache:
            raise KeyError(app_id)
        return self._cache[app_id]

    def is_known_missing(self, app_id: str) -> bool:
        self._ensure_preloaded()
        return app_id in self._cache and self._cache[app_id] is None

    def set(self, app_id: str, pix: QPixmap | None) -> None:
        self._cache[app_id] = pix

    def save_to_disk(self, app_id: str, data: bytes) -> None:
        try:
            covers_dir = PathManager.covers_dir()
            path = covers_dir / f"{app_id}.jpg"
            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            logger.debug(f"Failed to save cover to disk ({app_id}): {e}")

    def _ensure_preloaded(self) -> None:
        if self._preloaded:
            return
        self._preloaded = True
        try:
            self._preload_from_disk()
        except Exception as e:
            logger.debug("CoverCache preload skipped: %s", e)

    def _preload_from_disk(self) -> None:
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
    from utils.http_client import get_bytes, get_json
    from config import STEAM_CDN_BASE, STEAM_STORE_API, HTTP_COVER_TIMEOUT

    data = get_bytes(f"{STEAM_CDN_BASE}/{app_id}/header.jpg", timeout=HTTP_COVER_TIMEOUT)
    if data:
        return data

    try:
        info = get_json(STEAM_STORE_API, params={"appids": app_id, "cc": "us"}, timeout=HTTP_COVER_TIMEOUT)
        if info and app_id in info and info[app_id].get("success"):
            header_url = info[app_id]["data"].get("header_image", "")
            if header_url:
                return get_bytes(header_url, timeout=HTTP_COVER_TIMEOUT)
    except Exception as e:
        logger.debug(f"Store API fallback for {app_id}: {e}")

    return None
