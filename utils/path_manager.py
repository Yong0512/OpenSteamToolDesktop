from __future__ import annotations

from pathlib import Path

from config import APP_NAME


class PathManager:

    _base: Path | None = None

    @classmethod
    def base_dir(cls) -> Path:
        if cls._base is None:
            cls._base = Path.home() / f".{APP_NAME}"
            cls._base.mkdir(parents=True, exist_ok=True)
        return cls._base

    @classmethod
    def logs_dir(cls) -> Path:
        d = cls.base_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def cache_dir(cls) -> Path:
        d = cls.base_dir() / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def covers_dir(cls) -> Path:
        d = cls.cache_dir() / "covers"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def crash_log_path(cls) -> Path:
        return cls.logs_dir() / "crash.log"

    @classmethod
    def stderr_log_path(cls) -> Path:
        return cls.logs_dir() / "stderr.log"

    @classmethod
    def http_404_cache_path(cls) -> Path:
        return cls.cache_dir() / "http_404_cache.json"
