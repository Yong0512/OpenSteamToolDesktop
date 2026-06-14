"""\nInjectPage — 注入管理页面\n\n提供 Steam 注入、移除注入、设置 Steam 路径等功能\n"""
from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QFileDialog, QMessageBox,
)

from qfluentwidgets import (
    ScrollArea, SubtitleLabel, CaptionLabel, BodyLabel,
    PrimaryPushButton, PushButton, ComboBox, CheckBox,
    CardWidget, GroupHeaderCardWidget, InfoBar, InfoBarPosition,
    FluentIcon, LineEdit,
)

from core.steam_bridge import SteamBridge
from core.steam_detector import SteamDetector, SteamStatus
from core.config_manager import ConfigManager
from core.dll_manager import DLLManager
from utils.logger import setup_logger


logger = setup_logger(__name__)


class InjectPage(ScrollArea):
    """注入管理页面"""

    # 信号
    steam_path_changed = pyqtSignal(str)  # Steam 路径变更信号
    inject_status_changed = pyqtSignal()  # 注入状态变更信号（注入/移除/验证后发射）

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

        # 全局状态变化时自动刷新显示
        from core.app_state import app_state
        app_state.injection_changed.connect(self._update_status)

        self.setStyleSheet("InjectPage { background: transparent; }")
        self._container.setStyleSheet(
            "QWidget#injectContainer { background: transparent; }"
        )

    # ---- UI 构建 ----

    def _init_ui(self):
        self._main_layout.addWidget(SubtitleLabel("注入管理", self))

        self._build_status_card()
        self._build_steam_path_card()
        self._build_inject_actions_card()
        self._build_advanced_card()

        self._main_layout.addStretch(1)

    def _build_status_card(self):
        """构建状态显示卡片"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("当前状态")
        layout.addWidget(header)

        # Steam 状态
        self.steam_status_label = BodyLabel()
        layout.addWidget(self.steam_status_label)

        # Steam 注入状态
        self.dll_status_label = BodyLabel()
        layout.addWidget(self.dll_status_label)

        # 注入激活状态
        self.inject_status_label = BodyLabel()
        layout.addWidget(self.inject_status_label)

        # DLL 版本号（新增）
        self.dll_version_label = BodyLabel()
        layout.addWidget(self.dll_version_label)

        # 刷新按钮
        refresh_btn = PushButton(FluentIcon.SYNC, "刷新状态")
        refresh_btn.clicked.connect(self._update_status)
        layout.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._main_layout.addWidget(card)

    def _build_steam_path_card(self):
        """构建 Steam 路径设置卡片"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("Steam 路径设置")
        layout.addWidget(header)

        # Steam 路径输入
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

        # 提示文本
        hint_label = CaptionLabel("Steam 安装目录，留空自动检测")
        hint_label.setTextColor("#888888", "#888888")
        layout.addWidget(hint_label)

        self._main_layout.addWidget(card)

    def _build_inject_actions_card(self):
        """构建注入操作卡片"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("注入操作")
        layout.addWidget(header)

        # 注入按钮
        inject_layout = QHBoxLayout()
        inject_label = BodyLabel("将 OpenSteamTool 注入到 Steam")
        inject_layout.addWidget(inject_label)
        inject_layout.addStretch()
        self.inject_btn = PrimaryPushButton(FluentIcon.DOWNLOAD, "注入 Steam")
        self.inject_btn.clicked.connect(self._on_inject)
        inject_layout.addWidget(self.inject_btn)
        layout.addLayout(inject_layout)

        # 移除注入按钮
        remove_layout = QHBoxLayout()
        remove_label = BodyLabel("移除 Steam 注入")
        remove_layout.addWidget(remove_label)
        remove_layout.addStretch()
        self.remove_btn = PushButton(FluentIcon.DELETE, "移除注入")
        self.remove_btn.clicked.connect(self._on_remove_inject)
        remove_layout.addWidget(self.remove_btn)
        layout.addLayout(remove_layout)

        # 验证注入按钮
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
        """构建高级操作卡片"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SubtitleLabel("高级操作")
        layout.addWidget(header)

        # 启动/关闭 Steam 按钮
        steam_ctrl_layout = QHBoxLayout()
        self._steam_ctrl_label = BodyLabel("Steam 客户端")
        steam_ctrl_layout.addWidget(self._steam_ctrl_label)
        steam_ctrl_layout.addStretch()
        self.restart_btn = PushButton(FluentIcon.POWER_BUTTON, "启动 Steam")
        self.restart_btn.clicked.connect(self._on_toggle_steam)
        steam_ctrl_layout.addWidget(self.restart_btn)
        layout.addLayout(steam_ctrl_layout)

        # 打开 Steam 目录按钮
        open_dir_layout = QHBoxLayout()
        open_dir_label = BodyLabel("打开 Steam 安装目录")
        open_dir_layout.addWidget(open_dir_label)
        open_dir_layout.addStretch()
        self.open_dir_btn = PushButton(FluentIcon.FOLDER, "打开 Steam 安装目录")
        self.open_dir_btn.clicked.connect(self._on_open_steam_dir)
        open_dir_layout.addWidget(self.open_dir_btn)
        layout.addLayout(open_dir_layout)

        self._main_layout.addWidget(card)

    # ---- 状态更新 ----

    def _update_status(self):
        """更新状态显示并同步到全局 AppState"""
        from core.app_state import app_state, STEAM_INSTALLED, STEAM_PATH, DLL_DEPLOYED, DLL_ACTIVE

        # 重新检测 Steam
        self._bridge.redetect_steam()
        steam_path = str(app_state.get(STEAM_PATH, ""))  # 从全局状态读取
        steam_ok = bool(steam_path and os.path.exists(steam_path))
        dll_deployed = self._bridge.is_deployed()
        dll_active = self._bridge.is_connected()

        # 同步到全局状态（任何观察者自动刷新）
        app_state.set(STEAM_INSTALLED, steam_ok)
        app_state.set(DLL_DEPLOYED, dll_deployed)
        app_state.set(DLL_ACTIVE, dll_active)

        # Steam 状态
        if steam_ok:
            self.steam_status_label.setText(
                f"✓ Steam 已安装"
            )
            self.steam_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.steam_status_label.setText("✗ Steam 未安装或路径无效")
            self.steam_status_label.setStyleSheet("color: #f5222d;")

        # Steam 注入状态
        if dll_deployed:
            self.dll_status_label.setText("✓ Steam 已注入")
            self.dll_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.dll_status_label.setText("✗ Steam 未注入")
            self.dll_status_label.setStyleSheet("color: #f5222d;")

        # 注入激活状态
        if dll_active:
            self.inject_status_label.setText("✓ OpenSteamTool 已激活")
            self.inject_status_label.setStyleSheet("color: #52c41a;")
        else:
            self.inject_status_label.setText("✗ OpenSteamTool 未激活")
            self.inject_status_label.setStyleSheet("color: #ff9800;")

        # DLL 版本号（新增）
        self._update_dll_version_display()

        # 更新按钮状态
        self._update_buttons_state()

    def _update_buttons_state(self):
        """根据状态更新按钮状态"""
        steam_ok = bool(self._bridge.get_steam_path() and os.path.exists(self._bridge.get_steam_path()))
        dll_deployed = self._bridge.is_deployed()
        steam_running = self._detector.is_steam_running()

        # 注入按钮：Steam 已安装且 Steam 未注入时可用
        self.inject_btn.setEnabled(steam_ok and not dll_deployed)

        # 移除注入按钮：Steam 已注入时可用
        self.remove_btn.setEnabled(dll_deployed)

        # 验证注入按钮：总是可用
        self.verify_btn.setEnabled(True)

        # 启动/关闭 Steam 按钮
        self.restart_btn.setEnabled(steam_ok)
        if steam_running:
            self.restart_btn.setText("关闭 Steam")
            self._steam_ctrl_label.setText("关闭 Steam 客户端")
        else:
            self.restart_btn.setText("启动 Steam")
            self._steam_ctrl_label.setText("启动 Steam 客户端")

        # 打开 Steam 目录按钮：Steam 已安装时可用
        self.open_dir_btn.setEnabled(steam_ok)

    # ---- Steam 路径设置 ----

    def _auto_detect_steam(self):
        """自动检测 Steam 路径（强制重新扫描系统，覆盖手动设置）"""
        from core.app_state import app_state, STEAM_PATH
        # 先清除全局缓存，强制 detector 走注册表/文件系统扫描
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
        """浏览选择 Steam 路径"""
        path = QFileDialog.getExistingDirectory(
            self, "选择 Steam 安装目录", ""
        )
        if path:
            self.steam_path_input.setText(path)
            self._save_steam_path()

    def _save_steam_path(self):
        """保存 Steam 路径"""
        path = self.steam_path_input.text()
        if path:
            from core.app_state import app_state, STEAM_PATH
            app_state.set(STEAM_PATH, path)          # 全局同步
            self._config.set("steam_path", path)     # 持久化
            self._bridge.redetect_steam()
            self._update_status()
            self.steam_path_changed.emit(path)
            InfoBar.success(
                "保存成功", "Steam 路径已保存",
                parent=self, position=InfoBarPosition.TOP,
            )

    def _load_config(self):
        """加载配置并同步到全局状态"""
        try:
            from core.app_state import app_state, STEAM_PATH
            steam_path = self._config.get("steam_path", "")
            if steam_path:
                self.steam_path_input.setText(steam_path)
                app_state.set(STEAM_PATH, steam_path)
        except Exception:
            pass

    # ---- 注入操作 ----

    def _on_inject(self):
        """执行注入操作"""
        # 检查 Steam 是否在运行
        if self._detector.is_steam_running():
            reply = QMessageBox.question(
                self, "Steam 正在运行",
                "Steam 正在运行，注入 Steam 需要先关闭 Steam。\n\n是否要关闭 Steam 并继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 关闭 Steam
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

        # 执行注入
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
        """移除注入"""
        reply = QMessageBox.question(
            self, "确认移除",
            "确定要移除注入吗？\n\n这将移除 Steam 目录下的注入文件，并清除所有已入库的游戏。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 检查 Steam 是否在运行
        if self._detector.is_steam_running():
            reply = QMessageBox.question(
                self, "Steam 正在运行",
                "Steam 正在运行，移除注入需要先关闭 Steam。\n\n是否要关闭 Steam 并继续移除？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 关闭 Steam
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "steam.exe"],
                        capture_output=True, timeout=10,
                        creationflags=0x08000000,
                    )
                    # 等待进程退出并释放文件句柄
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

        # 执行移除
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
        """验证注入状态"""
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

    # ---- 高级操作 ----

    def _on_toggle_steam(self):
        """启动或关闭 Steam"""
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
            # 关闭 Steam
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
            # 启动 Steam
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

        # 刷新状态
        QTimer.singleShot(500, self._update_status)

    def _on_open_steam_dir(self):
        """打开 Steam 安装目录"""
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

    # ---- 主题通知 ---

    def _update_dll_version_display(self):
        """更新 DLL 版本号显示"""
        try:
            # 从 bridge 获取 DLLManager
            dll_manager = self._bridge.get_dll_manager()
            if dll_manager:
                current_version = dll_manager.get_current_version()
                dll_path = dll_manager.get_dll_path()
                
                if current_version:
                    self.dll_version_label.setText(f"DLL 版本：{current_version}")
                    self.dll_version_label.setStyleSheet("color: #52c41a;")
                elif dll_path and dll_path.exists():
                    # 有 DLL 目录但无法读取版本信息
                    self.dll_version_label.setText("DLL 版本：未知（未设置当前版本）")
                    self.dll_version_label.setStyleSheet("color: #ff9800;")
                else:
                    self.dll_version_label.setText("DLL 版本：未安装")
                    self.dll_version_label.setStyleSheet("color: #f5222d;")
            else:
                self.dll_version_label.setText("DLL 版本：无法获取（DLLManager 未初始化）")
                self.dll_version_label.setStyleSheet("color: #888888;")
        except Exception as e:
            logger.error(f"更新 DLL 版本显示失败: {e}")
            self.dll_version_label.setText("DLL 版本：获取失败")
            self.dll_version_label.setStyleSheet("color: #f5222d;")

    def notify_theme_changed(self):
        """响应主题变化"""
        pass

    def update_text(self):
        """更新页面文本（语言切换时调用）"""
        # 更新标题
        if hasattr(self, "_main_layout") and self._main_layout.count() > 0:
            title_widget = self._main_layout.itemAt(0).widget()
            if title_widget:
                title_widget.setText("注入管理")

        # 更新按钮文本
        if hasattr(self, "inject_btn"):
            self.inject_btn.setText("注入 Steam")
        if hasattr(self, "remove_btn"):
            self.remove_btn.setText("移除注入")
        if hasattr(self, "verify_btn"):
            self.verify_btn.setText("验证注入")
        if hasattr(self, "restart_btn"):
            # 由 _update_buttons_state 动态设置文字，这里仅设默认值
            self.restart_btn.setText("启动/关闭 Steam")
        if hasattr(self, "open_dir_btn"):
            self.open_dir_btn.setText("打开 Steam 安装目录")
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setText("刷新状态")

        # 更新状态显示
        self._update_status()
