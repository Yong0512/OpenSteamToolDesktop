from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    ScrollArea, SubtitleLabel, CaptionLabel, BodyLabel,
    SearchLineEdit,
    ComboBox, TransparentToolButton,
    InfoBar, InfoBarPosition, FluentIcon,
    ToolTipFilter, ToolTipPosition,
)

from config import STEAM_STORE_API
from core.game_manager import LuaGameManager, GameInfo
from gui.widgets import GameCard
from utils.async_worker import AsyncWorker
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _fetch_game_name(app_id: str) -> tuple[str, str]:
    from utils.http_client import get_json
    url = f"{STEAM_STORE_API}?appids={app_id}&l=zh-CN"
    data = get_json(url, timeout=8.0)
    if data and app_id in data and data[app_id].get("success"):
        name = data[app_id].get("data", {}).get("name", "")
        return (app_id, name)
    return (app_id, "")

class LibraryPage(ScrollArea):

    library_changed = pyqtSignal()

    def __init__(self, game_manager: LuaGameManager, parent=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._sort_mode = "default"
        self._games_data: list[GameInfo] = []
        self._card_list: list[GameCard] = []
        self._alive = True

        self._load_worker = None
        self._name_workers: list[AsyncWorker] = []

        self.setObjectName("libraryPage")
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._container.setObjectName("libraryContainer")
        self.setWidget(self._container)
        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(30, 30, 30, 30)
        self._main_layout.setSpacing(16)

        self._init_ui()

        self.setStyleSheet("LibraryPage { background: transparent; }")
        self._container.setStyleSheet(
            "QWidget#libraryContainer { background: transparent; }"
        )

    def _init_ui(self):

        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("已入库的游戏", self))

        self.stats_label = CaptionLabel("", self)
        self.stats_label.setTextColor("#606060", "#d2d2d2")
        header.addStretch(1)
        header.addWidget(self.stats_label)

        self.refresh_btn = TransparentToolButton(FluentIcon.SYNC, self)
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("刷新")
        self.refresh_btn.installEventFilter(
            ToolTipFilter(self.refresh_btn, showDelay=150, position=ToolTipPosition.TOP)
        )
        self.refresh_btn.clicked.connect(self._load_games_async)
        header.addWidget(self.refresh_btn)

        self._main_layout.addLayout(header)

        toolbar = QHBoxLayout()

        self.filter_input = SearchLineEdit(self)
        self.filter_input.setPlaceholderText("搜索游戏名称或 AppID...")
        self.filter_input.setFixedHeight(35)
        self.filter_input.textChanged.connect(self._on_filter)
        self.filter_input.clearSignal.connect(self._on_filter_clear)
        toolbar.addWidget(self.filter_input, 1)

        self.sort_combo = ComboBox(self)
        self.sort_combo.addItems(["默认", "A-Z", "Z-A"])
        self.sort_combo.setFixedWidth(100)
        self.sort_combo.currentIndexChanged.connect(self._on_sort)
        toolbar.addWidget(self.sort_combo)

        self._main_layout.addLayout(toolbar)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addLayout(self._list_layout)

        self.empty_label = BodyLabel("暂无入库游戏", self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        self._main_layout.addWidget(self.empty_label)

        self._main_layout.addStretch(1)

    def _check_injection_required(self) -> bool:
        from core.app_state import app_state, DLL_ACTIVE
        return bool(app_state.get(DLL_ACTIVE, False))

    def showEvent(self, event):
        super().showEvent(event)
        self._alive = True
        if not self._check_injection_required():
            self._show_not_injected()
        else:
            self._load_games_async()

    def _show_not_injected(self):
        self._clear_list()
        self.refresh_btn.setEnabled(False)
        self.empty_label.setVisible(True)
        self.empty_label.setText("请先在「注入管理」页面完成 Steam 注入与激活")
        self.stats_label.setText("")

    def _load_games_async(self):
        if not self._check_injection_required():
            self._show_not_injected()
            return

        if self._load_worker and not self._load_worker.isFinished():
            self._load_worker.cancel()

        self.refresh_btn.setEnabled(False)
        self.empty_label.setVisible(False)

        self._load_worker = AsyncWorker(self._load_games_sync)
        self._load_worker.finished_with_result.connect(
            self._on_games_loaded, Qt.ConnectionType.QueuedConnection
        )
        self._load_worker.finished_with_error.connect(
            self._on_games_error, Qt.ConnectionType.QueuedConnection
        )
        self._load_worker.start()

    def _load_games_sync(self):
        games = self._game_manager.refresh()
        missing_ids = [g.app_id for g in games if not g.name]
        return {"games": games, "missing_ids": missing_ids}

    def _on_games_loaded(self, result: dict):
        self._load_worker = None
        if not self._alive:
            return
        self._games_data = result["games"]
        self._display_games(self._games_data)
        self.refresh_btn.setEnabled(True)

        missing = result.get("missing_ids", [])
        if missing:
            self._fetch_missing_names(missing)

    def _on_games_error(self, error: str):
        self._load_worker = None
        if not self._alive:
            return
        self.refresh_btn.setEnabled(True)
        InfoBar.error("错误", error, parent=self,
                      position=InfoBarPosition.TOP)

    def _fetch_missing_names(self, app_ids: list[str]):

        for w in self._name_workers[:]:
            try:
                w.finished_with_result.disconnect(self._on_name_fetched)
            except (TypeError, RuntimeError):
                pass
            w.cancel()
        self._name_workers.clear()

        for app_id in app_ids:
            worker = AsyncWorker(_fetch_game_name, app_id)
            worker.finished_with_result.connect(
                self._on_name_fetched, Qt.ConnectionType.QueuedConnection
            )
            worker.finished_with_error.connect(
                lambda err, aid=app_id: logger.warning(f"获取名称失败 AppID={aid}: {err}"),
                Qt.ConnectionType.QueuedConnection
            )
            worker.start()
            self._name_workers.append(worker)

    def _on_name_fetched(self, result: tuple[str, str]):
        if not self._alive:
            return
        try:
            app_id, name = result
            if name:
                for card in self._card_list:
                    if card.app_id == app_id:
                        card.game_name = name
                        card.title_label.setText(name)
                        break
                for g in self._games_data:
                    if g.app_id == app_id:
                        g.name = name
                        break
        except (RuntimeError, Exception) as e:
            logger.warning(f"更新游戏名失败 AppID={result[0]}: {e}")

    def _display_games(self, games: list[GameInfo]):
        self._clear_list()

        if not games:
            self.empty_label.setVisible(True)
            self.stats_label.setText("")
            return

        for idx, game in enumerate(games):
            try:
                card = GameCard(game.app_id, game.name, parent=self)
                card.removed.connect(self._on_remove_game)
                self._list_layout.addWidget(card)
                self._card_list.append(card)

                QTimer.singleShot(100 + idx * 150, card.load_cover_async)
            except Exception as e:
                logger.error(f"创建游戏卡片失败 AppID={game.app_id}: {e}")

        self.stats_label.setText("共 {0} 个游戏".format(len(games)))

        self._apply_current_sort()

    def _clear_list(self):
        for card in self._card_list:
            card.cleanup()
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._card_list.clear()

    def _on_remove_game(self, app_id: str):
        ok = self._game_manager.remove_game(app_id)
        if ok:
            target = None
            for card in self._card_list:
                if card.app_id == app_id:
                    target = card
                    break
            if target:
                self._card_list.remove(target)
                self._list_layout.removeWidget(target)
                target.cleanup()
                target.deleteLater()

            InfoBar.success("出库成功", "游戏已从库中移除",
                            parent=self, position=InfoBarPosition.TOP)

            cnt = len(self._card_list)
            self.stats_label.setText("共 {0} 个游戏".format(cnt) if cnt > 0 else "")
            self.empty_label.setVisible(cnt == 0)

            self.library_changed.emit()
        else:
            InfoBar.error("出库失败", "",
                          parent=self, position=InfoBarPosition.TOP)

    def _on_filter(self, text: str):
        keyword = text.lower().strip()
        if not keyword:
            for card in self._card_list:
                card.setVisible(True)
            self.stats_label.setText("共 {0} 个游戏".format(len(self._card_list)))
            return

        visible = 0
        for card in self._card_list:
            name = getattr(card, "game_name", "").lower()
            app_id = getattr(card, "app_id", "").lower()
            match = keyword in name or keyword in app_id
            card.setVisible(match)
            if match:
                visible += 1

        self.stats_label.setText("共 {0} 个游戏".format(visible))

    def _on_filter_clear(self):
        self._on_filter("")

    def _on_sort(self, index: int):
        mode_map = {0: "default", 1: "az", 2: "za"}
        self._sort_mode = mode_map.get(index, "default")
        self._apply_current_sort()

    def _apply_current_sort(self):
        if self._sort_mode == "default":
            sorted_cards = [
                card for g in self._games_data
                for card in self._card_list
                if card.app_id == g.app_id
            ]
        elif self._sort_mode == "az":
            sorted_cards = sorted(
                self._card_list,
                key=lambda c: getattr(c, "game_name", "").lower()
            )
        elif self._sort_mode == "za":
            sorted_cards = sorted(
                self._card_list,
                key=lambda c: getattr(c, "game_name", "").lower(),
                reverse=True
            )
        else:
            return

        for card in sorted_cards:
            self._list_layout.removeWidget(card)
        for card in sorted_cards:
            self._list_layout.addWidget(card)

    def notify_theme_changed(self):
        for card in self._card_list:
            if hasattr(card, "notify_theme_changed"):
                card.notify_theme_changed()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._alive = False

        for w in self._name_workers[:]:
            try:
                w.finished_with_result.disconnect(self._on_name_fetched)
            except (TypeError, RuntimeError):
                pass
            w.cancel()
            w.wait(2000)
            if w.isFinished():
                w.deleteLater()
            if w in self._name_workers:
                self._name_workers.remove(w)
        self._name_workers.clear()

        if self._load_worker:
            try:
                self._load_worker.finished_with_result.disconnect(self._on_games_loaded)
            except (TypeError, RuntimeError):
                pass
            self._load_worker.cancel()
            self._load_worker.wait(2000)
            self._load_worker = None
