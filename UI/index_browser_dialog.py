from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)


class IndexCatalogTableModel(QAbstractTableModel):
    COLUMNS = (
        ("十进制", "data_id"),
        ("HEX", "hex_id"),
        ("名称", "name"),
        ("符号名", "symbol"),
        ("位置", "location"),
        ("类型", "type_label"),
        ("单位", "display_unit"),
        ("权限", "access_label"),
    )

    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self.entries = list(entries or [])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            _title, attribute = self.COLUMNS[index.column()]
            value = getattr(entry, attribute)
            if attribute == "display_unit" and not value:
                value = entry.unit
            return value
        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"{entry.short_name}\n{entry.symbol}\n{entry.description}\n"
                f"{entry.category_label} / {entry.type_label} / {entry.access_label}"
            )
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (0, 1, 5, 6, 7):
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.UserRole:
            return entry
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section][0]
        return section + 1

    def entry_at(self, row):
        if row < 0 or row >= len(self.entries):
            return None
        return self.entries[row]


class IndexCatalogFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self.category = ""
        self.setDynamicSortFilter(True)

    def set_query(self, query):
        self.query = str(query or "").strip().lower()
        self.invalidateFilter()

    def set_category(self, category):
        self.category = str(category or "")
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        entry = model.entry_at(source_row) if model is not None else None
        if entry is None:
            return False
        if self.category and entry.category != self.category:
            return False
        return not self.query or self.query in entry.search_text

    def lessThan(self, left, right):
        left_entry = self.sourceModel().entry_at(left.row())
        right_entry = self.sourceModel().entry_at(right.row())
        if left.column() == 0:
            return left_entry.data_id < right_entry.data_id
        return str(self.sourceModel().data(left) or "") < str(self.sourceModel().data(right) or "")


class IndexBrowserDialog(QDialog):
    indexSelected = pyqtSignal(int)
    catalogChanged = pyqtSignal()

    def __init__(self, index_catalog, runtime_config, parent=None):
        super().__init__(parent)
        self.index_catalog = index_catalog
        self.runtime_config = runtime_config
        self.selected_resolution = None
        self.setWindowTitle("索引浏览器")
        self.setMinimumSize(900, 560)
        self.resize(1180, 720)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("索引浏览器", self)
        title.setObjectName("pageTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.source_label = QLabel(self.index_catalog.source_summary, self)
        self.source_label.setObjectName("sectionHint")
        title_row.addWidget(self.source_label)
        root.addLayout(title_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("搜索中文名称、符号名、十进制或十六进制索引")
        self.search_edit.setClearButtonEnabled(True)
        toolbar.addWidget(self.search_edit, 1)
        self.category_combo = QComboBox(self)
        toolbar.addWidget(self.category_combo)
        self.import_button = QPushButton("导入配置", self)
        self.import_button.setToolTip("导入 JSON 或 YAML 自定义索引配置")
        toolbar.addWidget(self.import_button)
        self.export_button = QPushButton("导出模板", self)
        self.export_button.setToolTip("导出可编辑的自定义索引配置模板")
        toolbar.addWidget(self.export_button)
        self.clear_custom_button = QPushButton("清除自定义", self)
        self.clear_custom_button.setToolTip("停用已导入的自定义索引配置")
        toolbar.addWidget(self.clear_custom_button)
        root.addLayout(toolbar)

        self.table = QTableView(self)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        root.addWidget(self.table, 1)

        self.detail_panel = QFrame(self)
        self.detail_panel.setObjectName("indexDetailPanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 10, 12, 10)
        detail_layout.setSpacing(4)
        self.detail_title = QLabel("请选择一个索引", self.detail_panel)
        self.detail_title.setObjectName("sectionTitle")
        self.detail_meta = QLabel("", self.detail_panel)
        self.detail_meta.setObjectName("sectionHint")
        self.detail_meta.setWordWrap(True)
        self.detail_description = QLabel("", self.detail_panel)
        self.detail_description.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(self.detail_description)
        root.addWidget(self.detail_panel)

        bottom = QHBoxLayout()
        self.result_label = QLabel("", self)
        self.result_label.setObjectName("sectionHint")
        bottom.addWidget(self.result_label)
        bottom.addStretch(1)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.use_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.use_button.setText("填入当前行")
        self.use_button.setObjectName("primaryButton")
        self.use_button.setEnabled(False)
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        bottom.addWidget(self.button_box)
        root.addLayout(bottom)

        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.table.doubleClicked.connect(self._accept_current)
        self.button_box.accepted.connect(self._accept_current)
        self.button_box.rejected.connect(self.reject)
        self.import_button.clicked.connect(self._choose_custom_config)
        self.export_button.clicked.connect(self._choose_template_target)
        self.clear_custom_button.clicked.connect(self._confirm_clear_custom)
        self._reload_models()
        self.search_edit.setFocus()

    def _reload_models(self):
        query = self.search_edit.text() if hasattr(self, "search_edit") else ""
        category = self.category_combo.currentData() if self.category_combo.count() else ""
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("全部分类", "")
        for label, category_value in self.index_catalog.category_options():
            self.category_combo.addItem(label, category_value)
        category_index = self.category_combo.findData(category)
        self.category_combo.setCurrentIndex(max(0, category_index))
        self.category_combo.blockSignals(False)

        entries = self.index_catalog.iter_entries(self.runtime_config)
        self.source_model = IndexCatalogTableModel(entries, self)
        self.proxy_model = IndexCatalogFilterModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self.table.setModel(self.proxy_model)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.proxy_model.set_query(query)
        self.proxy_model.set_category(self.category_combo.currentData())
        self._configure_columns()
        self.source_label.setText(self.index_catalog.source_summary)
        self.clear_custom_button.setEnabled(self.index_catalog.custom_count > 0)
        self.selected_resolution = None
        self.use_button.setEnabled(False)
        self._show_resolution(None)
        self._update_result_count()

    def _configure_columns(self):
        header = self.table.horizontalHeader()
        for column in (0, 1, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

    def set_initial_query(self, query):
        self.search_edit.setText(str(query or ""))
        self.search_edit.selectAll()

    def _on_filter_changed(self, _value=None):
        self.proxy_model.set_query(self.search_edit.text())
        self.proxy_model.set_category(self.category_combo.currentData())
        self.table.clearSelection()
        self.selected_resolution = None
        self.use_button.setEnabled(False)
        self._show_resolution(None)
        self._update_result_count()

    def _update_result_count(self, *args):
        self.result_label.setText(f"匹配 {self.proxy_model.rowCount()} / {self.source_model.rowCount()} 项")

    def _on_selection_changed(self, _selected, _deselected):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.selected_resolution = None
        else:
            source_index = self.proxy_model.mapToSource(indexes[0])
            self.selected_resolution = self.source_model.entry_at(source_index.row())
        self.use_button.setEnabled(self.selected_resolution is not None)
        self._show_resolution(self.selected_resolution)

    def _show_resolution(self, resolution):
        if resolution is None:
            self.detail_title.setText("请选择一个索引")
            self.detail_meta.setText("")
            self.detail_description.setText("")
            return
        self.detail_title.setText(f"{resolution.data_id} / {resolution.hex_id}    {resolution.short_name}")
        custom = "    自定义" if resolution.custom else ""
        self.detail_meta.setText(
            f"{resolution.symbol}    {resolution.category_label}    {resolution.type_label}    "
            f"单位 {resolution.display_unit or resolution.unit or '--'}    {resolution.access_label}{custom}"
        )
        source = f"    来源 {resolution.source_label}" if resolution.source_label else ""
        self.detail_description.setText(f"{resolution.description or '--'}{source}")

    def _accept_current(self, _index=None):
        if self.selected_resolution is None:
            return
        self.indexSelected.emit(self.selected_resolution.data_id)
        self.accept()

    def _choose_custom_config(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入自定义索引配置",
            str(Path.home()),
            "索引配置 (*.yaml *.yml *.json);;所有文件 (*)",
        )
        if path:
            self.import_custom_config(path, show_message=True)

    def import_custom_config(self, path, show_message=False):
        try:
            count = self.index_catalog.import_custom_config(path)
        except Exception as exc:
            if show_message:
                QMessageBox.warning(self, "导入失败", str(exc))
            return False
        self._reload_models()
        self.catalogChanged.emit()
        if show_message:
            QMessageBox.information(self, "导入完成", f"已加载 {count} 项自定义索引配置。")
        return True

    def _choose_template_target(self):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出自定义索引模板",
            str(Path.home() / "index_custom.yaml"),
            "YAML 配置 (*.yaml);;JSON 配置 (*.json)",
        )
        if not path:
            return
        try:
            self.index_catalog.export_custom_template(path)
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出完成", f"模板已保存到：\n{path}")

    def _confirm_clear_custom(self):
        answer = QMessageBox.question(
            self,
            "清除自定义配置",
            "清除后将恢复固件生成的基础索引目录，是否继续？",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_custom_config()

    def clear_custom_config(self):
        self.index_catalog.clear_custom_config()
        self._reload_models()
        self.catalogChanged.emit()
