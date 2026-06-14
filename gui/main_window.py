from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QIcon

from qfluentwidgets import (
    FluentIcon,
    NavigationItemPosition,
    MSFluentWindow,
    MessageBox,
    InfoBar,
    InfoBarPosition,
    StateToolTip,
    ProgressBar,
)
from utils.async_worker import AsyncWorker

from config import APP_NAME, APP_VERSION
from core.config_manager import ConfigManager
from core.game_manager import LuaGameManager
from core.steam_bridge import SteamBridge
from core.app_state import app_state, DLL_VERSION_MISMATCH
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MainWindow(MSFluentWindow):
    """主窗口 — MSFluentWindow 架构"""

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
        # 程序图标（兼容 PyInstaller 打包路径）
        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "assets" / "icon.ico"
        else:
            icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.titleBar.raise_()

        # 延迟导入页面
        from gui.home_page import HomePage
        from gui.inject_page import InjectPage
        from gui.search_page import SearchPage
        from gui.library_page import LibraryPage
        from gui.accelerate_page import AcceleratePage

        # 创建页面
        self.home_page = HomePage(
            bridge,
            game_manager,
            page_switch_callback=self._switch_page,
            parent=self,
        )

        self.inject_page = InjectPage(bridge, config_manager, parent=self)

        self.search_page = SearchPage(game_manager, bridge=bridge, parent=self)

        self.library_page = LibraryPage(game_manager, bridge=bridge, parent=self)

        self.accelerate_page = AcceleratePage(parent=self)
        self.accelerate_page.setObjectName("acceleratePage")

        # 连接首页 DLL 检查信号
        self.home_page.dll_check_needed.connect(self._check_dll_version_on_startup)

        # ---- 全局状态订阅（一处改动，全局跟进） ----
        from core.app_state import app_state
        app_state.injection_changed.connect(self.home_page.refresh_status)

        # 保留旧信号兼容（InjectPage 内部同步用）
        self.inject_page.inject_status_changed.connect(self.home_page.refresh_status)

        # ---- 导航 ----

        # 页面导航
        self._home_nav_btn = self.addSubInterface(self.home_page, FluentIcon.HOME, "首页")
        self._inject_nav_btn = self.addSubInterface(self.inject_page, FluentIcon.DOWNLOAD, "注入管理")
        self._search_nav_btn = self.addSubInterface(self.search_page, FluentIcon.SEARCH, "搜索入库")
        self._library_nav_btn = self.addSubInterface(self.library_page, FluentIcon.LIBRARY, "游戏库")
        self._accelerate_nav_btn = self.addSubInterface(self.accelerate_page, FluentIcon.SPEED_HIGH, "科学加速")

        # 底部：重启 Steam 按钮
        self._restart_nav_item = self.navigationInterface.addItem(
            routeKey="restart_steam",
            icon=FluentIcon.POWER_BUTTON,
            text="重启 Steam",
            onClick=self._on_restart_steam,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # 透明背景
        self.setStyleSheet("MSFluentWindow { background: transparent; }")

    def _check_dll_version_on_startup(self):
        """检查 DLL 版本（在首页 showEvent 时调用）

        逻辑：
        1. 总是检查是否有新版本（后台）
        2. 如果有新版本且本地没有，自动下载
        3. 只有已注入时才检查本地 DLL 版本是否匹配
        """
        if self._bridge is None:
            return

        try:
            # 使用 AsyncWorker 在后台检查更新（避免阻塞 UI）
            self._update_check_worker = AsyncWorker(self._check_for_updates_sync)
            self._update_check_worker.finished_with_result.connect(self._on_update_check_result)
            self._update_check_worker.finished_with_error.connect(self._on_update_check_error)
            self._update_check_worker.start()

        except Exception as e:
            logger.error(f"DLL 版本检查失败: {e}")

    def _check_for_updates_sync(self):
        """后台线程中检查更新（同步函数，供 AsyncWorker 调用）"""
        try:
            # 检查是否有更新
            update_available, msg, version_info = self._bridge.check_for_dll_updates()
            return {
                "update_available": update_available,
                "message": msg,
                "version_info": version_info,
            }
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return {
                "update_available": False,
                "message": f"检查更新失败: {e}",
                "version_info": None,
            }

    def _on_update_check_result(self, result: dict):
        """更新检查完成（主线程回调）"""
        try:
            update_available = result.get("update_available", False)
            message = result.get("message", "")
            version_info = result.get("version_info")

            if update_available and version_info:
                # 发现新版本，后台下载（不管是否注入）
                logger.info(f"发现新版本，开始后台下载：{message}")
                self._download_and_install_dll(version_info)
            else:
                # 无更新或已是最新版本
                logger.info(f"DLL 版本检查完成：{message}")
                # 只有已注入时才检查本地版本是否匹配
                if self._bridge and self._bridge.is_deployed():
                    self._check_local_dll_mismatch()
                
        except Exception as e:
            logger.error(f"处理更新检查结果失败: {e}")

    def _on_update_check_error(self, error_msg: str):
        """更新检查失败（主线程回调）"""
        logger.warning(f"更新检查失败: {error_msg}")
        # 失败时不阻塞用户，继续检查本地 DLL
        self._check_local_dll_mismatch()

    def _prompt_download_new_version(self, message: str, version_info: dict):
        """提示用户下载新版本 DLL"""
        msg_box = MessageBox(
            "发现新版本 DLL",
            f"{message}\n\n是否立即下载并安装？",
            self,
        )
        msg_box.yesButton.setText("立即下载")
        msg_box.cancelButton.setText("稍后提醒")

        if msg_box.exec():
            self._download_and_install_dll(version_info)
        else:
            # 用户选择稍后提醒
            app_state.set(DLL_VERSION_MISMATCH, True)

    def _download_and_install_dll(self, version_info: dict):
        """下载并安装 DLL（使用 AsyncWorker 后台下载）"""
        # 显示进度提示
        self._download_progress_tip = StateToolTip(
            "正在下载 DLL",
            "准备下载...",
            self,
        )
        self._download_progress_tip.show()

        # 使用 AsyncWorker 在后台下载
        self._download_worker = AsyncWorker(self._download_dll_sync, version_info)
        self._download_worker.finished_with_result.connect(self._on_download_complete)
        self._download_worker.finished_with_error.connect(self._on_download_error)
        self._download_worker.start()

        # 连接进度信号（如果 DLLManager 支持）
        dll_manager = self._bridge.get_dll_manager()
        if dll_manager:
            dll_manager.download_progress.connect(self._on_download_progress)

    def _download_dll_sync(self, version_info: dict) -> dict:
        """后台下载 DLL（同步函数，供 AsyncWorker 调用）"""
        try:
            success, msg = self._bridge.download_and_install_latest_dll()
            return {"success": success, "message": msg}
        except Exception as e:
            logger.error(f"下载 DLL 失败: {e}")
            return {"success": False, "message": f"下载失败: {e}"}

    def _on_download_progress(self, downloaded: int, total: int):
        """下载进度更新"""
        if hasattr(self, '_download_progress_tip') and self._download_progress_tip:
            if total > 0:
                percent = int((downloaded / total) * 100)
                self._download_progress_tip.setContent(f"下载进度: {percent}% ({downloaded}/{total} bytes)")
            else:
                self._download_progress_tip.setContent(f"已下载: {downloaded} bytes")

    def _on_download_complete(self, result: dict):
        """下载完成（主线程回调）"""
        try:
            success = result.get("success", False)
            message = result.get("message", "")

            # 关闭进度提示
            if hasattr(self, '_download_progress_tip') and self._download_progress_tip:
                self._download_progress_tip.close()

            if success:
                InfoBar.success(
                    "DLL 更新完成",
                    f"{message}\n\n请重启 Steam 使新版本生效。",
                    parent=self,
                    position=InfoBarPosition.TOP,
                )
                # 清除版本不匹配状态
                app_state.set(DLL_VERSION_MISMATCH, False)
                # 更新 bridge 的 DLL 源目录（指向新下载的版本）
                if self._bridge:
                    self._bridge._update_dll_source_from_manager()
                # 通知注入管理页面刷新 DLL 版本显示
                if hasattr(self, 'inject_page') and self.inject_page:
                    self.inject_page._update_dll_version_display()
            else:
                InfoBar.error(
                    "DLL 下载失败",
                    message,
                    parent=self,
                    position=InfoBarPosition.TOP,
                )

        except Exception as e:
            logger.error(f"处理下载结果失败: {e}")

    def _on_download_error(self, error_msg: str):
        """下载失败（主线程回调）"""
        logger.error(f"下载失败: {error_msg}")
        if hasattr(self, '_download_progress_tip') and self._download_progress_tip:
            self._download_progress_tip.close()

        InfoBar.error(
            "下载失败",
            error_msg,
            parent=self,
            position=InfoBarPosition.TOP,
        )

    def _check_local_dll_mismatch(self):
        """检查本地 DLL 版本是否匹配（原有逻辑）

        只有已注入时才检查（未注入时没有对比基准）
        """
        if self._bridge is None or not self._bridge.is_deployed():
            return

        try:
            mismatch, mismatched_dlls = self._bridge.check_dll_version_mismatch()
            if mismatch:
                msg = "检测到 DLL 文件版本不匹配：\n\n"
                msg += "\n".join([f"• {dll}" for dll in mismatched_dlls])
                msg += "\n\n是否立即更新注入？"

                from qfluentwidgets import MessageBox
                msg_box = MessageBox(
                    "DLL 版本不匹配",
                    msg,
                    self,
                )
                msg_box.yesButton.setText("立即更新")
                msg_box.cancelButton.setText("稍后提醒")

                if msg_box.exec():
                    self._update_and_inject()
                else:
                    # 用户选择稍后提醒，设置状态
                    app_state.set(DLL_VERSION_MISMATCH, True)
        except Exception as e:
            from loguru import logger
            logger.error(f"本地 DLL 版本检查失败: {e}")

    def _update_and_inject(self):
        """更新 DLL 并重新注入"""
        if self._bridge is None:
            return

        # 显示进度提示
        self._inject_progress = StateToolTip(
            "正在更新",
            "正在更新 DLL 并重新注入...",
            self,
        )
        self._inject_progress.show()

        # 1. 关闭 Steam
        self._do_kill_steam()

    def _do_kill_steam(self):
        """关闭 Steam"""
        if self._bridge is None:
            return

        success, msg = self._bridge.kill_steam()
        if success:
            # 等待 Steam 关闭
            QTimer.singleShot(2000, self._do_inject)
        else:
            if hasattr(self, '_inject_progress') and self._inject_progress:
                self._inject_progress.close()
            InfoBar.error(
                "错误",
                f"关闭 Steam 失败: {msg}",
                parent=self,
                position=InfoBarPosition.TOP,
            )

    def _do_inject(self):
        """执行注入"""
        if self._bridge is None:
            return

        success, msg = self._bridge.inject()
        if hasattr(self, '_inject_progress') and self._inject_progress:
            self._inject_progress.close()

        if success:
            # 清除 DLL 版本不匹配状态
            app_state.set(DLL_VERSION_MISMATCH, False)

            InfoBar.success(
                "更新成功",
                "DLL 已更新并重新注入，请重启 Steam",
                parent=self,
                position=InfoBarPosition.TOP,
            )
            # 提示用户重启 Steam
            from qfluentwidgets import MessageBox
            from PyQt6.QtWidgets import QMessageBox
            msg_box = MessageBox(
                "重启 Steam",
                "DLL 已更新并重新注入，是否立即重启 Steam？",
                self,
            )
            msg_box.yesButton.setText("立即重启")
            msg_box.cancelButton.setText("稍后重启")

            if msg_box.exec():
                self._bridge.start_steam()
        else:
            InfoBar.error(
                "更新失败",
                msg,
                parent=self,
                position=InfoBarPosition.TOP,
            )

    # 切换到默认页面

    # ---- 页面路由 ----

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
        """接收首页的页面跳转请求，切换到对应页面"""
        page_map = {
            "home": self.home_page,
            "inject": self.inject_page,
            "search": self.search_page,
            "library": self.library_page,
        }
        target = page_map.get(page_key)
        if target:
            self.switchTo(target)

    # ---- 重启 Steam ----

    def _on_restart_steam(self):
        """重启 Steam 客户端"""
        # 先检测 Steam 是否已安装
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

        # 1. 关闭 Steam
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "steam.exe"],
                capture_output=True,
                timeout=10,
                creationflags=0x08000000,
            )
        except Exception:
            pass

        # 2. 重新启动 Steam
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

    # ---- 重启按钮状态 ----

    def _update_restart_button_state(self):
        """根据 Steam 安装状态启用/禁用重启按钮"""
        steam_path = self._bridge.get_steam_path()
        installed = bool(steam_path and os.path.exists(steam_path))
        self.set_restart_button_enabled(installed)

    def _on_steam_status_changed(self, installed: bool):
        """响应首页 Steam 状态变化"""
        self.set_restart_button_enabled(installed)

    def set_restart_button_enabled(self, enabled: bool):
        """设置重启按钮是否可用"""
        if hasattr(self, "_restart_nav_item"):
            self._restart_nav_item.setEnabled(enabled)

    # ---- 主题通知 ----

    def notify_theme_changed(self):
        pages = [self.home_page, self.inject_page, self.search_page, self.library_page]
        for page in pages:
            if hasattr(page, "notify_theme_changed"):
                page.notify_theme_changed()
            page.update()
            page.repaint()

    # ---- 窗口特效 ----

    def apply_window_effect(self, effect: str):
        if effect == "mica":
            self.setMicaEffectEnabled(True)
        else:
            self.setMicaEffectEnabled(False)

    # ---- 生命周期 ----

    def closeEvent(self, event):
        """窗口关闭时完整清理所有后台线程，防止 QThread 销毁时仍在运行导致崩溃"""
        logger.info("MainWindow closing, cleaning up threads...")
        try:
            self.shutdown()
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
        event.accept()

    def shutdown(self):
        """清理所有页面的后台线程和资源"""
        pages = [self.home_page, self.inject_page, self.search_page, self.library_page]

        # 1. 停止定时器
        for page in pages:
            if hasattr(page, '_auto_refresh_timer') and page._auto_refresh_timer is not None:
                try:
                    page._auto_refresh_timer.stop()
                except Exception:
                    pass

        # 2. 清理 HomePage 的后台 worker（不再使用 ThreadPoolExecutor）
        try:
            if hasattr(self.home_page, '_status_worker') and self.home_page._status_worker:
                self.home_page._status_worker.cancel()
                self.home_page._status_worker.wait(3000)
        except Exception:
            pass

        # 3. 等待所有页面的后台 worker 完成（不强制取消，避免线程销毁错误）
        for page in pages:
            try:
                if hasattr(page, 'wait_for_workers'):
                    page.wait_for_workers()
            except Exception:
                pass

        # 4. LibraryPage 额外清理
        try:
            self.library_page._alive = False
            if hasattr(self.library_page, 'hideEvent'):
                # 触发 hideEvent 中的清理逻辑
                pass  # hideEvent 需要 QHideEvent 参数，这里直接调用关键清理
        except Exception:
            pass

        # 5. 清理 SearchPage 的卡片（递归清理所有子卡片线程）
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

        # 6. 清理 LibraryPage 的卡片
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
