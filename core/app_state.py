from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

STEAM_INSTALLED = "steam_installed"
STEAM_RUNNING = "steam_running"
STEAM_PATH = "steam_path"
DLL_DEPLOYED = "dll_deployed"
DLL_ACTIVE = "dll_active"
GAME_COUNT = "game_count"

class AppState(QObject):

    injection_changed = pyqtSignal()

    _instance: AppState | None = None

    @classmethod
    def instance(cls) -> AppState:
        if cls._instance is None:
            cls._instance = AppState()
        return cls._instance

    def __init__(self):
        if AppState._instance is not None:
            raise RuntimeError("AppState is a singleton, use AppState.instance()")
        super().__init__()
        self._state: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    _SIGNAL_KEYS = (DLL_DEPLOYED, DLL_ACTIVE, STEAM_INSTALLED, STEAM_RUNNING, STEAM_PATH, GAME_COUNT)

    def set(self, key: str, value):
        old = self._state.get(key)
        if old != value:
            self._state[key] = value
            if key in self._SIGNAL_KEYS:
                self.injection_changed.emit()

    def set_bulk(self, updates: dict[str, object]):
        changed = False
        for k, v in updates.items():
            if self._state.get(k) != v:
                self._state[k] = v
                changed = True
        if changed:
            self.injection_changed.emit()

app_state = AppState.instance()
