"""
SearchPage — 专业搜索入库页面

项目，特性：
- 清晰的层级布局与留白设计
- 模糊匹配 + 多模式搜索（AppID / 名称 / 推荐）
- 快捷预设热门游戏标签
- 结果卡片带状态标签与批量操作
- 响应式布局，深色/浅色主题自适应
"""
from __future__ import annotations

import re
import urllib.parse

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PyQt6.QtGui import QFont, QPixmap, QIcon

from qfluentwidgets import (
    ScrollArea, SubtitleLabel, CaptionLabel, BodyLabel, TitleLabel,
    PrimaryPushButton, PushButton, SearchLineEdit, ComboBox,
    CardWidget, FlowLayout, FluentIcon, Theme,
    InfoBar, InfoBarPosition, isDarkTheme,
    MessageBox, TransparentPushButton, StateToolTip,
)
from qfluentwidgets.common.style_sheet import setCustomStyleSheet

from core.game_manager import LuaGameManager
from core.metadata_fetcher import MetadataFetcher
from utils.async_worker import AsyncWorker
from utils.logger import setup_logger
from utils.download_cover import CoverCache, download_cover

from config import TEXT_COLOR, STEAM_STORE_API, STEAM_CDN_BASE, STEAM_STORE_SEARCH_RESULTS

_cover_cache = CoverCache.instance()

logger = setup_logger(__name__)


# 设计令牌
_SPACE_XS = 4
_SPACE_SM = 8
_SPACE_MD = 16
_SPACE_LG = 24
_SPACE_XL = 32
_CARD_H = 72
_COVER_W = 120
_COVER_H = 54
_MAX_WIDTH = None  # 不限制最大宽度，自适应窗口

# 热门推荐
_RECOMMENDED: list[tuple[str, str]] = [
    ("730", "Counter-Strike 2"), ("570", "Dota 2"),
    ("440", "Team Fortress 2"), ("1172470", "Apex Legends"),
    ("578080", "PUBG"), ("252490", "Rust"),
    ("1091500", "Cyberpunk 2077"), ("1245620", "Elden Ring"),
    ("292030", "The Witcher 3"), ("1174180", "Red Dead Redemption 2"),
    ("814380", "Sekiro"), ("1086940", "Baldur's Gate 3"),
    ("271590", "GTA V"), ("582010", "Monster Hunter: World"),
    ("1938090", "Call of Duty"), ("1213210", "Monster Hunter Rise"),
    ("2050650", "Palworld"), ("1203220", "Persona 3 Reload"),
    ("1145360", "Hades"), ("367520", "Hollow Knight"),
    ("413150", "Stardew Valley"), ("105600", "Terraria"),
    ("892970", "Valheim"), ("1229490", "Ultrakill"),
    ("1325860", "Sifu"), ("391540", "Undertale"),
    ("1087100", "Deep Rock Galactic"), ("1551360", "Forza Horizon 5"),
    ("553850", "Halo: MCC"), ("1887720", "Octopath Traveler II"),
    ("400", "Portal"), ("620", "Portal 2"),
    ("550", "Left 4 Dead 2"), ("500", "Left 4 Dead"),
    ("220", "Half-Life 2"), ("320", "Half-Life 2: Deathmatch"),
]


class _SearchResultCard(CardWidget):
    """搜索结果卡片 — 紧凑横向布局"""

    add_requested = pyqtSignal(str, str)

    def __init__(self, app_id: str, game_name: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self.game_name = game_name
        self._added = False
        self._cover_worker = None
        self._alive = True  # 安全标志，防止回调到已删除对象

        self.setFixedHeight(_CARD_H)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(_COVER_W, _COVER_H)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setScaledContents(True)
        self.cover_label.setStyleSheet(
            "border-radius: 4px; background-color: #2a2a2a;"
        )
        layout.addWidget(self.cover_label)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = BodyLabel(self.game_name or "未知游戏", self)
        name_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        name_label.setFont(QFont(name_label.font().family(), 14, QFont.Weight.Bold))
        name_label.setWordWrap(True)
        info.addWidget(name_label)

        appid_label = CaptionLabel(f"AppID: {self.app_id}", self)
        appid_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        info.addWidget(appid_label)

        layout.addLayout(info, 1)

        self.add_btn = PrimaryPushButton(FluentIcon.ADD.icon(Theme.DARK), "入库", self)
        self.add_btn.setMinimumWidth(88)
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setCustomStyleSheet(
            self.add_btn,
            f"PushButton {{ color: {TEXT_COLOR}; }}",
            f"PushButton {{ color: {TEXT_COLOR}; }}",
        )
        layout.addWidget(self.add_btn)

    def load_cover_async(self):
        """延迟加载封面（必须在事件循环启动后调用）"""
        if self._cover_worker is not None:
            return
        if _cover_cache.has(self.app_id):
            pix = _cover_cache.get(self.app_id)
            if pix is None:
                return
            if not pix.isNull():
                self.cover_label.setPixmap(pix.scaled(
                    _COVER_W, _COVER_H, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                ))
            return
        self._cover_worker = AsyncWorker(download_cover, self.app_id)
        self._cover_worker.finished_with_result.connect(
            self._on_cover_result, Qt.ConnectionType.QueuedConnection
        )
        self._cover_worker.start()

    def _on_cover_result(self, data: bytes | None):
        if self._cover_worker is not None:
            self._cover_worker.deleteLater()
            self._cover_worker = None
        if not self._alive:
            return
        if data:
            try:
                pix = QPixmap()
                pix.loadFromData(data)
                if not pix.isNull():
                    _cover_cache.set(self.app_id, pix)
                    self.cover_label.setPixmap(pix.scaled(
                        _COVER_W, _COVER_H, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    ))
                    _cover_cache.save_to_disk(self.app_id, data)
                    return
            except Exception as e:
                logger.warning(f"封面渲染失败 AppID={self.app_id}: {e}")
        _cover_cache.set(self.app_id, None)

    def _on_add_clicked(self):
        if not self._added:
            self.add_requested.emit(self.app_id, self.game_name)

    def mark_added(self):
        self._added = True
        self.add_btn.setText("已入库")
        self.add_btn.setIcon(QIcon())
        self.add_btn.setEnabled(False)
        dark = isDarkTheme()
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#2D4A2D' if dark else '#E8F5E9'};
                color: {'#6ECB6E' if dark else '#2E7D32'};
                border: 1px solid {'#3D6A3D' if dark else '#A5D6A7'};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 4px 14px;
            }}
        """)

    def restore_state(self):
        self._added = False
        self.add_btn.setText("入库")
        self.add_btn.setIcon(FluentIcon.ADD.icon(Theme.DARK))
        self.add_btn.setEnabled(True)
        self.add_btn.setStyleSheet("")

    def cleanup(self):
        """安全清理：取消线程、断开信号（不阻塞主线程）"""
        self._alive = False
        if self._cover_worker is not None:
            self._cover_worker.cancel()
            try:
                self._cover_worker.finished_with_result.disconnect(self._on_cover_result)
            except TypeError:
                pass  # 信号可能已被断开
            self._cover_worker = None


class SearchPage(ScrollArea):
    """搜索入库页面 — 专业设计"""

    library_changed = pyqtSignal()

    def __init__(
        self,
        game_manager: LuaGameManager,
        bridge=None,
        parent=None,
    ):
        super().__init__(parent)
        self._game_manager = game_manager
        self._bridge = bridge

        self.setObjectName("searchPage")
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._container.setObjectName("searchContainer")
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(_SPACE_XL, _SPACE_LG, _SPACE_XL, _SPACE_XL)
        self._main_layout.setSpacing(_SPACE_LG)

        self.setWidget(self._container)
        self._cards: list[_SearchResultCard] = []
        self._rec_cards: list[_RecommendCard] = []
        self._active_workers: list[AsyncWorker] = []  # 跟踪活跃 worker，hideEvent 时等待
        self._state_tooltip: StateToolTip | None = None  # 加载动画

        # 分页状态
        self._search_keyword: str = ""
        self._current_page: int = 0
        self._total_count: int = 0
        self._page_size: int = 25

        self._init_ui()

        self.setStyleSheet("QScrollArea#searchPage { border: none; background: transparent; }")
        self._container.setStyleSheet("QWidget#searchContainer { background: transparent; }")

    # ── UI 构建 ──────────────────────────────────────────────

    def _init_ui(self):
        self._build_header()
        self._build_search_bar()
        self._build_results_section()
        self._build_recommendations()

        # 注入状态警告横幅
        self._inject_warning = InfoBar.warning(
            "未注入 Steam",
            "请先在「注入管理」页面完成 Steam 注入与激活，入库功能暂不可用",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=-1,  # 不自动消失
            isClosable=False,
        )
        self._inject_warning.setVisible(False)

        self._main_layout.addStretch()

        # 监听全局注入状态变化
        from core.app_state import app_state
        app_state.injection_changed.connect(self._on_injection_changed)

        # 延迟加载推荐内容（避免构造期间大量网络请求导致崩溃）
        QTimer.singleShot(100, self._show_recommendations)

    def _build_header(self):
        dark = isDarkTheme()
        title = TitleLabel("搜索入库", self)
        title.setTextColor(TEXT_COLOR, TEXT_COLOR)
        title.setFont(QFont(title.font().family(), 22, QFont.Weight.Bold))
        self._main_layout.addWidget(title)

        subtitle = CaptionLabel("输入 AppID 或 英文游戏名 搜索（中文搜索可能不精确）", self)
        subtitle.setWordWrap(True)
        subtitle.setMinimumHeight(36)
        subtitle.setTextColor(TEXT_COLOR, TEXT_COLOR)
        subtitle.setFont(QFont(subtitle.font().family(), 12))
        self._main_layout.addWidget(subtitle)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3A3A3A; border: none;")
        self._main_layout.addWidget(sep)

    def _build_search_bar(self):
        """搜索栏 — 居中、大尺寸"""
        bar = CardWidget(self)
        bar.setObjectName("searchBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(_SPACE_MD, _SPACE_MD, _SPACE_MD, _SPACE_MD)
        bar_layout.setSpacing(_SPACE_MD)

        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("输入 AppID 或游戏名称搜索...")
        self.search_input.setFixedHeight(44)
        self.search_input.setMinimumWidth(300)
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.searchSignal.connect(self._on_search)
        self.search_input.searchButton.setVisible(False)
        bar_layout.addWidget(self.search_input, 1)

        self.search_btn = PrimaryPushButton(FluentIcon.SEARCH.icon(Theme.DARK), "搜索", self)
        self.search_btn.setFixedHeight(44)
        self.search_btn.setMinimumWidth(80)
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setCustomStyleSheet(
            self.search_btn,
            f"PushButton {{ color: {TEXT_COLOR}; }}",
            f"PushButton {{ color: {TEXT_COLOR}; }}",
        )
        bar_layout.addWidget(self.search_btn)

        self._apply_search_bar_theme(bar)

        self._main_layout.addWidget(bar)

    def _apply_search_bar_theme(self, bar: CardWidget):
        dark = isDarkTheme()
        bar.setStyleSheet(f"""
            QWidget#searchBar {{
                background-color: {'#1E1E1E' if dark else '#FFFFFF'};
                border: 1px solid {'#3A3A3A' if dark else '#E0E0E0'};
                border-radius: 10px;
            }}
        """)

    def _build_results_section(self):
        """搜索结果区域"""
        # 结果计数
        self._results_header = QWidget()
        header_layout = QHBoxLayout(self._results_header)
        header_layout.setContentsMargins(0, _SPACE_SM, 0, 0)

        self._results_count = CaptionLabel("", self)
        self._results_count.setStyleSheet("font-size: 13px; font-weight: 600; color: #0078D4;")
        header_layout.addWidget(self._results_count)
        header_layout.addStretch()
        self._results_header.setVisible(False)
        self._main_layout.addWidget(self._results_header)

        # 结果列表
        self._results_layout = QVBoxLayout()
        self._results_layout.setSpacing(_SPACE_SM)
        self._main_layout.addLayout(self._results_layout)

        # 分页导航
        self._pagination_widget = QWidget(self)
        self._pagination_widget.setVisible(False)
        pagination_layout = QHBoxLayout(self._pagination_widget)
        pagination_layout.setContentsMargins(0, _SPACE_MD, 0, 0)
        pagination_layout.setSpacing(_SPACE_MD)
        pagination_layout.addStretch()

        self._prev_btn = PushButton("上一页", self)
        self._prev_btn.setFixedHeight(36)
        self._prev_btn.setMinimumWidth(80)
        self._prev_btn.clicked.connect(self._on_prev_page)
        pagination_layout.addWidget(self._prev_btn)

        self._page_label = CaptionLabel("第 1 页 / 共 1 页", self)
        self._page_label.setStyleSheet("font-size: 13px; color: #AAA; padding: 0 8px;")
        pagination_layout.addWidget(self._page_label)

        self._next_btn = PushButton("下一页", self)
        self._next_btn.setFixedHeight(36)
        self._next_btn.setMinimumWidth(80)
        self._next_btn.clicked.connect(self._on_next_page)
        pagination_layout.addWidget(self._next_btn)

        # 每页条数选择
        self._page_size_combo = ComboBox(self)
        self._page_size_combo.addItems(["25", "50", "100", "200"])
        self._page_size_combo.setCurrentIndex(0)
        self._page_size_combo.setFixedHeight(36)
        self._page_size_combo.setFixedWidth(72)
        self._page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        pagination_layout.addWidget(self._page_size_combo)

        pagination_layout.addStretch()
        self._main_layout.addWidget(self._pagination_widget)

        # 空状态
        self._empty_label = BodyLabel("输入 AppID 或游戏名称开始搜索", self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dark = isDarkTheme()
        self._empty_label.setStyleSheet(
            f"color: {TEXT_COLOR}; padding: 32px 0; font-size: 14px;"
        )
        self._empty_label.setVisible(False)
        self._main_layout.addWidget(self._empty_label)

    def _build_recommendations(self):
        """热门推荐区域"""
        self._rec_header = QWidget()
        rec_title_layout = QHBoxLayout(self._rec_header)
        rec_title_layout.setContentsMargins(0, _SPACE_MD, 0, _SPACE_SM)

        rec_icon = QLabel()
        rec_icon.setPixmap(FluentIcon.GAME.icon().pixmap(20, 20))
        rec_title_layout.addWidget(rec_icon)

        rec_title = SubtitleLabel("热门推荐", self)
        rec_title.setTextColor(TEXT_COLOR, TEXT_COLOR)
        rec_title.setFont(QFont(rec_title.font().family(), 16, QFont.Weight.Bold))
        rec_title_layout.addWidget(rec_title)
        rec_title_layout.addStretch()
        self._main_layout.addWidget(self._rec_header)

        # 推荐卡片网格
        self._rec_layout = FlowLayout()
        self._rec_layout.setSpacing(12)
        self._main_layout.addLayout(self._rec_layout)

    # ── 搜索逻辑 ──────────────────────────────────────────────

    def _on_search(self):
        text = self.search_input.text().strip()
        if not text:
            self._clear_results()
            self._show_recommendations()
            return

        if text.isdigit():
            self._search_by_appid(text)
        else:
            self._search_by_name(text)

    def _search_by_appid(self, app_id: str):
        self._clear_results()
        self._hide_recommendations()
        self._show_loading("正在获取游戏信息...")

        worker = AsyncWorker(_fetch_game_info, app_id)
        worker.finished_with_result.connect(
            lambda data: self._on_appid_result(app_id, data),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished_with_error.connect(
            lambda err: self._on_search_error(app_id, err),
            Qt.ConnectionType.QueuedConnection,
        )
        self._register_worker(worker)
        worker.start()

    def _search_by_name(self, keyword: str):
        self._clear_results()
        self._hide_recommendations()
        self._show_loading_tooltip("正在搜索 Steam 商店...")
        self._search_keyword = keyword
        self._current_page = 0

        worker = AsyncWorker(_search_steam_store, keyword, 0, self._page_size)
        worker.finished_with_result.connect(
            self._on_name_results, Qt.ConnectionType.QueuedConnection
        )
        worker.finished_with_error.connect(
            lambda err: self._on_search_error("", err),
            Qt.ConnectionType.QueuedConnection,
        )
        self._register_worker(worker)
        worker.start()

    def _on_prev_page(self):
        """上一页"""
        if self._current_page <= 0:
            return
        self._load_page(self._current_page - 1)

    def _on_next_page(self):
        """下一页"""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        if self._current_page >= total_pages - 1:
            return
        self._load_page(self._current_page + 1)

    def _on_page_size_changed(self, text: str):
        """每页条数变更 → 重新从第 1 页加载"""
        self._page_size = int(text)
        self._load_page(0)

    def _load_page(self, page: int):
        """加载指定页"""
        self._current_page = page
        # 清除当前卡片
        for card in self._cards:
            card.cleanup()
            self._results_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._pagination_widget.setVisible(False)

        start = page * self._page_size
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)
        self._page_label.setText("加载中...")
        self._show_loading_tooltip("正在搜索 Steam 商店...")

        worker = AsyncWorker(_search_steam_store, self._search_keyword, start, self._page_size)
        worker.finished_with_result.connect(
            self._on_page_results_display, Qt.ConnectionType.QueuedConnection
        )
        worker.finished_with_error.connect(
            lambda err: self._on_search_error("", err),
            Qt.ConnectionType.QueuedConnection,
        )
        self._register_worker(worker)
        worker.start()

    def _on_page_results_display(self, results_and_count: tuple):
        """显示分页结果并更新导航"""
        self._hide_loading_tooltip()
        try:
            results, total_count = results_and_count
            self._total_count = total_count

            for r in results:
                self._add_result_card(r.get("appid", ""), r.get("name", "未知"))

            total_pages = max(1, (total_count + self._page_size - 1) // self._page_size)
            self._show_results_count(total_count)
            self._update_pagination_ui(total_pages)
            self.verticalScrollBar().setValue(0)

            self._stagger_load_covers()
        except Exception as e:
            logger.error(f"Page results display error: {e}")
        finally:
            self._prev_btn.setEnabled(self._current_page > 0)
            self._next_btn.setEnabled(True)

    def _update_pagination_ui(self, total_pages: int):
        """更新分页导航 UI"""
        self._pagination_widget.setVisible(total_pages > 1)
        self._page_label.setText(f"第 {self._current_page + 1} 页 / 共 {total_pages} 页")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total_pages - 1)

    def _show_loading_tooltip(self, text: str):
        """显示加载动画提示"""
        self._hide_loading_tooltip()
        self._state_tooltip = StateToolTip(text, f"请耐心等待...", self.window())
        self._state_tooltip.move(
            self.window().width() // 2 - 100,
            self.window().height() // 2 - 40,
        )

    def _hide_loading_tooltip(self):
        """隐藏加载动画"""
        if self._state_tooltip is not None:
            self._state_tooltip.setState(True)
            self._state_tooltip.deleteLater()
            self._state_tooltip = None

    def _show_loading(self, text: str):
        self._empty_label.setText(f"⏳ {text}")
        self._empty_label.setVisible(True)

    def _on_appid_result(self, app_id: str, data: dict | None):
        try:
            self._empty_label.setVisible(False)
            if data and data.get("success"):
                name = data.get("name", f"AppID {app_id}")
                self._add_result_card(app_id, name)
                self._show_results_count(1)
            else:
                self._empty_label.setText("未找到该 AppID 对应的游戏，请检查 AppID 是否正确")
                self._empty_label.setVisible(True)
        except Exception as e:
            logger.error(f"AppID search callback error: {e}")

    def _on_name_results(self, result_and_count: tuple):
        """首页搜索结果处理"""
        self._hide_loading_tooltip()
        try:
            results, total_count = result_and_count
            self._empty_label.setVisible(False)
            if not results:
                self._empty_label.setText("未找到匹配的游戏，请尝试使用英文名或 AppID 搜索")
                self._empty_label.setVisible(True)
                return

            self._total_count = total_count
            for r in results:
                self._add_result_card(r.get("appid", ""), r.get("name", "未知"))
            self._stagger_load_covers()

            total_pages = max(1, (total_count + self._page_size - 1) // self._page_size)
            self._show_results_count(total_count)
            self._update_pagination_ui(total_pages)

            if results and results[0].get("_cjk_fallback"):
                InfoBar.info(
                    "搜索提示",
                    "Steam API 不支持中文搜索，当前为网页模糊匹配，建议使用英文名或 AppID",
                    parent=self, position=InfoBarPosition.TOP, duration=5000,
                )
        except Exception as e:
            logger.error(f"Name search callback error: {e}")

    def _on_search_error(self, app_id: str, error: str):
        self._hide_loading_tooltip()
        self._empty_label.setVisible(False)
        try:
            InfoBar.error(
                "搜索失败", f"网络请求失败: {error}",
                parent=self, position=InfoBarPosition.TOP,
            )
        except Exception as e:
            logger.error(f"Search error callback error: {e}")

    def _add_result_card(self, app_id: str, name: str):
        # 去重
        for card in self._cards:
            if card.app_id == app_id:
                return

        card = _SearchResultCard(app_id, name, self)

        # 已入库的标记
        if self._game_manager.has_game(app_id):
            card.mark_added()
        elif not self._is_injected():
            card.add_btn.setEnabled(False)

        card.add_requested.connect(self._on_add_game)
        self._cards.append(card)
        self._results_layout.addWidget(card)
        return card

    def _stagger_load_covers(self):
        """异步加载封面：已缓存的立即显示，未缓存的延迟到下一事件循环启动下载"""
        for card in self._cards:
            if _cover_cache.has(card.app_id):
                card.load_cover_async()  # 已缓存 → 立即从内存显示
            else:
                QTimer.singleShot(0, card.load_cover_async)  # 延迟启动，避免阻塞主线程
        self._results_layout.addWidget(card)

    def _show_results_count(self, total: int):
        self._results_count.setText(f"共 {total} 个结果")
        self._results_header.setVisible(True)

    def _hide_recommendations(self):
        """隐藏推荐区域"""
        self._rec_header.setVisible(False)
        for card in self._rec_cards:
            card.cleanup()
            self._rec_layout.removeWidget(card)
            card.deleteLater()
        self._rec_cards.clear()

    def _clear_results(self):
        self._results_header.setVisible(False)
        self._pagination_widget.setVisible(False)
        for card in self._cards:
            card.cleanup()
            self._results_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._empty_label.setVisible(False)
        self._current_page = 0
        self._total_count = 0

    # ── 推荐游戏 ──────────────────────────────────────────────

    def _show_recommendations(self):
        self._rec_header.setVisible(True)
        # 清除旧卡片
        for card in self._rec_cards:
            card.cleanup()
            self._rec_layout.removeWidget(card)
            card.deleteLater()
        self._rec_cards.clear()

        for idx, (appid, name) in enumerate(_RECOMMENDED[:24]):
            card = _RecommendCard(appid, name, self)
            card.add_requested.connect(self._on_add_game)
            if self._game_manager.has_game(appid):
                card.mark_added()
            elif not self._is_injected():
                card.add_btn.setEnabled(False)
            self._rec_cards.append(card)
            self._rec_layout.addWidget(card)
            # 错峰异步加载封面，每张间隔 300ms
            QTimer.singleShot(300 + idx * 300, card.load_cover_async)

    # ── 入库逻辑 ──────────────────────────────────────────────

    def _on_add_game(self, app_id: str, game_name: str):
        if self._game_manager.has_game(app_id):
            InfoBar.warning(
                "已入库", f"AppID {app_id} 已在游戏库中",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        if not self._is_injected():
            InfoBar.warning(
                "未注入", "请先在「注入管理」页面完成 Steam 注入与激活后再入库",
                parent=self, position=InfoBarPosition.TOP, duration=3000,
            )
            return

        # 即时入库（先入库，后台拉元数据）
        self._game_manager.add_game_basic(app_id, game_name)
        self._mark_cards_added(app_id)
        InfoBar.success(
            "入库成功", f"AppID {app_id} {game_name or ''} 已加入游戏库",
            parent=self, position=InfoBarPosition.TOP,
        )
        self.library_changed.emit()

        # 后台异步：获取元数据 → 写 Lua → 下载 Manifest（不阻塞 UI）
        worker = AsyncWorker(self._do_fetch_metadata, app_id, game_name)
        worker.finished_with_result.connect(
            lambda r: self._on_metadata_done(app_id, r), Qt.ConnectionType.QueuedConnection
        )
        self._register_worker(worker)
        worker.start()

    def _mark_cards_added(self, app_id: str):
        for card in self._cards:
            if card.app_id == app_id:
                card.mark_added()
        for card in self._rec_cards:
            if card.app_id == app_id:
                card.mark_added()

    def _do_fetch_metadata(self, app_id: str, game_name: str) -> dict | None:
        """后台线程：获取元数据 → 写 Lua（Manifest 由 DLL 自动下载）"""
        try:
            fetcher = MetadataFetcher()
            metadata = fetcher.fetch_all(app_id)

            if game_name and not metadata.name:
                metadata.name = game_name

            self._game_manager.add_game_with_metadata(metadata)

            logger.info(f"Metadata fetch complete for {app_id} ({metadata.name})")
            return {"depots": len(metadata.depots), "dlcs": len(metadata.dlc_ids)}
        except Exception as e:
            logger.warning(f"Metadata fetch failed for {app_id}: {e}")
            return None

    def _on_metadata_done(self, app_id: str, result: dict | None):
        """后台元数据获取完成（静默处理）"""
        if result:
            logger.info(f"Game {app_id} Lua + Manifest ready: {result}")

    # ── Worker 管理 ──────────────────────────────────────────

    def _on_worker_done(self, worker: AsyncWorker):
        """Worker 完成后从活跃列表移除并清理"""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
            logger.debug(f"Worker done, remaining active: {len(self._active_workers)}")
        worker.deleteLater()

    def _register_worker(self, worker: AsyncWorker):
        """注册 worker：连接清理回调 + 加入活跃列表"""
        worker.finished_with_result.connect(
            lambda _: self._on_worker_done(worker), Qt.ConnectionType.QueuedConnection
        )
        worker.finished_with_error.connect(
            lambda _: self._on_worker_done(worker), Qt.ConnectionType.QueuedConnection
        )
        self._active_workers.append(worker)

    def _cancel_all_workers(self):
        """取消所有活跃 worker 并等待完成"""
        for w in self._active_workers[:]:
            w.cancel()
            w.wait(2000)
            if w.isFinished():
                w.deleteLater()
            if w in self._active_workers:
                self._active_workers.remove(w)
        self._active_workers.clear()

    # ── 生命周期 ──────────────────────────────────────────────

    def hideEvent(self, event):
        super().hideEvent(event)
        self._cancel_all_workers()

    def _refresh_recommendations(self):
        for card in self._rec_cards:
            if self._game_manager.has_game(card.app_id):
                card.mark_added()

    def notify_theme_changed(self):
        self._apply_search_bar_theme(self.findChild(CardWidget, "searchBar"))

    # ── 注入状态管理 ──────────────────────────────────────────

    def _is_injected(self) -> bool:
        """当前 Steam 是否已注入激活"""
        if self._bridge is None:
            return False
        return self._bridge.is_connected()

    def _on_injection_changed(self):
        """全局注入状态变化时更新 UI"""
        injected = self._is_injected()
        self._inject_warning.setVisible(not injected)
        self._update_all_card_buttons()

    def _update_all_card_buttons(self):
        """统一启用/禁用所有卡片的入库按钮"""
        injected = self._is_injected()
        for card in self._cards:
            card.add_btn.setEnabled(injected and not card._added)
        for card in self._rec_cards:
            card.add_btn.setEnabled(injected and not card._added)

    def showEvent(self, event):
        super().showEvent(event)
        self._on_injection_changed()
        self._refresh_recommendations()




# ── 辅助类 ──────────────────────────────────────────────────

class _RecommendCard(CardWidget):
    """推荐游戏卡片 — 紧凑卡片，封面延迟异步加载"""

    add_requested = pyqtSignal(str, str)

    def __init__(self, app_id: str, name: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self.game_name = name
        self._added = False
        self._cover_worker = None
        self._alive = True  # 安全标志

        self.setFixedSize(180, 200)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(8)

        self.cover = QLabel()
        self.cover.setFixedSize(164, 80)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setScaledContents(True)
        self.cover.setStyleSheet(
            "border-radius: 8px; background-color: #2a2a2a;"
        )
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignCenter)

        name_label = BodyLabel(self.game_name, self)
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(36)
        name_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        name_label.setFont(QFont(name_label.font().family(), 12, QFont.Weight.DemiBold))
        layout.addWidget(name_label)

        appid_label = CaptionLabel(f"AppID: {self.app_id}", self)
        appid_label.setTextColor(TEXT_COLOR, TEXT_COLOR)
        appid_label.setFont(QFont(appid_label.font().family(), 11))
        layout.addWidget(appid_label)

        self.add_btn = PrimaryPushButton(FluentIcon.ADD.icon(Theme.DARK), "入库", self)
        self.add_btn.setMinimumWidth(88)
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self._on_add)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setCustomStyleSheet(
            self.add_btn,
            f"PushButton {{ color: {TEXT_COLOR}; }}",
            f"PushButton {{ color: {TEXT_COLOR}; }}",
        )
        layout.addWidget(self.add_btn)

    def load_cover_async(self):
        """延迟加载封面（必须在事件循环启动后调用）"""
        if self._cover_worker is not None:
            return
        if _cover_cache.has(self.app_id):
            pix = _cover_cache.get(self.app_id)
            if pix is None:
                return
            if not pix.isNull():
                self.cover.setPixmap(pix.scaled(164, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            return
        self._cover_worker = AsyncWorker(download_cover, self.app_id)
        self._cover_worker.finished_with_result.connect(
            self._on_cover_result, Qt.ConnectionType.QueuedConnection
        )
        self._cover_worker.start()

    def _on_cover_result(self, data: bytes | None):
        if self._cover_worker is not None:
            self._cover_worker.deleteLater()
            self._cover_worker = None
        if not self._alive:
            return
        if data:
            try:
                pix = QPixmap()
                pix.loadFromData(data)
                if not pix.isNull():
                    _cover_cache.set(self.app_id, pix)
                    self.cover.setPixmap(pix.scaled(164, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    _cover_cache.save_to_disk(self.app_id, data)
                    return
            except Exception as e:
                logger.warning(f"推荐封面渲染失败 AppID={self.app_id}: {e}")
        _cover_cache.set(self.app_id, None)

    def _on_add(self):
        if not self._added:
            self.add_requested.emit(self.app_id, self.game_name)

    def mark_added(self):
        self._added = True
        self.add_btn.setText("已入库")
        self.add_btn.setIcon(QIcon())
        self.add_btn.setEnabled(False)
        dark = isDarkTheme()
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#2D4A2D' if dark else '#E8F5E9'};
                color: {'#6ECB6E' if dark else '#2E7D32'};
                border: 1px solid {'#3D6A3D' if dark else '#A5D6A7'};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 4px 14px;
            }}
        """)

    def restore_state(self):
        self._added = False
        self.add_btn.setText("入库")
        self.add_btn.setIcon(FluentIcon.ADD.icon(Theme.DARK))
        self.add_btn.setEnabled(True)
        self.add_btn.setStyleSheet("")

    def cleanup(self):
        """安全清理：取消线程、断开信号（不阻塞主线程）"""
        self._alive = False
        if self._cover_worker is not None:
            self._cover_worker.cancel()
            try:
                self._cover_worker.finished_with_result.disconnect(self._on_cover_result)
            except TypeError:
                pass  # 信号可能已被断开
            self._cover_worker = None


# ── 后台下载函数（AsyncWorker 线程执行）───────────────────────

def _download_cover(app_id: str) -> bytes | None:
    """下载游戏封面图片（结果会写入 _cover_cache）"""
    from utils.http_client import get_bytes, is_404_cached
    # 先检查内存缓存（由 game_card 模块共享）
    if app_id in _cover_cache:
        return None  # 调用方会根据缓存判断
    url = f"{STEAM_CDN_BASE}/{app_id}/header.jpg"
    # http_client 内部会处理 404 缓存，这里直接请求
    return get_bytes(url, timeout=8.0)


# ── 网络查询函数（后台线程执行）─────────────────────────────

def _fetch_game_info(app_id: str) -> dict | None:
    """通过 Steam Store API 获取单个游戏信息"""
    from utils.http_client import get_json
    data = get_json(
        STEAM_STORE_API,
        params={"appids": app_id, "cc": "us", "l": "zh-CN"},
        timeout=10.0,
    )
    if data and app_id in data and data[app_id].get("success"):
        info = data[app_id]["data"]
        return {
            "success": True,
            "name": info.get("name", ""),
            "type": info.get("type", ""),
            "header_image": info.get("header_image", ""),
        }
    return {"success": False}


_SEARCH_PAGE_SIZE = 25


def _search_steam_store(keyword: str, start: int = 0, count: int = _SEARCH_PAGE_SIZE) -> tuple[list[dict], int]:
    """通过 Steam HTML 搜索游戏，返回 (results, total_count)"""
    try:
        results, total_count = _search_steam_store_html(keyword, start=start, count=count)
        has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', keyword))
        if has_cjk:
            for r in results:
                r["_cjk_fallback"] = True
        return results, total_count
    except Exception as e:
        logger.error(f"Steam search failed: {e}")
        return [], 0


def _search_steam_store_html(keyword: str, start: int = 0, count: int = _SEARCH_PAGE_SIZE) -> tuple[list[dict], int]:
    """HTML 解析 Steam 搜索结果页面，返回 (results, total_count)"""
    from utils.http_client import get_text
    param = urllib.parse.quote(keyword)
    url = f"{STEAM_STORE_SEARCH_RESULTS}?term={param}&start={start}&count={count}"
    html = get_text(url, timeout=10.0)

    if not html:
        return [], 0

    # 解析总结果数
    total_match = re.search(r'(\d[\d,]*)\s+results?\s+match', html)
    total_count = 0
    if total_match:
        total_count = int(total_match.group(1).replace(",", ""))

    # 解析 data-ds-appid 和 title
    row_pattern = re.compile(
        r'data-ds-appid="(\d+)"[^>]*>.*?<span\s+class="title">(.*?)</span>',
        re.DOTALL,
    )
    results: list[dict] = []
    seen: set[str] = set()
    for appid, name in row_pattern.findall(html):
        if appid in seen:
            continue
        seen.add(appid)
        name = name.strip()
        if name:
            results.append({"appid": appid, "name": name})

    if not results:
        logger.info(f"Steam HTML search returned no results for '{keyword}'")
    return results, total_count
