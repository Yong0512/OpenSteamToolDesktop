"""
EditGameDialog — 编辑游戏元数据的对话框

解析 Lua 文件为 GameMetadata，提供表单编辑界面。
保存时将 GameMetadata 重新生成 Lua 文件。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QGroupBox, QMessageBox,
    QAbstractItemView,
)

from qfluentwidgets import FluentIcon

from core.game_manager import GameMetadata, DepotInfo


class EditGameDialog(QDialog):
    """编辑游戏元数据的对话框"""

    saved = pyqtSignal()  # 保存成功信号，通知父页面刷新

    def __init__(self, game_manager, app_id: str, parent=None):
        super().__init__(parent)
        self._game_manager = game_manager
        self._app_id = app_id
        self._metadata = None

        self.setWindowTitle(f"编辑游戏 - AppID: {app_id}")
        self.setMinimumSize(740, 560)
        self.setModal(True)

        self._init_ui()
        self._load_metadata()

    # ── UI 构建 ──────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 16)
        main_layout.setSpacing(14)

        # ---- 基本信息组 ----
        basic_group = QGroupBox("基本信息", self)
        basic_layout = QFormLayout(basic_group)
        basic_layout.setContentsMargins(16, 16, 16, 16)
        basic_layout.setSpacing(12)

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("输入游戏名称...")
        basic_layout.addRow("游戏名称", self._name_edit)

        self._app_id_label = QLabel(self._app_id, self)
        font = self._app_id_label.font()
        font.setBold(True)
        self._app_id_label.setFont(font)
        basic_layout.addRow("AppID", self._app_id_label)

        self._token_edit = QLineEdit(self)
        self._token_edit.setPlaceholderText("Steam PICS Access Token...")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        basic_layout.addRow("Access Token", self._token_edit)

        self._app_key_edit = QLineEdit(self)
        self._app_key_edit.setPlaceholderText("应用级密钥（可选）...")
        basic_layout.addRow("App-level Key", self._app_key_edit)

        main_layout.addWidget(basic_group)

        # ---- Depots 组 ----
        depots_group = QGroupBox("Depots（仓库）", self)
        depots_layout = QVBoxLayout(depots_group)
        depots_layout.setContentsMargins(16, 16, 16, 16)
        depots_layout.setSpacing(8)

        self._depots_table = QTableWidget(0, 2, self)
        self._depots_table.setHorizontalHeaderLabels(["Depot ID", "Depot Key（解密密钥）"])
        self._depots_table.horizontalHeader().setStretchLastSection(True)
        self._depots_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._depots_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        depots_layout.addWidget(self._depots_table)

        depot_btn_layout = QHBoxLayout()
        add_depot_btn = QPushButton("添加 Depot", self)
        add_depot_btn.clicked.connect(self._add_depot_row)
        remove_depot_btn = QPushButton("删除选中", self)
        remove_depot_btn.clicked.connect(self._remove_depot_row)
        depot_btn_layout.addWidget(add_depot_btn)
        depot_btn_layout.addWidget(remove_depot_btn)
        depot_btn_layout.addStretch()
        depots_layout.addLayout(depot_btn_layout)

        main_layout.addWidget(depots_group)

        # ---- DLCs 组 ----
        dlc_group = QGroupBox("DLCs（下载内容）", self)
        dlc_layout = QVBoxLayout(dlc_group)
        dlc_layout.setContentsMargins(16, 16, 16, 16)
        dlc_layout.setSpacing(8)

        self._dlc_list = QListWidget(self)
        self._dlc_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        dlc_layout.addWidget(self._dlc_list)

        dlc_btn_layout = QHBoxLayout()
        add_dlc_btn = QPushButton("添加 DLC", self)
        add_dlc_btn.clicked.connect(self._add_dlc)
        remove_dlc_btn = QPushButton("删除选中", self)
        remove_dlc_btn.clicked.connect(self._remove_dlc)
        dlc_btn_layout.addWidget(add_dlc_btn)
        dlc_btn_layout.addWidget(remove_dlc_btn)
        dlc_btn_layout.addStretch()
        dlc_layout.addLayout(dlc_btn_layout)

        main_layout.addWidget(dlc_group)

        # ---- 按钮行 ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消", self)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存", self)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    # ── 数据加载 ──────────────────────────────

    def _load_metadata(self):
        """从 Lua 文件加载元数据到表单"""
        self._metadata = self._game_manager.parse_lua_to_metadata(self._app_id)

        if self._metadata is None:
            from utils.logger import setup_logger
            logger = setup_logger(__name__)
            logger.warning(f"Lua 文件解析失败 {self._app_id}，创建空元数据")
            self._metadata = GameMetadata(app_id=self._app_id)

        self._name_edit.setText(self._metadata.name or "")
        self._token_edit.setText(self._metadata.access_token or "")
        self._app_key_edit.setText(self._metadata.app_level_key or "")

        self._depots_table.setRowCount(0)
        for depot in self._metadata.depots:
            row = self._depots_table.rowCount()
            self._depots_table.insertRow(row)
            id_item = QTableWidgetItem(depot.depot_id)
            self._depots_table.setItem(row, 0, id_item)
            key_item = QTableWidgetItem(depot.depot_key or "")
            self._depots_table.setItem(row, 1, key_item)

        self._dlc_list.clear()
        for dlc_id in self._metadata.dlc_ids:
            if dlc_id == self._app_id:
                continue
            self._dlc_list.addItem(dlc_id)

    # ── Depots 操作 ──────────────────────────────

    def _add_depot_row(self):
        row = self._depots_table.rowCount()
        self._depots_table.insertRow(row)
        self._depots_table.setItem(row, 0, QTableWidgetItem(""))
        self._depots_table.setItem(row, 1, QTableWidgetItem(""))
        self._depots_table.scrollToBottom()

    def _remove_depot_row(self):
        selected = self._depots_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self._depots_table.removeRow(row)

    # ── DLCs 操作 ──────────────────────────────

    def _add_dlc(self):
        from PyQt6.QtWidgets import QInputDialog
        dlc_id, ok = QInputDialog.getText(
            self, "添加 DLC", "输入 DLC 的 AppID：", text=""
        )
        if ok and dlc_id.strip().isdigit():
            dlc_id = dlc_id.strip()
            for i in range(self._dlc_list.count()):
                if self._dlc_list.item(i).text() == dlc_id:
                    return
            self._dlc_list.addItem(dlc_id)

    def _remove_dlc(self):
        row = self._dlc_list.currentRow()
        if row >= 0:
            self._dlc_list.takeItem(row)

    # ── 保存 ──────────────────────────────

    def _save(self):
        """收集表单数据，保存到 Lua 文件"""
        if self._metadata is None:
            self._metadata = GameMetadata(app_id=self._app_id)

        self._metadata.name = self._name_edit.text().strip()
        self._metadata.access_token = self._token_edit.text().strip()
        self._metadata.app_level_key = self._app_key_edit.text().strip()

        self._metadata.depots.clear()
        for row in range(self._depots_table.rowCount()):
            id_item = self._depots_table.item(row, 0)
            key_item = self._depots_table.item(row, 1)
            if id_item:
                depot_id = id_item.text().strip()
                if not depot_id:
                    continue
                depot_key = key_item.text().strip() if key_item else ""
                self._metadata.depots.append(
                    DepotInfo(depot_id=depot_id, depot_key=depot_key)
                )

        self._metadata.dlc_ids.clear()
        for i in range(self._dlc_list.count()):
            item = self._dlc_list.item(i)
            if item:
                dlc_id = item.text().strip()
                if dlc_id:
                    self._metadata.dlc_ids.append(dlc_id)

        from utils.logger import setup_logger
        logger = setup_logger(__name__)
        logger.info(f"保存游戏元数据 {self._app_id}...")

        ok = self._game_manager.add_game_with_metadata(self._metadata)

        if ok:
            logger.info(f"游戏 {self._app_id} 保存成功")
            self.saved.emit()
            self.accept()
        else:
            logger.error(f"游戏 {self._app_id} 保存失败")
            QMessageBox.warning(self, "保存失败", "无法写入 Lua 文件，请查看日志")
