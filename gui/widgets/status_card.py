from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QSizePolicy
from qfluentwidgets import CardWidget, TitleLabel, CaptionLabel, PushButton

from config import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING


class StatusCard(CardWidget):

    def __init__(
        self,
        title: str,
        status_text: str = "",
        is_active: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._is_active = is_active
        self._status_type: str | None = None
        self._action_callback = None

        self.setMinimumHeight(100)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)
        layout.addStretch()

        self.title_label = CaptionLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        layout.addSpacing(4)

        self.status_label = TitleLabel(status_text)
        self.status_label.setWordWrap(True)
        self._apply_color()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.action_button = PushButton(self)
        self.action_button.setVisible(False)
        self.action_button.setFixedHeight(28)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def update_status(self, text: str, is_active: bool = False, status_type: str | None = None):
        self.status_label.setText(text)
        self._is_active = is_active
        self._status_type = status_type
        self._apply_color()

    def set_action(self, text: str, callback=None):
        self.action_button.setText(text)
        self.action_button.setVisible(True)
        if callback:

            if self._action_callback is not None:
                try:
                    self.action_button.clicked.disconnect(self._action_callback)
                except Exception:
                    pass
            self._action_callback = callback
            self.action_button.clicked.connect(callback)
        else:
            self.clear_action()
        self.adjustSize()

    def clear_action(self):
        if self._action_callback is not None:
            try:
                self.action_button.clicked.disconnect(self._action_callback)
            except Exception:
                pass
            self._action_callback = None
        self.action_button.setVisible(False)

    def _apply_color(self):
        if self._status_type == "success":
            color = COLOR_SUCCESS
        elif self._status_type == "warning":
            color = COLOR_WARNING
        elif self._status_type == "error":
            color = COLOR_ERROR
        else:
            color = COLOR_SUCCESS if self._is_active else COLOR_ERROR

        self.status_label.setStyleSheet(f"color: {color};")

    @property
    def is_active(self) -> bool:
        return self._is_active
