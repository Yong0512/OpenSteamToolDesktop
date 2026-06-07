from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox,
)
from qfluentwidgets import (
    ScrollArea, SubtitleLabel, CaptionLabel, BodyLabel,
    PrimaryPushButton, PushButton, CardWidget, InfoBar, InfoBarPosition,
    FluentIcon, LineEdit,
)

from core.config_manager import ConfigManager
from core.steam_bridge import SteamBridge
from core.steam_detector import SteamDetector, SteamStatus
from utils.logger import setup_logger

logger = setup_logger(__name__)

class InjectPage(ScrollArea):

    steam_path_changed = pyqtSignal(str)
    inject_status_changed = pyqtSignal()

    def __init__(
        self,
        bridge: SteamBridge,
        config_manager: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self._bridge = bridge
        self._config = config_manager
        self._detector = SteamDetector()

        self.setObjectName("injectPage")
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._container.setObjectName("injectContainer")
        self.setWidget(self._container)
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(30, 30, 30, 30)
        self._main_layout.setSpacing(24)

        self._init_ui()
        self._load_config()
        self._update_status()

        from core.app_state import app_state
        app_state.injection_changed.connect(self._update_status)

        self.setStyleSheet("InjectPage { background: transparent; }")
        self._container.setStyleSheet(
            "QWidget#injectContainer { background: transparent; }"
        )

    def _init_ui(self):
        self._main_layout.addWidget(SubtitleLabel("注入管理", self))

        self._build_status_card()
        self._build_steam_path_card()
        self._build_inject_actions_card()
        self._build_advanced_card()

        self._main_layout.addStretch(1)

    def _build_status_card(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("当前状态")
        layout.addWidget(header)

        self.steam_status_label = BodyLabel()
        layout.addWidget(self.steam_status_label)

        self.dll_status_label = BodyLabel()
        layout.addWidget(self.dll_status_label)

        self.inject_status_label = BodyLabel()
        layout.addWidget(self.inject_status_label)

        refresh_btn = PushButton(FluentIcon.SYNC, "刷新状态")
        refresh_btn.clicked.connect(self._update_status)
        layout.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._main_layout.addWidget(card)

    def _build_steam_path_card(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("Steam 路径设置")
        layout.addWidget(header)

        path_layout = QHBoxLayout()
        self.steam_path_input = LineEdit()
        self.steam_path_input.setPlaceholderText("Steam 安装目录，留空自动检测")
        path_layout.addWidget(self.steam_path_input)

        detect_btn = PushButton(FluentIcon.SEARCH, "自动检测")
        detect_btn.clicked.connect(self._auto_detect_steam)
        path_layout.addWidget(detect_btn)

        browse_btn = PushButton(FluentIcon.FOLDER, "浏览")
        browse_btn.clicked.connect(self._browse_steam_path)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        hint_label = CaptionLabel("Steam 安装目录，留空自动检测")
        hint_label.setTextColor("#888888", "#888888")
        layout.addWidget(hint_label)

        self._main_layout.addWidget(card)

    def _build_inject_actions_card(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("注入操作")
        layout.addWidget(header)

        inject_layout = QHBoxLayout()
        inject_label = BodyLabel("将 OpenSteamTool 注入到 Steam")
        inject_layout.addWidget(inject_label)
        inject_layout.addStretch()
        self.inject_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "注入 Steam")
        self.inject_btn.clicked.connect(self._on_inject)
        inject_layout.addWidget(self.inject_btn)
        layout.addLayout(inject_layout)

        remove_layout = QHBoxLayout()
        remove_label = BodyLabel("移除 Steam 注入")
        remove_layout.addWidget(remove_label)
        remove_layout.addStretch()
        self.remove_btn = PushButton(FluentIcon.DELETE, "移除注入")
        self.remove_btn.clicked.connect(self._on_remove_inject)
        remove_layout.addWidget(self.remove_btn)
        layout.addLayout(remove_layout)

        verify_layout = QHBoxLayout()
        verify_label = BodyLabel("验证 OpenSteamTool 是否已激活")
        verify_layout.addWidget(verify_label)
        verify_layout.addStretch()
        self.verify_btn = PushButton(FluentIcon.SEARCH, "验证注入")
        self.verify_btn.clicked.connect(self._on_verify_injection)
        verify_layout.addWidget(self.verify_btn)
        layout.addLayout(verify_layout)

        self._main_layout.addWidget(card)

    def _build_advanced_card(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("高级操作")
        layout.addWidget(header)

        steam_ctrl_layout = QHBoxLayout()
        self._steam_ctrl_label = BodyLabel("Steam 客户端")
        steam_ctrl_layout.addWidget(self._steam_ctrl_label)
        steam_ctrl_layout.addStretch()
        self.restart_btn = PushButton(FluentIcon.POWER_BUTTON, "启动 Steam")
        self.restart_btn.clicked.connect(self._on_toggle_steam)
        steam_ctrl_layout.addWidget(self.restart_btn)
        layout.addLayout(steam_ctrl_layout)

        open_dir_layout = QHBoxLayout()
        open_dir_label = BodyLabel("打开 Steam 安装目录")
        open_dir_layout.addWidget(open_dir_label)
        open_dir_layout.addStretch()
        self.open_dir_btn = PushButton(FluentIcon.FOLDER, "打开 Steam 安装目录")
        self.open_dir_btn.clicked.connect(self._on_open_steam_dir)
        open_dir_layout.addWidget(self.open_dir_btn)
        layout.addLayout(open_dir_layout)

        self._main_layout.addWidget(card)

    def _update_status(self):
        from core.app_state import app_state, STEAM_INSTALLED, STEAM_PATH, DLL_DEPLOYED, DLL_ACTIVE

        self._bridge.redetect_steam()
        steam_path = str(app_state.get(STEAM_PATH, ""))
        steam_ok = bool(steam_path and os.path.exists(steam_path))
        dll_deployed = self._bridge.is_deployed()
        dll_active = self._bridge.is_connected()

        app_state.set(STEAM_INSTALLED, steam_ok)
        app_state.set(DLL_DEPLOYED, dll_deployed)
        app_state.set(DLL_ACTIVE, dll_active)

        if steam_ok:
            self.steam_status_label.setText(
                f"✓ Steam 已安装"
            )
            self.steam_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.steam_status_label.setText("✗ Steam 未安装或路径无效")
            self.steam_status_label.setStyleSheet("color: #f5222d;")

        if dll_deployed:
            self.dll_status_label.setText("✓ Steam 已注入")
            self.dll_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.dll_status_label.setText("✗ Steam 未注入")
            self.dll_status_label.setStyleSheet("color: #f5222d;")

        if dll_active:
            self.inject_status_label.setText("✓ OpenSteamTool 已激活")
            self.inject_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.inject_status_label.setText("✗ OpenSteamTool 未激活")
            self.inject_status_label.setStyleSheet("color: #ff9800;")

        self._update_buttons_state()

    def _update_buttons_state(self):
        steam_ok = bool(self._bridge.get_steam_path() and os.path.exists(self._bridge.get_steam_path()))
        dll_deployed = self._bridge.is_deployed()
        steam_running = self._detector.is_steam_running()

        self.inject_btn.setEnabled(steam_ok and not dll_deployed)

        self.remove_btn.setEnabled(dll_deployed)

        self.verify_btn.setEnabled(True)

        self.restart_btn.setEnabled(steam_ok)
        if steam_running:
            self.restart_btn.setText("关闭 Steam")
            self._steam_ctrl_label.setText("关闭 Steam 客户端")
        else:
            self.restart_btn.setText("启动 Steam")
            self._steam_ctrl_label.setText("启动 Steam 客户端")

        self.open_dir_btn.setEnabled(steam_ok)

    def _auto_detect_steam(self):
        from core.app_state import app_state, STEAM_PATH

        app_state.set(STEAM_PATH, "")
        result = self._detector.detect()
        if result.status == SteamStatus.INSTALLED:
            self.steam_path_input.setText(str(result.path))
            self._save_steam_path()
        else:
            InfoBar.warning(
                "检测失败", result.message,
                parent=self, position=InfoBarPosition.TOP,
            )

    def _browse_steam_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择 Steam 安装目录", ""
        )
        if path:
            self.steam_path_input.setText(path)
            self._save_steam_path()

    def _save_steam_path(self):
        path = self.steam_path_input.text()
        if path:
            from core.app_state import app_state, STEAM_PATH
            app_state.set(STEAM_PATH, path)
            self._config.set("steam_path", path)
            self._bridge.redetect_steam()
            self._update_status()
            self.steam_path_changed.emit(path)
            InfoBar.success(
                "保存成功", "Steam 路径已保存",
                parent=self, position=InfoBarPosition.TOP,
            )

    def _load_config(self):
        try:
            from core.app_state import app_state, STEAM_PATH
            steam_path = self._config.get("steam_path", "")
            if steam_path:
                self.steam_path_input.setText(steam_path)
                app_state.set(STEAM_PATH, steam_path)
        except Exception:
            pass

    def _on_inject(self):

        if self._detector.is_steam_running():
            reply = QMessageBox.question(
                self, "Steam 正在运行",
                "Steam 正在运行，注入 Steam 需要先关闭 Steam。\n\n是否要关闭 Steam 并继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:

                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "steam.exe"],
                        capture_output=True, timeout=10,
                        creationflags=0x08000000,
                    )
                    InfoBar.success(
                        "成功", "Steam 已关闭",
                        parent=self, position=InfoBarPosition.TOP,
                    )
                except Exception as e:
                    InfoBar.error(
                        "错误", "关闭 Steam 失败" + str(e),
                        parent=self, position=InfoBarPosition.TOP,
                    )
                    return
            else:
                return

        try:
            success, msg = self._bridge.inject()
            if success:
                InfoBar.success(
                    "成功", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            else:
                InfoBar.error(
                    "错误", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            self._update_status()
            self.inject_status_changed.emit()
        except Exception as e:
            InfoBar.error(
                "错误", str(e),
                parent=self, position=InfoBarPosition.TOP,
            )

    def _on_remove_inject(self):
        reply = QMessageBox.question(
            self, "确认移除",
            "确定要移除注入吗？\n\n这将移除 Steam 目录下的注入文件，并清除所有已入库的游戏。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._detector.is_steam_running():
            reply = QMessageBox.question(
                self, "Steam 正在运行",
                "Steam 正在运行，移除注入需要先关闭 Steam。\n\n是否要关闭 Steam 并继续移除？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:

                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "steam.exe"],
                        capture_output=True, timeout=10,
                        creationflags=0x08000000,
                    )

                    import time
                    time.sleep(3)
                except Exception as e:
                    InfoBar.error(
                        "错误", "关闭 Steam 失败" + str(e),
                        parent=self, position=InfoBarPosition.TOP,
                    )
                    return
            else:
                return

        try:
            success, msg = self._bridge.disconnect()
            if success:
                InfoBar.success(
                    "成功", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            else:
                InfoBar.error(
                    "错误", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            self._update_status()
            self.inject_status_changed.emit()
        except Exception as e:
            InfoBar.error(
                "错误", str(e),
                parent=self, position=InfoBarPosition.TOP,
            )

    def _on_verify_injection(self):
        try:
            active, msg = self._bridge.verify_injection()
            if active:
                InfoBar.success(
                    "验证结果", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            else:
                InfoBar.warning(
                    "验证失败", msg,
                    parent=self, position=InfoBarPosition.TOP,
                )
            self._update_status()
            self.inject_status_changed.emit()
        except Exception as e:
            InfoBar.error(
                "错误", str(e),
                parent=self, position=InfoBarPosition.TOP,
            )

    def _on_toggle_steam(self):
        steam_path = self._bridge.get_steam_path()
        if not steam_path or not os.path.exists(steam_path):
            InfoBar.error(
                "错误", "未检测到 Steam 安装路径",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        steam_exe = os.path.join(steam_path, "steam.exe")
        if not os.path.exists(steam_exe):
            InfoBar.error(
                "错误", "未找到 steam.exe",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        if self._detector.is_steam_running():

            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "steam.exe"],
                    capture_output=True, timeout=10,
                )
                InfoBar.success(
                    "成功", "Steam 已关闭",
                    parent=self, position=InfoBarPosition.TOP,
                )
            except Exception as e:
                InfoBar.error(
                    "错误", f"关闭 Steam 失败: {e}",
                    parent=self, position=InfoBarPosition.TOP,
                )
        else:

            try:
                subprocess.Popen([steam_exe])
                InfoBar.success(
                    "成功", "Steam 已启动",
                    parent=self, position=InfoBarPosition.TOP,
                )
            except Exception as e:
                InfoBar.error(
                    "错误", str(e),
                    parent=self, position=InfoBarPosition.TOP,
                )

        QTimer.singleShot(500, self._update_status)

    def _on_open_steam_dir(self):
        steam_path = self._bridge.get_steam_path()
        if not steam_path or not os.path.exists(steam_path):
            InfoBar.error(
                "错误", "未检测到 Steam 安装路径，请检查 Steam 是否已安装或在设置中手动指定路径。",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        try:
            os.startfile(steam_path)
        except Exception as e:
            InfoBar.error(
                "错误", str(e),
                parent=self, position=InfoBarPosition.TOP,
            )

    def notify_theme_changed(self):
        pass

    def update_text(self):

        if hasattr(self, "_main_layout") and self._main_layout.count() > 0:
            title_widget = self._main_layout.itemAt(0).widget()
            if title_widget:
                title_widget.setText("注入管理")

        if hasattr(self, "inject_btn"):
            self.inject_btn.setText("注入 Steam")
        if hasattr(self, "remove_btn"):
            self.remove_btn.setText("移除注入")
        if hasattr(self, "verify_btn"):
            self.verify_btn.setText("验证注入")
        if hasattr(self, "restart_btn"):

            self.restart_btn.setText("启动/关闭 Steam")
        if hasattr(self, "open_dir_btn"):
            self.open_dir_btn.setText("打开 Steam 安装目录")
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setText("刷新状态")

        self._update_status()
