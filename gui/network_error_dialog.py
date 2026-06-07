from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget
from qfluentwidgets import (
    PrimaryPushButton, PushButton, TitleLabel, BodyLabel,
    FluentIcon, isDarkTheme,
)

from config import GITHUB_RELEASES_URL


class NetworkErrorDialog(QDialog):

    def __init__(self, error_msg: str, parent=None):
        super().__init__(parent)
        self._error_msg = error_msg
        self.setWindowTitle("连接失败")
        self.setFixedSize(520, 300)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.CustomizeWindowHint)
        self.setModal(True)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

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

        msg = BodyLabel(self._error_msg, self)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        hint = BodyLabel(
            "如果因网络限制无法访问 GitHub，可以安装 Watt Toolkit 来加速访问。",
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(hint)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.github_btn = PrimaryPushButton(FluentIcon.GITHUB, "前往项目主页", self)
        self.github_btn.setMinimumWidth(165)
        self.github_btn.clicked.connect(self._on_github)

        self.watt_btn = PushButton(FluentIcon.DOWNLOAD, "安装 Watt Toolkit", self)
        self.watt_btn.setMinimumWidth(165)
        self.watt_btn.clicked.connect(self._on_watt)

        self.exit_btn = PushButton("退出", self)
        self.exit_btn.setMinimumWidth(100)
        self.exit_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.github_btn)
        btn_layout.addWidget(self.watt_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.exit_btn)

        layout.addLayout(btn_layout)

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
