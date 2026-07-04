from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.cluster_view_config import (
    MAX_FIELDS,
    default_cluster_view_fields,
    load_cluster_view_fields,
    save_cluster_view_fields,
)
from application.index_catalog import IndexCatalog
from .conf import config
from .index_browser_dialog import IndexBrowserDialog


class ClusterCustomMonitorPage(QWidget):
    configurationChanged = pyqtSignal(tuple)

    ENABLED_COLUMN = 0
    LABEL_COLUMN = 1
    INDEX_COLUMN = 2
    HEX_COLUMN = 3
    VALUE_COLUMN = 4
    UNIT_COLUMN = 5
    TYPE_COLUMN = 6
    STATUS_COLUMN = 7

    def __init__(self, index_catalog=None, runtime_config=None, config_path=None, parent=None):
        super().__init__(parent)
        self.runtime_config = runtime_config if runtime_config is not None else config
        self.index_catalog = index_catalog or IndexCatalog.load_default()
        self.config_path = config_path
        self.current_cluster_index = 0
        self.current_address = ""
        self.raw_words = {}
        self._rebuilding = False
        self._index_browser = None
        self._build_ui()
        self.set_fields(load_cluster_view_fields(self.config_path), emit=False)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        heading = QHBoxLayout()
        title = QLabel("自定义索引监控", self)
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        heading.addWidget(self.cluster_label)
        root.addLayout(heading)

        self.hint_label = QLabel(
            "选择固件索引并调整名称、启用状态和顺序；比例、偏移、单位及枚举映射来自索引目录。",
            self,
        )
        self.hint_label.setObjectName("sectionHint")
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.browse_button = QPushButton("浏览索引", self)
        self.add_button = QPushButton("添加行", self)
        self.remove_button = QPushButton("删除", self)
        self.move_up_button = QPushButton("上移", self)
        self.move_down_button = QPushButton("下移", self)
        self.save_button = QPushButton("保存配置", self)
        self.save_button.setObjectName("primaryButton")
        self.restore_button = QPushButton("恢复默认", self)
        for button in (
            self.browse_button,
            self.add_button,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
            self.save_button,
            self.restore_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.count_label = QLabel("0 / 64 项", self)
        self.count_label.setObjectName("sectionHint")
        toolbar.addWidget(self.count_label)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 8, self)
        self.table.setHorizontalHeaderLabels(
            ("启用", "显示名称", "索引", "HEX", "实时值", "单位", "类型", "状态")
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.ENABLED_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.LABEL_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.INDEX_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.HEX_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.VALUE_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.UNIT_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.TYPE_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.STATUS_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("配置尚未修改。", self)
        self.status_label.setObjectName("sectionHint")
        root.addWidget(self.status_label)

        self.table.itemChanged.connect(self._on_item_changed)
        self.browse_button.clicked.connect(self.open_index_browser)
        self.add_button.clicked.connect(self.add_row)
        self.remove_button.clicked.connect(self.remove_selected_row)
        self.move_up_button.clicked.connect(lambda: self.move_selected_row(-1))
        self.move_down_button.clicked.connect(lambda: self.move_selected_row(1))
        self.save_button.clicked.connect(self.save_configuration)
        self.restore_button.clicked.connect(self.restore_defaults)

    @staticmethod
    def _readonly_item(text=""):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    @staticmethod
    def _center(item):
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _append_field(self, field):
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled = self._center(self._readonly_item())
        enabled.setFlags(enabled.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        enabled.setCheckState(
            Qt.CheckState.Checked if bool(field.get("enabled", True)) else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, self.ENABLED_COLUMN, enabled)
        self.table.setItem(row, self.LABEL_COLUMN, QTableWidgetItem(str(field.get("label", ""))))
        self.table.setItem(row, self.INDEX_COLUMN, self._center(QTableWidgetItem(str(field.get("data_id", 0)))))
        for column in (
            self.HEX_COLUMN,
            self.VALUE_COLUMN,
            self.UNIT_COLUMN,
            self.TYPE_COLUMN,
            self.STATUS_COLUMN,
        ):
            self.table.setItem(row, column, self._center(self._readonly_item("--")))
        self._refresh_row(row)

    def set_fields(self, fields, emit=True):
        self._rebuilding = True
        self.table.setRowCount(0)
        for field in list(fields or ())[:MAX_FIELDS]:
            self._append_field(field)
        self._rebuilding = False
        self._update_count()
        self._refresh_all_values()
        if emit:
            self._emit_configuration_changed()

    def fields(self):
        result = []
        for row in range(self.table.rowCount()):
            data_id = self._row_data_id(row)
            if data_id is None:
                continue
            result.append(
                {
                    "data_id": data_id,
                    "label": self.table.item(row, self.LABEL_COLUMN).text().strip(),
                    "enabled": self.table.item(row, self.ENABLED_COLUMN).checkState()
                    == Qt.CheckState.Checked,
                }
            )
        return result

    def request_indexes(self):
        result = []
        seen = set()
        for field in self.fields():
            data_id = int(field["data_id"])
            if field["enabled"] and data_id not in seen:
                result.append(data_id)
                seen.add(data_id)
        return tuple(result)

    def _row_data_id(self, row):
        item = self.table.item(row, self.INDEX_COLUMN)
        try:
            value = int(item.text().strip(), 0)
        except (AttributeError, TypeError, ValueError):
            return None
        return value if 0 <= value <= 0xFFFFFFFF else None

    def _refresh_row(self, row):
        data_id = self._row_data_id(row)
        resolution = self.index_catalog.resolve(data_id, self.runtime_config) if data_id is not None else None
        index_item = self.table.item(row, self.INDEX_COLUMN)
        invalid_color = QColor("#b42318")
        normal_color = QColor("#172b4d")
        index_item.setForeground(normal_color if data_id is not None else invalid_color)

        if resolution is None:
            self.table.item(row, self.HEX_COLUMN).setText("ERR")
            self.table.item(row, self.VALUE_COLUMN).setText("--")
            self.table.item(row, self.UNIT_COLUMN).setText("--")
            self.table.item(row, self.TYPE_COLUMN).setText("--")
            self.table.item(row, self.STATUS_COLUMN).setText("索引无效")
            return

        self.table.item(row, self.HEX_COLUMN).setText(resolution.hex_id)
        self.table.item(row, self.UNIT_COLUMN).setText(
            resolution.display_unit or resolution.unit or "--"
        )
        self.table.item(row, self.TYPE_COLUMN).setText(resolution.type_label)
        label_item = self.table.item(row, self.LABEL_COLUMN)
        if not label_item.text().strip():
            label_item.setText(resolution.short_name if resolution.known else f"索引 {data_id}")
        label_item.setToolTip(
            f"{resolution.symbol}\n{resolution.description}\n来源: {resolution.source_label or '--'}"
        )
        self._refresh_row_value(row, resolution)

    def _refresh_row_value(self, row, resolution=None):
        data_id = self._row_data_id(row)
        if data_id is None:
            return
        resolution = resolution or self.index_catalog.resolve(data_id, self.runtime_config)
        raw_value = self.raw_words.get(data_id)
        if raw_value is None:
            self.table.item(row, self.VALUE_COLUMN).setText("--")
            self.table.item(row, self.STATUS_COLUMN).setText(
                "等待数据" if resolution is not None and resolution.known else "未识别"
            )
            return
        if resolution is None:
            value_text = str(raw_value)
        else:
            value_text = resolution.format_physical_value(raw_value)
        self.table.item(row, self.VALUE_COLUMN).setText(value_text)
        self.table.item(row, self.STATUS_COLUMN).setText("已更新")

    def _refresh_all_values(self):
        self._rebuilding = True
        for row in range(self.table.rowCount()):
            self._refresh_row(row)
        self._rebuilding = False

    def _on_item_changed(self, item):
        if self._rebuilding:
            return
        if item.column() in (self.ENABLED_COLUMN, self.LABEL_COLUMN, self.INDEX_COLUMN):
            self._rebuilding = True
            self._refresh_row(item.row())
            self._rebuilding = False
            self.status_label.setText("配置已修改，点击“保存配置”后下次启动继续使用。")
            self._emit_configuration_changed()

    def _emit_configuration_changed(self):
        self.configurationChanged.emit(self.request_indexes())

    def _update_count(self):
        self.count_label.setText(f"{self.table.rowCount()} / {MAX_FIELDS} 项")

    def add_row(self, data_id=0):
        if self.table.rowCount() >= MAX_FIELDS:
            QMessageBox.information(self, "已达上限", f"最多配置 {MAX_FIELDS} 个索引。")
            return
        self._rebuilding = True
        self._append_field({"data_id": int(data_id), "label": "", "enabled": True})
        self._rebuilding = False
        row = self.table.rowCount() - 1
        self.table.selectRow(row)
        self.table.scrollToItem(self.table.item(row, self.INDEX_COLUMN))
        self._update_count()
        self._emit_configuration_changed()

    def remove_selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self._update_count()
        self.status_label.setText("配置已修改，点击“保存配置”后下次启动继续使用。")
        self._emit_configuration_changed()

    def move_selected_row(self, offset):
        row = self.table.currentRow()
        target = row + int(offset)
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        fields = self.fields()
        fields[row], fields[target] = fields[target], fields[row]
        self.set_fields(fields, emit=True)
        self.table.selectRow(target)
        self.status_label.setText("显示顺序已修改，点击“保存配置”后下次启动继续使用。")

    def open_index_browser(self):
        dialog = IndexBrowserDialog(self.index_catalog, self.runtime_config, parent=self)
        dialog.indexSelected.connect(self._apply_browser_selection)
        dialog.catalogChanged.connect(self._on_catalog_changed)
        row = self.table.currentRow()
        if row >= 0:
            data_id = self._row_data_id(row)
            if data_id is not None:
                dialog.set_initial_query(str(data_id))
        self._index_browser = dialog
        dialog.exec()

    def _apply_browser_selection(self, data_id):
        row = self.table.currentRow()
        if row < 0:
            self.add_row(data_id)
            return
        self.table.item(row, self.INDEX_COLUMN).setText(str(int(data_id)))

    def _on_catalog_changed(self):
        self._refresh_all_values()
        self._emit_configuration_changed()

    def save_configuration(self):
        try:
            normalized = save_cluster_view_fields(self.fields(), self.config_path)
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return False
        self.set_fields(normalized, emit=True)
        self.status_label.setText("配置已保存。")
        return True

    def restore_defaults(self):
        answer = QMessageBox.question(self, "恢复默认", "是否恢复默认索引监控项？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.set_fields(default_cluster_view_fields(), emit=True)
        self.status_label.setText("已恢复默认配置，点击“保存配置”后永久生效。")

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = int(cluster_index or 0)
        self.current_address = str(address or "")
        if self.current_cluster_index <= 0:
            self.cluster_label.setText("当前簇: 00（未编制）")
        else:
            self.cluster_label.setText(
                f"当前簇: 簇{self.current_cluster_index} / 地址 {self.current_address}"
            )

    def set_snapshot(self, raw_words):
        self.raw_words = {
            int(data_id): int(raw_value) & 0xFFFF
            for data_id, raw_value in dict(raw_words or {}).items()
        }
        self._refresh_all_values()

    def update_raw_value(self, data_id, raw_value):
        data_id = int(data_id)
        self.raw_words[data_id] = int(raw_value) & 0xFFFF
        self._rebuilding = True
        for row in range(self.table.rowCount()):
            if self._row_data_id(row) == data_id:
                self._refresh_row_value(row)
        self._rebuilding = False

    def clear_values(self):
        self.raw_words = {}
        self._refresh_all_values()
