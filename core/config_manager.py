from __future__ import annotations

import json
import os
from typing import Any

from config import CONFIG_DIR, CONFIG_FILE
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ConfigManager:

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.config_file: str = CONFIG_FILE
        self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def set_bulk(self, updates: dict[str, Any]) -> None:
        self._data.update(updates)
        self._save()

    def get_all(self) -> dict[str, Any]:
        return dict(self._data)

    def _load(self) -> None:
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
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("Failed to save config: %s", e)
