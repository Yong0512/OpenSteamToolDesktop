from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QApplication
from qfluentwidgets import (
    CardWidget, BodyLabel, CaptionLabel,
    TransparentToolButton, FluentIcon, RoundMenu, Action,
    ToolTipFilter, ToolTipPosition, isDarkTheme,
)

from config import TEXT_COLOR
from utils.async_worker import AsyncWorker
from utils.download_cover import CoverCache, download_cover

_cover_cache = CoverCache.instance()
_save_cover_disk = _cover_cache.save_to_disk

class GameCard(CardWidget):

    removed = pyqtSignal(str)

    def __init__(
        self,
        app_id: str,
        game_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.app_id = app_id
        self.game_name = game_name
        self._cover_worker = None
        self._alive = True

        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(80)

        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(15, 12, 15, 12)
        h_layout.setSpacing(15)

        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(120, 56)
        self.cover_label.setScaledContents(True)
        self._theme_cover_bg()
        h_layout.addWidget(self.cover_label)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(4)

        display_name = self.game_name or f"AppID: {self.app_id}"
        self.title_label = BodyLabel(display_name, self)
        self.title_label.setWordWrap(False)
        self.title_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        v_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.info_label = CaptionLabel(f"AppID: {self.app_id}", self)
        self.info_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        v_layout.addWidget(self.info_label, 0, Qt.AlignmentFlag.AlignVCenter)

        v_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_layout.addLayout(v_layout)
        h_layout.addStretch(1)

        self.more_button = TransparentToolButton(FluentIcon.MORE, self)
        self.more_button.setFixedSize(32, 32)
        self.more_button.setToolTip("复制 AppID")
        self.more_button.installEventFilter(
            ToolTipFilter(self.more_button, showDelay=150, position=ToolTipPosition.TOP)
        )
        self.more_button.clicked.connect(self._show_more_menu)
        h_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignRight)

    def load_cover_async(self):
        if self._cover_worker is not None:
            return
        if _cover_cache.has(self.app_id):
            pix = _cover_cache.get(self.app_id)
            if pix is None:
                return
            if not pix.isNull():
                self.cover_label.setPixmap(pix)
            return
        self._cover_worker = AsyncWorker(download_cover, self.app_id)
        self._cover_worker.finished_with_result.connect(
            self._on_cover_result, Qt.ConnectionType.QueuedConnection
        )
        self._cover_worker.start()

    def _on_cover_result(self, data: bytes | None):
        self._cover_worker = None
        if not self._alive:
            return
        if data:
            try:
                pix = QPixmap()
                pix.loadFromData(data)
                if not pix.isNull():
                    _cover_cache.set(self.app_id, pix)
                    self.cover_label.setPixmap(pix)
                    _cover_cache.save_to_disk(self.app_id, data)
                    return
            except Exception:
                pass
        _cover_cache.set(self.app_id, None)

    def cleanup(self):
        self._alive = False
        if self._cover_worker is not None:
            self._cover_worker.cancel()
            self._cover_worker.finished_with_result.disconnect(self._on_cover_result)
            self._cover_worker.wait(3000)
            self._cover_worker = None

    def notify_theme_changed(self):
        self._theme_cover_bg()
        self.update()
        self.repaint()

    def _theme_cover_bg(self):
        if isDarkTheme():
            self.cover_label.setStyleSheet(
                "border-radius: 4px; background: #2a2a2a;"
            )
        else:
            self.cover_label.setStyleSheet(
                "border-radius: 4px; background: #f0f0f0;"
            )

    def _show_more_menu(self):
        menu = RoundMenu(parent=self)

        menu.addAction(Action(FluentIcon.COPY, "复制 AppID", triggered=self._copy_appid))
        menu.addAction(Action(FluentIcon.COPY, "复制游戏名", triggered=self._copy_name))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.LINK, "在 Steam 中查看", triggered=self._open_steam_store))
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.DELETE, "出库", triggered=self._confirm_remove))

        pos = self.more_button.mapToGlobal(
            self.more_button.rect().bottomLeft()
        )
        menu.exec(pos)

    def _copy_appid(self):
        QApplication.clipboard().setText(self.app_id)

    def _copy_name(self):
        QApplication.clipboard().setText(self.game_name or f"AppID: {self.app_id}")

    def _open_steam_store(self):
        webbrowser.open(f"steam://store/{self.app_id}")

    def _confirm_remove(self):
        from qfluentwidgets import MessageBox
        dialog = MessageBox(
            "确认出库",
            "确定要将 AppID {0} 从游戏库中移除吗？\n\n这将删除对应的 Lua 配置文件。".format(self.app_id),
            self.window(),
        )
        if dialog.exec():
            self.removed.emit(self.app_id)
