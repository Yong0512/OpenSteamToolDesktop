"""
路径管理器
==========

统一管理日志、缓存等所有输出目录。
固定使用 Windows ``我的文档\\.OpenSteamToolDesktop\\`` 目录。

.. code-block:: python

    from utils.path_manager import PathManager

    print(PathManager.logs_dir())       # .../Documents/.OpenSteamToolDesktop/logs/
    print(PathManager.covers_dir())     # .../Documents/.OpenSteamToolDesktop/cache/covers/
"""
from __future__ import annotations

from pathlib import Path

from config import APP_NAME


class PathManager:
    """统一路径管理器"""

    _base: Path | None = None

    @classmethod
    def base_dir(cls) -> Path:
        """数据根目录：``{home}\\.{APP_NAME}\\``"""
        if cls._base is None:
            cls._base = Path.home() / f".{APP_NAME}"
            cls._base.mkdir(parents=True, exist_ok=True)
        return cls._base

    @classmethod
    def user_data_dir(cls) -> Path:
        """用户数据目录（base_dir 的别名，便于理解）

        用于存放用户数据，如 DLL、配置等。
        """
        return cls.base_dir()

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
