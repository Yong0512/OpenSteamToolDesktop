"""
StatusCard — 状态仪表盘卡片组件
从 HomePage 提取，独立复用。
支持 3 种状态类型：success / warning / error
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QSizePolicy
from qfluentwidgets import CardWidget, TitleLabel, CaptionLabel, PushButton

from config import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING


class StatusCard(CardWidget):
    """状态卡片：显示某项系统状态（如 Steam/注入/DLL）

    status_type 优先级高于 is_active：
    - status_type="success" → 绿色
    - status_type="warning" → 橙色
    - status_type="error" → 红色
    - status_type=None → 根据 is_active 布尔值判断（向后兼容）
    卡片自适应宽高，无最大宽度限制。
    """

    def __init__(
        self,
        title: str,
        status_text: str = "",
        is_active: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._is_active = is_active
        self._status_type: str | None = None  # "success" / "warning" / "error" / None
        self._action_callback = None  # 记录当前回调，避免重复 disconnect

        # 自适应：最小尺寸 + Expanding 策略，不限制最大宽度
        self.setMinimumHeight(100)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)
        layout.addStretch()

        # 标题
        self.title_label = CaptionLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        layout.addSpacing(4)

        # 状态文本
        self.status_label = TitleLabel(status_text)
        self.status_label.setWordWrap(True)
        self._apply_color()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 操作按钮（可选，默认隐藏）
        self.action_button = PushButton(self)
        self.action_button.setVisible(False)
        self.action_button.setFixedHeight(28)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def update_status(self, text: str, is_active: bool = False, status_type: str | None = None):
        """更新状态显示

        Args:
            text: 状态文本
            is_active: 是否为正常状态（绿色/红色），当 status_type 为 None 时生效
            status_type: 状态类型，优先级高于 is_active
                - "success" → 绿色
                - "warning" → 橙色
                - "error" → 红色
                - None → 根据 is_active 判断（向后兼容）
        """
        self.status_label.setText(text)
        self._is_active = is_active
        self._status_type = status_type
        self._apply_color()

    def set_action(self, text: str, callback=None):
        """设置操作按钮（如"下载 Steam"）"""
        self.action_button.setText(text)
        self.action_button.setVisible(True)
        if callback:
            # 精确断开旧回调（避免无连接时 disconnect 警告）
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
        """隐藏操作按钮"""
        if self._action_callback is not None:
            try:
                self.action_button.clicked.disconnect(self._action_callback)
            except Exception:
                pass
            self._action_callback = None
        self.action_button.setVisible(False)

    def _apply_color(self):
        """根据状态类型应用颜色"""
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
