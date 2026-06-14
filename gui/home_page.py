"""
HomePage — 专业向导式首页

设计理念：
1. 水平垂直居中对齐，视觉平衡
2. 清晰的三步向导引导用户完成配置
3. 深色/浅色主题自适应
4. 响应式布局适配不同窗口
"""
from __future__ import annotations

import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, Callable

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy,
)

from qfluentwidgets import (
    SubtitleLabel, CaptionLabel, BodyLabel, TitleLabel,
    PrimaryPushButton, PushButton,
    InfoBar, InfoBarPosition, FluentIcon,
    isDarkTheme, CardWidget, MessageBox, TransparentToolButton,
)
from qfluentwidgets.common.style_sheet import setCustomStyleSheet

from core.steam_bridge import SteamBridge
from core.steam_detector import SteamDetector, SteamStatus
from core.game_manager import LuaGameManager
from config import (
    APP_NAME, APP_VERSION, TEXT_COLOR,
    GITHUB_REPO_URL, GITHUB_ISSUES_URL, STEAM_DOWNLOAD_URL,
)

# ── 常量 ──────────────────────────────────────────────────

# 后台线程池
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="StatusDetect")

# 向导步骤
STEP_INSTALL_STEAM = 0
STEP_DEPLOY_DLL = 1
STEP_ACTIVATE = 2
STEP_ADD_GAMES = 3

# 设计令牌 — 间距系统 (px)
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32
SPACE_XXL = 48

# 设计令牌 — 尺寸
CARD_MAX_WIDTH = 540
CARD_BORDER_RADIUS = 12
BUTTON_HEIGHT = 44
BUTTON_MIN_WIDTH = 220
ICON_SIZE_LG = 96
ICON_SIZE_SM = 20
STEP_CIRCLE_SIZE = 36


from utils.logger import setup_logger
logger = setup_logger(__name__)


def _detect_status(detector: SteamDetector, bridge: SteamBridge, game_manager: LuaGameManager):
    """在后台线程执行状态检测"""
    result = detector.detect()
    steam_ok = result.status == SteamStatus.INSTALLED
    steam_path = result.path if steam_ok else ""

    # 关键修复：检测到 Steam 后，更新 bridge 的 steam_path
    if steam_ok and steam_path:
        bridge._steam_path = steam_path
        bridge._injector.set_steam_path(steam_path)

    steam_running = detector.is_steam_running() if steam_ok else False
    dll_ok = bridge.is_deployed() if steam_ok else False

    if steam_ok:
        active_ok = bridge.is_connected()
        deployed_ok = bridge.is_deployed()
    else:
        active_ok = False
        deployed_ok = False

    game_count = 0
    try:
        game_count = len(game_manager.get_games())
    except Exception:
        pass

    return {
        'steam_installed': steam_ok,
        'steam_running': steam_running,
        'steam_path': steam_path,
        'dll_ok': dll_ok,
        'active_ok': active_ok,
        'deployed_ok': deployed_ok,
        'game_count': game_count,
    }


class _StepIndicator(QWidget):
    """三步进度指示器组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[tuple[QLabel, BodyLabel, QFrame]] = []
        self._current = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        step_names = ["安装 Steam", "注入 Steam", "激活注入", "添加游戏"]
        for i, name in enumerate(step_names):
            # 圆圈
            circle = QLabel(str(i + 1))
            circle.setFixedSize(STEP_CIRCLE_SIZE, STEP_CIRCLE_SIZE)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(circle)
            layout.addSpacing(SPACE_SM)

            # 名称
            label = BodyLabel(name, self)
            layout.addWidget(label)

            if i < len(step_names) - 1:
                layout.addSpacing(SPACE_MD)
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedWidth(40)
                line.setFixedHeight(2)
                layout.addWidget(line)
                layout.addSpacing(SPACE_MD)

            self._steps.append((circle, label, line if i < len(step_names) - 1 else None))

        layout.addStretch()
        self._apply_style()

    def set_current(self, step: int):
        self._current = step
        self._apply_style()

    def _apply_style(self):
        for i, (circle, label, line) in enumerate(self._steps):
            if i < self._current:
                # 已完成
                circle.setStyleSheet(f"""
                    QLabel {{
                        background-color: #0078D4;
                        color: white;
                        border-radius: {STEP_CIRCLE_SIZE // 2}px;
                        font-weight: bold;
                        font-size: 14px;
                    }}
                """)
                label.setStyleSheet("color: #0078D4; font-weight: 600;")
                if line:
                    line.setStyleSheet("background-color: #0078D4;")
            elif i == self._current:
                # 当前步骤
                circle.setStyleSheet(f"""
                    QLabel {{
                        background-color: #0078D4;
                        color: white;
                        border-radius: {STEP_CIRCLE_SIZE // 2}px;
                        font-weight: bold;
                        font-size: 14px;
                        border: 2px solid #0078D4;
                    }}
                """)
                label.setStyleSheet("color: #0078D4; font-weight: 700; font-size: 15px;")
                if line:
                    line.setStyleSheet("background-color: #0078D4;")
            else:
                # 未完成
                circle.setStyleSheet(f"""
                    QLabel {{
                        background-color: #2B2B2B;
                        color: {TEXT_COLOR};
                        border-radius: {STEP_CIRCLE_SIZE // 2}px;
                        font-size: 14px;
                    }}
                """)
                label.setStyleSheet(f"color: {TEXT_COLOR};")
                if line:
                    line.setStyleSheet("background-color: #3A3A3A;")


class HomePage(QScrollArea):
    """向导式首页 — 专业设计"""

    steam_status_changed = pyqtSignal(bool)
    library_need_refresh = pyqtSignal()

    def __init__(
        self,
        bridge: SteamBridge,
        game_manager: LuaGameManager,
        page_switch_callback: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._bridge = bridge
        self._game_manager = game_manager
        self._detector = SteamDetector()
        self._page_switch_callback = page_switch_callback
        self._current_step = STEP_INSTALL_STEAM

        self.setObjectName("homePage")

        # 外层容器
        self._outer = QWidget()
        self._outer.setObjectName("homePageOuter")
        outer_layout = QVBoxLayout(self._outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 内容容器（固定最大宽度，水平居中）
        self._container = QWidget()
        self._container.setObjectName("homePageContainer")
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(SPACE_XL, SPACE_XXL, SPACE_XL, SPACE_XL)
        self._main_layout.setSpacing(SPACE_LG)

        # 包装容器实现水平居中
        wrap = QHBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addStretch()
        wrap.addWidget(self._container)
        wrap.addStretch()
        outer_layout.addLayout(wrap)

        self._init_ui()

        # 样式
        self.setStyleSheet("QScrollArea#homePage { border: none; background: transparent; }")
        self._outer.setStyleSheet("QWidget#homePageOuter { background: transparent; }")
        self._container.setStyleSheet("QWidget#homePageContainer { background: transparent; }")

        # 状态检测
        self._status_future: Optional[Future] = None
        self._status_poll_timer: Optional[QTimer] = None
        self._status: dict = {}

        # 自动刷新定时器（页面可见时每 10 秒刷新状态）
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(10000)
        self._auto_refresh_timer.timeout.connect(self._update_status)

        self.setWidget(self._outer)
        QTimer.singleShot(50, self._update_status)

    def _init_ui(self):
        """构建 UI"""
        self._init_header()
        self._init_progress()
        self._init_content_card()
        self._init_footer()

    def _init_header(self):
        """头部 — 应用名称 + 版本"""
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(FluentIcon.CLOUD_DOWNLOAD.icon().pixmap(36, 36))
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("border-radius: 8px;")
        header.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = TitleLabel(APP_NAME, self)
        title.setTextColor(TEXT_COLOR, TEXT_COLOR)
        title.setFont(QFont(title.font().family(), 20, QFont.Weight.Bold))
        title_col.addWidget(title)

        version = CaptionLabel(f"v{APP_VERSION}", self)
        version.setTextColor(TEXT_COLOR, TEXT_COLOR)
        version.setFont(QFont(version.font().family(), 12))
        title_col.addWidget(version)

        header.addLayout(title_col)
        header.addStretch()
        self._main_layout.addLayout(header)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3A3A3A; border: none;")
        self._main_layout.addWidget(sep)
        self._main_layout.addSpacing(SPACE_SM)

    def _init_progress(self):
        """三步进度指示器"""
        self._progress = _StepIndicator(self)
        self._main_layout.addWidget(self._progress)
        self._main_layout.addSpacing(SPACE_LG)

    def _init_content_card(self):
        """主内容卡片 — 状态图标 + 文本 + 操作按钮"""
        self._card = CardWidget(self)
        self._card.setObjectName("homeContentCard")
        self._card.setMinimumWidth(400)
        self._card.setMaximumWidth(CARD_MAX_WIDTH)
        self._card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(SPACE_XXL, SPACE_XXL, SPACE_XXL, SPACE_XXL)
        card_layout.setSpacing(SPACE_LG)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 状态图标
        self._status_icon = QLabel()
        self._status_icon.setFixedSize(ICON_SIZE_LG, ICON_SIZE_LG)
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._status_icon, 0, Qt.AlignmentFlag.AlignCenter)

        # 状态标题
        self._status_title = SubtitleLabel("", self)
        self._status_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_title.setFont(QFont(self._status_title.font().family(), 20, QFont.Weight.Bold))
        card_layout.addWidget(self._status_title)

        self._status_title.setWordWrap(True)
        self._status_title.setMaximumWidth(CARD_MAX_WIDTH - SPACE_XXL * 2)

        # 状态描述
        self._status_desc = BodyLabel("", self)
        self._status_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_desc.setWordWrap(True)
        self._status_desc.setMinimumHeight(60)
        self._status_desc.setMaximumWidth(CARD_MAX_WIDTH - SPACE_XXL * 2)
        self._status_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card_layout.addWidget(self._status_desc)

        card_layout.addSpacing(SPACE_SM)

        # 主操作按钮
        self._next_btn = PrimaryPushButton("", self)
        self._next_btn.setFixedHeight(BUTTON_HEIGHT)
        self._next_btn.setMinimumWidth(BUTTON_MIN_WIDTH)
        self._next_btn.clicked.connect(self._on_next_step)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setCustomStyleSheet(
            self._next_btn,
            f"PushButton {{ color: {TEXT_COLOR}; }}",
            f"PushButton {{ color: {TEXT_COLOR}; }}",
        )
        card_layout.addWidget(self._next_btn, 0, Qt.AlignmentFlag.AlignCenter)

        # 副操作按钮（查看游戏库，仅在已有游戏时显示）
        self._secondary_btn = PushButton("查看游戏库", self)
        self._secondary_btn.setFixedHeight(36)
        self._secondary_btn.setMinimumWidth(160)
        self._secondary_btn.clicked.connect(self._on_view_library)
        self._secondary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._secondary_btn.setVisible(False)
        setCustomStyleSheet(
            self._secondary_btn,
            f"PushButton {{ color: {TEXT_COLOR}; }}",
            f"PushButton {{ color: {TEXT_COLOR}; }}",
        )
        card_layout.addWidget(self._secondary_btn, 0, Qt.AlignmentFlag.AlignCenter)

        # 应用卡片样式
        self._apply_card_style()

        # 居中包装
        card_wrapper = QHBoxLayout()
        card_wrapper.addStretch()
        card_wrapper.addWidget(self._card)
        card_wrapper.addStretch()
        self._main_layout.addLayout(card_wrapper)
        self._main_layout.addStretch()

    def _apply_card_style(self):
        """为卡片应用样式（固定暗色）"""
        self._card.setStyleSheet(f"""
            QWidget#homeContentCard {{
                background-color: #1E1E1E;
                border: 1px solid #3A3A3A;
                border-radius: {CARD_BORDER_RADIUS}px;
            }}
            QWidget#homeContentCard:hover {{
                border-color: #5A5A5A;
            }}
        """)
        self._status_title.setTextColor(TEXT_COLOR, TEXT_COLOR)
        self._status_desc.setTextColor(TEXT_COLOR, TEXT_COLOR)

    def _init_footer(self):
        """页脚 — 版本信息 + 外部链接"""
        self._main_layout.addSpacing(SPACE_MD)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3A3A3A; border: none;")
        self._main_layout.addWidget(sep)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, SPACE_SM, 0, 0)
        footer.setSpacing(12)

        version = CaptionLabel(f"OpenSteamToolDesktop v{APP_VERSION}", self)
        version.setTextColor(TEXT_COLOR, TEXT_COLOR)
        version.setFont(QFont(version.font().family(), 11))
        footer.addWidget(version)
        footer.addStretch()

        github_btn = TransparentToolButton(FluentIcon.GITHUB, self)
        github_btn.setToolTip("GitHub 仓库")
        github_btn.clicked.connect(lambda: webbrowser.open(GITHUB_REPO_URL))
        footer.addWidget(github_btn)

        report_btn = TransparentToolButton(FluentIcon.FEEDBACK, self)
        report_btn.setToolTip("报告问题")
        report_btn.clicked.connect(lambda: webbrowser.open(GITHUB_ISSUES_URL))
        footer.addWidget(report_btn)

        self._main_layout.addLayout(footer)

    # ── 状态管理 ──────────────────────────────────────────────

    def _update_status(self):
        """异步更新状态"""
        # 如果有旧的定时器，先停止
        if self._status_poll_timer is not None:
            self._status_poll_timer.stop()
            self._status_poll_timer = None
        
        # 提交新的状态检测任务
        self._status_future = _executor.submit(_detect_status, self._detector, self._bridge, self._game_manager)

        self._status_poll_timer = QTimer(self)
        self._status_poll_timer.timeout.connect(self._check_status_done)
        self._status_poll_timer.start(100)

    def refresh_status(self):
        """外部调用的状态刷新接口（由其他页面信号触发）"""
        self._update_status()

    def _check_status_done(self):
        """检查后台检测是否完成"""
        if self._status_future is None or not self._status_future.done():
            return

        if self._status_poll_timer is not None:
            self._status_poll_timer.stop()
            self._status_poll_timer = None

        try:
            result = self._status_future.result()
        except Exception:
            result = {
                'steam_installed': False, 'steam_running': False,
                'steam_path': '', 'dll_ok': False,
                'active_ok': False, 'deployed_ok': False, 'game_count': 0,
            }

        self._status_future = None
        self._status = result
        self._update_wizard_state()

    def _update_wizard_state(self):
        """根据状态确定当前步骤"""
        if not self._status.get('steam_installed', False):
            self._current_step = STEP_INSTALL_STEAM
        elif not self._status.get('dll_ok', False):
            self._current_step = STEP_DEPLOY_DLL
        elif not self._status.get('active_ok', False):
            self._current_step = STEP_ACTIVATE
        else:
            self._current_step = STEP_ADD_GAMES

        self._progress.set_current(self._current_step)
        self._update_content_area()

    # ── 内容区域更新 ──────────────────────────────────────────

    def _update_content_area(self):
        """根据当前步骤更新内容"""
        if self._current_step == STEP_INSTALL_STEAM:
            self._show_step_install_steam()
        elif self._current_step == STEP_DEPLOY_DLL:
            self._show_step_deploy_dll()
        elif self._current_step == STEP_ACTIVATE:
            self._show_step_activate()
        else:
            self._show_step_add_games()

    def _show_step_install_steam(self):
        """步骤 1：安装 Steam"""
        self._status_icon.setPixmap(
            FluentIcon.DOWNLOAD.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
        )
        self._status_title.setText("需要安装 Steam")
        self._status_desc.setText(
            "使用本工具前需要先安装 Steam 客户端。\n"
            "点击下方按钮前往 Steam 官网下载并安装。"
        )
        self._next_btn.setText("下载 Steam")
        self._next_btn.setIcon(FluentIcon.DOWNLOAD.icon())
        self._secondary_btn.setVisible(False)

    def _show_step_deploy_dll(self):
        """步骤 2：注入 Steam"""
        steam_running = self._status.get('steam_running', False)

        if steam_running:
            self._status_icon.setPixmap(
                FluentIcon.WARNING.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
            )
            self._status_title.setText("Steam 正在运行")
            self._status_desc.setText(
                "Steam 正在运行中，注入 Steam 需要先关闭 Steam。\n"
                "点击下方按钮将自动关闭 Steam 并完成注入。"
            )
        else:
            self._status_icon.setPixmap(
                FluentIcon.PLAY.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
            )
            self._status_title.setText("注入 Steam")
            self._status_desc.setText(
                "Steam 已安装，现在需要注入 Steam。\n"
                "点击下方按钮完成注入。"
            )

        self._next_btn.setText("注入 Steam")
        self._next_btn.setIcon(FluentIcon.PLAY.icon())
        self._secondary_btn.setVisible(False)

    def _show_step_activate(self):
        """步骤 3：激活注入（需要启动 Steam）"""
        steam_running = self._status.get('steam_running', False)

        if steam_running:
            self._status_icon.setPixmap(
                FluentIcon.PLAY.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
            )
            self._status_title.setText("等待激活")
            self._status_desc.setText(
                "Steam 正在运行，请稍等片刻...\n"
                "系统将自动检测 OpenSteamTool 是否已激活。"
            )
            self._next_btn.setText("刷新状态")
            self._next_btn.setIcon(FluentIcon.SYNC.icon())
        else:
            self._status_icon.setPixmap(
                FluentIcon.POWER_BUTTON.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
            )
            self._status_title.setText("启动 Steam 激活注入")
            self._status_desc.setText(
                "DLL 已部署完成，现在需要启动 Steam 来激活注入。\n"
                "点击下方按钮启动 Steam，启动后请稍等片刻。"
            )
            self._next_btn.setText("启动 Steam")
            self._next_btn.setIcon(FluentIcon.POWER_BUTTON.icon())

        self._secondary_btn.setVisible(False)

    def _show_step_add_games(self):
        """步骤 4：添加游戏"""
        self._status_icon.setPixmap(
            FluentIcon.SEARCH.icon().pixmap(ICON_SIZE_LG, ICON_SIZE_LG)
        )

        game_count = self._status.get('game_count', 0)
        if game_count > 0:
            self._status_title.setText("继续添加游戏")
            self._status_desc.setText(
                f"游戏库已有 {game_count} 个游戏。"
                "您可以继续添加更多游戏，或查看游戏库。"
            )
            self._secondary_btn.setVisible(True)
        else:
            self._status_title.setText("添加游戏")
            self._status_desc.setText(
                "Steam 已注入成功！现在可以开始添加游戏了。\n"
                "点击下方按钮前往搜索页面添加游戏。"
            )
            self._secondary_btn.setVisible(False)

        self._next_btn.setText("前往搜索入库")
        self._next_btn.setIcon(FluentIcon.SEARCH.icon())

    # ── 按钮事件 ──────────────────────────────────────────────

    def _on_next_step(self):
        """主操作按钮"""
        if self._current_step == STEP_INSTALL_STEAM:
            webbrowser.open(STEAM_DOWNLOAD_URL)
        elif self._current_step == STEP_DEPLOY_DLL:
            self._deploy_dll()
        elif self._current_step == STEP_ACTIVATE:
            self._activate_injection()
        else:
            if self._page_switch_callback is not None:
                self._page_switch_callback("search")

    def _on_view_library(self):
        """查看游戏库"""
        if self._page_switch_callback is not None:
            self._page_switch_callback("library")

    # ── Steam 注入 ──────────────────────────────────────────────

    def _deploy_dll(self):
        """注入 Steam"""
        if self._detector.is_steam_running():
            dialog = MessageBox(
                "Steam 正在运行",
                "Steam 正在运行，注入 Steam 可能需要先关闭 Steam。\n\n是否要关闭 Steam 并继续注入？",
                self,
            )
            dialog.yesButton.setText("关闭 Steam 并继续")
            dialog.cancelButton.setText("取消")

            if not dialog.exec():
                return

            ok, msg = self._detector.kill_steam()
            if not ok:
                InfoBar.error(
                    "错误", f"关闭 Steam 失败: {msg}",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            InfoBar.info(
                "Steam 已关闭", msg,
                parent=self, position=InfoBarPosition.TOP,
            )

        ok, msg = self._bridge.inject()
        if ok:
            InfoBar.success(
                "Steam 注入成功", msg,
                parent=self, position=InfoBarPosition.TOP,
            )
            self._update_status()
        else:
            InfoBar.error(
                "Steam 注入失败", msg,
                parent=self, position=InfoBarPosition.TOP,
            )

    def _activate_injection(self):
        """激活注入（启动 Steam）"""
        steam_running = self._status.get('steam_running', False)

        if steam_running:
            # Steam 正在运行，刷新状态检查是否已激活
            self._update_status()
            InfoBar.info(
                "正在检测", "正在检测 OpenSteamTool 激活状态...",
                parent=self, position=InfoBarPosition.TOP,
            )
        else:
            # 启动 Steam
            steam_path = self._bridge.get_steam_path()
            if not steam_path:
                InfoBar.error(
                    "错误", "未检测到 Steam 安装路径",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            steam_exe = os.path.join(steam_path, "steam.exe")
            if not os.path.exists(steam_exe):
                InfoBar.error(
                    "错误", "未找到 Steam 可执行文件",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            try:
                import subprocess
                subprocess.Popen([steam_exe])
                InfoBar.success(
                    "Steam 启动中", "Steam 正在启动，请稍等片刻...",
                    parent=self, position=InfoBarPosition.TOP,
                )
                # 延迟刷新状态，等待 Steam 启动
                QTimer.singleShot(5000, self._update_status)
            except Exception as e:
                InfoBar.error(
                    "启动失败", f"无法启动 Steam: {e}",
                    parent=self, position=InfoBarPosition.TOP,
                )

    # ── 生命周期 ──────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._update_status()
        self._auto_refresh_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._auto_refresh_timer.stop()

    def notify_theme_changed(self):
        """主题变更时更新样式"""
        self._apply_card_style()
        self._progress._apply_style()

