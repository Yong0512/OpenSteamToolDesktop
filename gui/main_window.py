from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from qfluentwidgets import (
    FluentIcon,
    NavigationItemPosition,
    MSFluentWindow,
    MessageBox,
    InfoBar,
    InfoBarPosition,
)

from config import APP_NAME, APP_VERSION
from core.config_manager import ConfigManager
from core.game_manager import LuaGameManager
from core.steam_bridge import SteamBridge
from utils.logger import setup_logger

logger = setup_logger(__name__)

class MainWindow(MSFluentWindow):

    def __init__(
        self,
        bridge: SteamBridge,
        game_manager: LuaGameManager,
        config_manager: ConfigManager,
    ):
        super().__init__()
        self._bridge = bridge
        self._game_manager = game_manager
        self._config = config_manager

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "gui" / "icon.ico"
        else:
            icon_path = Path(__file__).parent.parent / "gui" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.titleBar.raise_()

        from gui.home_page import HomePage
        from gui.inject_page import InjectPage
        from gui.search_page import SearchPage
        from gui.library_page import LibraryPage

        self.home_page = HomePage(
            bridge,
            game_manager,
            page_switch_callback=self._switch_page,
            parent=self,
        )
        self.inject_page = InjectPage(bridge, config_manager, parent=self)
        self.search_page = SearchPage(game_manager, bridge=bridge, parent=self)
        self.library_page = LibraryPage(game_manager, parent=self)

        from core.app_state import app_state
        app_state.injection_changed.connect(self.home_page.refresh_status)

        self.inject_page.inject_status_changed.connect(self.home_page.refresh_status)

        self._home_nav_btn = self.addSubInterface(self.home_page, FluentIcon.HOME, "首页")
        self._inject_nav_btn = self.addSubInterface(self.inject_page, FluentIcon.DOWNLOAD, "注入管理")
        self._search_nav_btn = self.addSubInterface(self.search_page, FluentIcon.SEARCH, "搜索入库")
        self._library_nav_btn = self.addSubInterface(self.library_page, FluentIcon.LIBRARY, "游戏库")

        self._restart_nav_item = self.navigationInterface.addItem(
            routeKey="restart_steam",
            icon=FluentIcon.POWER_BUTTON,
            text="重启 Steam",
            onClick=self._on_restart_steam,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.setStyleSheet("MSFluentWindow { background: transparent; }")

    def _switch_to_default_page(self):
        try:
            default = self._config.get("default_page", "home")
        except Exception:
            default = "home"
        page_map = {
            "home": self.home_page,
            "inject": self.inject_page,
            "search": self.search_page,
            "library": self.library_page,
        }
        self.switchTo(page_map.get(default, self.home_page))

    def switch_to_default_page(self):
        self._switch_to_default_page()

    def _switch_page(self, page_key: str):
        page_map = {
            "home": self.home_page,
            "inject": self.inject_page,
            "search": self.search_page,
            "library": self.library_page,
        }
        target = page_map.get(page_key)
        if target:
            self.switchTo(target)

    def _on_restart_steam(self):

        self._bridge.redetect_steam()
        steam_path = self._bridge.get_steam_path()

        if not steam_path or not os.path.exists(steam_path):
            MessageBox(
                "错误",
                "未检测到 Steam 安装路径，请检查 Steam 是否已安装或在设置中手动指定路径。",
                self,
            ).exec()
            return

        steam_exe = os.path.join(steam_path, "steam.exe")
        if not os.path.exists(steam_exe):
            MessageBox(
                "错误",
                "未找到 Steam 可执行文件 (steam.exe)，请检查 Steam 安装是否完整。",
                self,
            ).exec()
            return

        dialog = MessageBox(
            "重启 Steam",
            "确定要重启 Steam 吗？\n\n这将关闭当前运行的 Steam 并重新启动。",
            self,
        )
        if not dialog.exec():
            return

        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "steam.exe"],
                capture_output=True,
                timeout=10,
                creationflags=0x08000000,
            )
        except Exception:
            pass

        try:
            subprocess.Popen([steam_exe])
            InfoBar.success(
                "重启成功",
                "Steam 已重启",
                parent=self,
                position=InfoBarPosition.TOP,
            )
        except Exception as e:
            InfoBar.error(
                "错误",
                str(e),
                parent=self,
                position=InfoBarPosition.TOP,
            )

    def _update_restart_button_state(self):
        steam_path = self._bridge.get_steam_path()
        installed = bool(steam_path and os.path.exists(steam_path))
        self.set_restart_button_enabled(installed)

    def _on_steam_status_changed(self, installed: bool):
        self.set_restart_button_enabled(installed)

    def set_restart_button_enabled(self, enabled: bool):
        if hasattr(self, "_restart_nav_item"):
            self._restart_nav_item.setEnabled(enabled)

    def notify_theme_changed(self):
        pages = [self.home_page, self.inject_page, self.search_page, self.library_page]
        for page in pages:
            if hasattr(page, "notify_theme_changed"):
                page.notify_theme_changed()
            page.update()
            page.repaint()

    def apply_window_effect(self, effect: str):
        if effect == "mica":
            self.setMicaEffectEnabled(True)
        else:
            self.setMicaEffectEnabled(False)

    def closeEvent(self, event):
        logger.info("MainWindow closing, cleaning up threads...")
        try:
            self.shutdown()
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
        event.accept()

    def shutdown(self):
        pages = [self.home_page, self.inject_page, self.search_page, self.library_page]

        for page in pages:
            if hasattr(page, '_auto_refresh_timer') and page._auto_refresh_timer is not None:
                try:
                    page._auto_refresh_timer.stop()
                except Exception:
                    pass

        try:
            from gui.home_page import _executor
            _executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            pass

        for page in pages:
            try:
                if hasattr(page, '_cancel_all_workers'):
                    page._cancel_all_workers()
            except Exception:
                pass

        try:
            self.library_page._alive = False
            if hasattr(self.library_page, 'hideEvent'):

                pass
        except Exception:
            pass

        try:
            if hasattr(self.search_page, '_cards'):
                for card in self.search_page._cards:
                    try:
                        card.cleanup()
                    except Exception:
                        pass
                self.search_page._cards.clear()
            if hasattr(self.search_page, '_rec_cards'):
                for card in self.search_page._rec_cards:
                    try:
                        card.cleanup()
                    except Exception:
                        pass
                self.search_page._rec_cards.clear()
        except Exception:
            pass

        try:
            if hasattr(self.library_page, '_card_list'):
                for card in self.library_page._card_list:
                    try:
                        card.cleanup()
                    except Exception:
                        pass
                self.library_page._card_list.clear()
        except Exception:
            pass

        logger.info("MainWindow shutdown complete")
