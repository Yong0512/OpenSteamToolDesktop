"""
配置文件管理器
===============

管理 ``%APPDATA%/OpenSteamToolDesktop/config.json`` 的 JSON 读写。

特性：
- 自动创建配置目录
- ``get`` / ``set`` 接口
- ``set_bulk`` 批量写入减少磁盘 IO

.. code-block:: python

    from core.config_manager import ConfigManager

    cm = ConfigManager()
    theme = cm.get("theme_mode", "dark")
    cm.set("theme_mode", "light")
"""
from __future__ import annotations

import json
import os
from typing import Any

from config import CONFIG_DIR, CONFIG_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ConfigManager:
    """JSON 配置文件的读写管理器"""

    def __init__(self) -> None:
        """初始化并加载配置"""
        self._data: dict[str, Any] = {}
        self.config_file: str = CONFIG_FILE
        self._load()

    # ── 公开接口 ──────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key: 配置键名
            default: 不存在时的默认值

        Returns:
            配置值或默认值
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置值并立即保存

        Args:
            key: 配置键名
            value: 新值
        """
        self._data[key] = value
        self._save()

    def set_bulk(self, updates: dict[str, Any]) -> None:
        """批量设置配置值（一次磁盘写入）

        Args:
            updates: {key: value, ...} 字典
        """
        self._data.update(updates)
        self._save()

    def get_all(self) -> dict[str, Any]:
        """返回全部配置的副本"""
        return dict(self._data)

    # ── 私有方法 ──────────────────────────────────────────

    def _load(self) -> None:
        """从文件加载配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.debug("Config loaded from %s (%d keys)", CONFIG_FILE, len(self._data))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config: %s, using defaults", e)
                self._data = {}
        else:
            logger.debug("No config file found, using defaults")
            self._data = {}

    def _save(self) -> None:
        """保存配置到文件"""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("Failed to save config: %s", e)
