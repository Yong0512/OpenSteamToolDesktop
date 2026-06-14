"""
网络错误弹窗 — 使用 qfluentwidgets 风格
"""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget

from qfluentwidgets import (
    PrimaryPushButton, PushButton, TitleLabel, BodyLabel,
    FluentIcon, isDarkTheme,
)

from config import GITHUB_RELEASES_URL


class NetworkErrorDialog(QDialog):
    """网络连接失败弹窗"""

    # 信号：用户选择退出应用
    exit_requested = pyqtSignal()

    def __init__(self, error_msg: str, parent=None):
        super().__init__(parent)
        self._error_msg = error_msg
        self.setWindowTitle("连接失败")
        self.setFixedSize(480, 310)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.CustomizeWindowHint)
        self.setModal(True)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # 图标 + 标题行
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_bg = QWidget()
        icon_bg.setFixedSize(48, 48)
        icon_bg.setStyleSheet("background-color: #ff9800; border-radius: 24px;")
        icon_inner = QVBoxLayout(icon_bg)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(FluentIcon.WIFI.icon().pixmap(28, 28))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_inner.addWidget(icon_label)
        header.addWidget(icon_bg)

        title = TitleLabel("无法连接到服务器", self)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # 错误信息
        msg = BodyLabel(self._error_msg, self)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        # 建议
        hint = BodyLabel(
            "如果因网络限制无法访问 GitHub，可尝试以下方案：",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(hint)

        layout.addStretch()

        # ── 按钮区（两行布局）────────────────────────────

        # 第一行：主操作 + 退出
        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)

        self.github_btn = PrimaryPushButton(FluentIcon.GITHUB, "前往项目主页", self)
        self.github_btn.setMinimumWidth(160)
        self.github_btn.clicked.connect(self._on_github)

        self.exit_btn = PushButton("退出", self)
        self.exit_btn.setMinimumWidth(80)
        self.exit_btn.clicked.connect(self._on_exit)

        primary_row.addWidget(self.github_btn)
        primary_row.addStretch()
        primary_row.addWidget(self.exit_btn)

        # 第二行：辅助方案（居中）
        helper_row = QHBoxLayout()
        helper_row.setSpacing(12)

        self.watt_btn = PushButton(FluentIcon.DOWNLOAD, "安装 Watt Toolkit", self)
        self.watt_btn.setMinimumWidth(155)
        self.watt_btn.clicked.connect(self._on_watt)

        self.vpn_btn = PushButton(FluentIcon.GLOBE, "科学上网(2元)", self)
        self.vpn_btn.setMinimumWidth(130)
        self.vpn_btn.clicked.connect(self._on_vpn)

        helper_row.addStretch()
        helper_row.addWidget(self.watt_btn)
        helper_row.addWidget(self.vpn_btn)
        helper_row.addStretch()

        layout.addLayout(primary_row)
        layout.addLayout(helper_row)

    def _apply_theme(self):
        dark = isDarkTheme()
        bg = "#2b2b2b" if dark else "#ffffff"
        fg = "#ffffff" if dark else "#000000"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
            }}
        """)

    def _on_github(self):
        webbrowser.open(GITHUB_RELEASES_URL)
        self.reject()

    def _on_watt(self):
        webbrowser.open("ms-windows-store://pdp/?productid=9MTCFHS560NG")
        self.reject()

    def _on_vpn(self):
        webbrowser.open("https://xn--9kqz23b19z.com/#/register?code=fVqOtCnc")
        self.reject()

    def _on_exit(self):
        """用户点击退出，通知主窗口退出应用"""
        self.exit_requested.emit()
        self.reject()
