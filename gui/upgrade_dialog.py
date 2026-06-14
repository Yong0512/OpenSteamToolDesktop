"""
升级对话框 — 检测到新版本时强制提示用户更新

设计特性:
- 模态对话框，不可通过 Esc/关闭按钮退出
- 显示当前版本 vs 最新版本对比
- 可滚动的更新日志区域
- 下载更新 / 退出应用 两个操作
- 深色/浅色主题自适应
"""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QWidget, QSizePolicy,
)

from qfluentwidgets import (
    SubtitleLabel, CaptionLabel, BodyLabel, TitleLabel,
    PrimaryPushButton, PushButton,
    FluentIcon, isDarkTheme, CardWidget,
)

from core.version_checker import ReleaseInfo
from config import APP_NAME, APP_VERSION, GITHUB_RELEASES_URL


class UpgradeDialog(QDialog):
    """强制升级对话框"""

    def __init__(self, release: ReleaseInfo, parent=None):
        super().__init__(parent)
        self._release = release

        self.setWindowTitle("发现新版本")
        self.setFixedSize(540, 580)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        self._apply_theme()

        # 居中显示
        self._center_on_screen()

    def _init_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)

        # ── 顶部图标 + 标题 ──
        header = QHBoxLayout()
        header.setSpacing(14)

        icon_bg = QWidget()
        icon_bg.setFixedSize(48, 48)
        icon_bg.setStyleSheet("background-color: #0078D4; border-radius: 24px;")
        icon_layout = QVBoxLayout(icon_bg)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label = QLabel()
        icon_label.setPixmap(FluentIcon.UPDATE.icon().pixmap(28, 28))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_bg)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        title = TitleLabel("发现新版本", self)
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        title_col.addWidget(title)

        subtitle = CaptionLabel(
            f"请立即更新到最新版本以继续使用 {APP_NAME}", self
        )
        subtitle.setWordWrap(True)
        title_col.addWidget(subtitle)

        header.addLayout(title_col)
        header.addStretch()
        layout.addLayout(header)

        # ── 分隔线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        dark = isDarkTheme()
        sep.setStyleSheet(
            f"background-color: {'#3A3A3A' if dark else '#E0E0E0'}; border: none;"
        )
        layout.addWidget(sep)

        # ── 版本对比卡片 ──
        version_card = CardWidget(self)
        version_card.setObjectName("versionCompareCard")
        version_layout = QHBoxLayout(version_card)
        version_layout.setContentsMargins(20, 16, 20, 16)
        version_layout.setSpacing(0)

        # 当前版本
        current_col = QVBoxLayout()
        current_col.setSpacing(4)
        cur_label = CaptionLabel("当前版本", self)
        cur_label.setStyleSheet(f"color: {'#999' if dark else '#888'};")
        current_col.addWidget(cur_label)

        cur_ver = BodyLabel(f"v{APP_VERSION}", self)
        cur_ver.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {'#999' if dark else '#888'};"
        )
        current_col.addWidget(cur_ver)
        version_layout.addLayout(current_col)

        # 箭头
        arrow_layout = QVBoxLayout()
        arrow_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow = QLabel("→", self)
        arrow.setStyleSheet(
            "font-size: 28px; color: #0078D4; font-weight: bold; padding: 0 24px;"
        )
        arrow_layout.addWidget(arrow)
        version_layout.addLayout(arrow_layout)

        # 最新版本
        latest_col = QVBoxLayout()
        latest_col.setSpacing(4)
        new_label = CaptionLabel("最新版本", self)
        new_label.setStyleSheet("color: #0078D4; font-weight: 600;")
        latest_col.addWidget(new_label)

        new_ver = BodyLabel(f"v{self._release.version}", self)
        new_ver.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #0078D4;"
        )
        latest_col.addWidget(new_ver)
        version_layout.addLayout(latest_col)

        version_layout.addStretch()
        layout.addWidget(version_card)

        # ── 更新日志 ──
        changelog_label = SubtitleLabel("更新内容", self)
        changelog_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(changelog_label)

        changelog = QTextEdit(self)
        changelog.setReadOnly(True)
        changelog.setMinimumHeight(140)
        changelog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 简单 Markdown → 纯文本转换（去掉 ##、** 等标记符号）
        body = self._release.body or "暂无更新说明"
        # 移除 Markdown 标记符号使纯文本可读
        body = body.replace("### ", "■ ").replace("## ", "■ ").replace("# ", "■ ")
        body = body.replace("**", "").replace("`", "")
        changelog.setPlainText(body)
        layout.addWidget(changelog)

        # ── 底部警示 ──
        warning = CaptionLabel(
            "⚠ 更新完成前，应用所有功能将不可用", self
        )
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning.setStyleSheet(
            f"color: {'#FFA500' if dark else '#CC7700'}; font-weight: 600; padding: 4px 0;"
        )
        layout.addWidget(warning)

        # ── 按钮 ──
        layout.addSpacing(4)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # 退出按钮
        exit_btn = PushButton("退出应用", self)
        exit_btn.setFixedHeight(40)
        exit_btn.setMinimumWidth(130)
        exit_btn.clicked.connect(self.reject)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(exit_btn)

        btn_layout.addStretch()

        # 下载按钮（主要操作）
        download_btn = PrimaryPushButton(
            FluentIcon.DOWNLOAD, "立即下载更新", self
        )
        download_btn.setFixedHeight(44)
        download_btn.setMinimumWidth(200)
        download_btn.clicked.connect(self._on_download)
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(download_btn)

        layout.addLayout(btn_layout)

    def _apply_theme(self):
        """主题样式"""
        dark = isDarkTheme()
        bg = "#1E1E1E" if dark else "#FFFFFF"
        border = "#3A3A3A" if dark else "#E0E0E0"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                border-radius: 12px;
            }}
        """)

        version_card_bg = "#2A2A2A" if dark else "#F5F7FA"
        self.findChild(CardWidget, "versionCompareCard").setStyleSheet(f"""
            QWidget#versionCompareCard {{
                background-color: {version_card_bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
        """)

    def _center_on_screen(self):
        """居中到屏幕"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _on_download(self):
        """打开下载页面并关闭应用"""
        webbrowser.open(self._release.html_url or GITHUB_RELEASES_URL)
        self.reject()

    def keyPressEvent(self, event):
        """禁用 Esc 键关闭"""
        if event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """禁用窗口关闭按钮"""
        event.ignore()
