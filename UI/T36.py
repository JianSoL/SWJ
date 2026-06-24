from pathlib import Path
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.dbc_parser import parse_dbc_file


class DbcParsePage(QWidget):
    def __init__(self):
        super().__init__()
        self.database = None
        self.default_dbc_path = self._default_dbc_path()
        self._build_ui()
        if self.default_dbc_path is not None:
            self.file_path_edit.setText(str(self.default_dbc_path))
            self.parse_current_file(show_success=False)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("DBC解析", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("请选择DBC文件")
        toolbar.addWidget(self.file_path_edit, 1)

        self.import_button = QPushButton("导入DBC", self)
        self.import_button.setObjectName("primaryButton")
        self.import_button.clicked.connect(self.choose_dbc_file)
        toolbar.addWidget(self.import_button)

        self.default_button = QPushButton("默认DBC", self)
        self.default_button.clicked.connect(self.load_default_dbc)
        self.default_button.setEnabled(self.default_dbc_path is not None)
        toolbar.addWidget(self.default_button)

        self.parse_button = QPushButton("重新解析", self)
        self.parse_button.clicked.connect(self.parse_current_file)
        toolbar.addWidget(self.parse_button)
        root.addLayout(toolbar)

        summary_group = QGroupBox("解析概览", self)
        summary_layout = QGridLayout(summary_group)
        summary_layout.setContentsMargins(12, 18, 12, 12)
        summary_layout.setHorizontalSpacing(10)
        summary_layout.setVerticalSpacing(8)
        self.summary_labels = {}
        for index, (key, label_text) in enumerate(
            (
                ("message_count", "报文数"),
                ("signal_count", "信号数"),
                ("node_count", "节点数"),
                ("encoding", "编码"),
                ("nodes", "节点"),
                ("warnings", "提示"),
            )
        ):
            row = index // 3
            column = (index % 3) * 2
            caption = QLabel(label_text, summary_group)
            caption.setObjectName("metricLabel")
            value = QLabel("--", summary_group)
            value.setObjectName("sectionHint")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            summary_layout.addWidget(caption, row, column)
            summary_layout.addWidget(value, row, column + 1)
            self.summary_labels[key] = value
        root.addWidget(summary_group)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.addWidget(QLabel("报文筛选", self))
        self.message_filter_edit = QLineEdit(self)
        self.message_filter_edit.setPlaceholderText("ID / 名称 / 发送节点")
        self.message_filter_edit.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.message_filter_edit, 1)
        filter_layout.addWidget(QLabel("信号筛选", self))
        self.signal_filter_edit = QLineEdit(self)
        self.signal_filter_edit.setPlaceholderText("信号名 / 单位 / 接收节点 / 注释")
        self.signal_filter_edit.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.signal_filter_edit, 1)
        self.follow_message_checkbox = QCheckBox("跟随选中报文", self)
        self.follow_message_checkbox.setChecked(True)
        self.follow_message_checkbox.toggled.connect(self.apply_filters)
        filter_layout.addWidget(self.follow_message_checkbox)
        root.addLayout(filter_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_message_group())
        splitter.addWidget(self._build_signal_group())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("请选择DBC文件。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _build_message_group(self):
        group = QGroupBox("报文列表", self)
        layout = QVBoxLayout(group)
        self.message_table = QTableWidget(group)
        self.message_table.setColumnCount(6)
        self.message_table.setHorizontalHeaderLabels(["ID(HEX)", "ID(DEC)", "报文名", "DLC", "发送节点", "信号数"])
        self.message_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.message_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.message_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.message_table.verticalHeader().setVisible(False)
        self.message_table.setAlternatingRowColors(True)
        self.message_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.message_table.horizontalHeader().setStretchLastSection(True)
        self.message_table.itemSelectionChanged.connect(self.on_message_selection_changed)
        layout.addWidget(self.message_table)
        return group

    def _build_signal_group(self):
        group = QGroupBox("信号列表", self)
        layout = QVBoxLayout(group)
        self.signal_table = QTableWidget(group)
        self.signal_table.setColumnCount(15)
        self.signal_table.setHorizontalHeaderLabels(
            [
                "报文",
                "ID",
                "信号名",
                "起始位",
                "长度",
                "字节序",
                "符号",
                "系数",
                "偏移",
                "最小",
                "最大",
                "单位",
                "接收节点",
                "枚举",
                "注释",
            ]
        )
        self.signal_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.signal_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.signal_table.verticalHeader().setVisible(False)
        self.signal_table.setAlternatingRowColors(True)
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.signal_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.signal_table)
        return group

    def _default_dbc_path(self):
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "IDC.dbc")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "IDC.dbc")
        candidates.append(Path.cwd() / "IDC.dbc")
        candidates.append(Path(__file__).resolve().parents[1] / "IDC.dbc")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def choose_dbc_file(self):
        current_path = Path(self.file_path_edit.text()) if self.file_path_edit.text() else self.default_dbc_path
        start_dir = str(current_path.parent if current_path else Path.cwd())
        file_name, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择DBC文件",
            start_dir,
            "DBC Files (*.dbc);;All Files (*)",
        )
        if file_name:
            self.file_path_edit.setText(file_name)
            self.parse_current_file()

    def load_default_dbc(self):
        if self.default_dbc_path is None:
            self.set_status("未找到默认 IDC.dbc。", failed=True)
            return
        self.file_path_edit.setText(str(self.default_dbc_path))
        self.parse_current_file()

    def parse_current_file(self, show_success=True):
        path_text = self.file_path_edit.text().strip()
        if not path_text:
            self.set_status("请选择DBC文件。", failed=True)
            return
        try:
            self.database = parse_dbc_file(path_text)
        except Exception as exc:
            self.database = None
            self._clear_tables()
            self._update_summary()
            self.set_status(f"DBC解析失败: {exc}", failed=True)
            return

        self.populate_tables()
        self._update_summary()
        if show_success:
            self.set_status(f"DBC解析完成: {Path(path_text).name}")
        else:
            self.set_status(f"已加载默认DBC: {Path(path_text).name}")

    def populate_tables(self):
        self.message_table.setSortingEnabled(False)
        self.signal_table.setSortingEnabled(False)
        self.message_table.setRowCount(0)
        self.signal_table.setRowCount(0)
        if self.database is None:
            return

        self.message_table.setRowCount(len(self.database.messages))
        signal_rows = []
        for row, message in enumerate(self.database.messages):
            values = [
                message.frame_id_hex,
                message.frame_id,
                message.name,
                message.dlc,
                message.transmitter,
                len(message.signals),
            ]
            for column, value in enumerate(values):
                item = self._table_item(value)
                item.setData(Qt.ItemDataRole.UserRole, message.frame_id)
                self.message_table.setItem(row, column, item)
            for signal in message.signals:
                signal_rows.append((message, signal))

        self.signal_table.setRowCount(len(signal_rows))
        for row, (message, signal) in enumerate(signal_rows):
            choices = "; ".join(f"{key}:{value}" for key, value in sorted(signal.choices.items()))
            values = [
                message.name,
                message.frame_id_hex,
                signal.name,
                signal.start_bit,
                signal.length,
                signal.byte_order,
                "有符号" if signal.is_signed else "无符号",
                signal.factor,
                signal.offset,
                signal.minimum,
                signal.maximum,
                signal.unit,
                signal.receivers,
                choices,
                signal.comment,
            ]
            for column, value in enumerate(values):
                item = self._table_item(value)
                item.setData(Qt.ItemDataRole.UserRole, message.frame_id)
                self.signal_table.setItem(row, column, item)

        self.message_table.setSortingEnabled(True)
        self.signal_table.setSortingEnabled(True)
        if self.message_table.rowCount() > 0:
            self.message_table.selectRow(0)
        self.apply_filters()

    def _table_item(self, value):
        item = QTableWidgetItem("" if value is None else str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _clear_tables(self):
        self.message_table.setRowCount(0)
        self.signal_table.setRowCount(0)

    def _update_summary(self):
        if self.database is None:
            for label in self.summary_labels.values():
                label.setText("--")
            return
        self.summary_labels["message_count"].setText(str(len(self.database.messages)))
        self.summary_labels["signal_count"].setText(str(self.database.signal_count))
        self.summary_labels["node_count"].setText(str(len(self.database.nodes)))
        self.summary_labels["encoding"].setText(self.database.encoding)
        self.summary_labels["nodes"].setText(", ".join(self.database.nodes) if self.database.nodes else "--")
        self.summary_labels["warnings"].setText(str(len(self.database.parse_warnings)))

    def on_message_selection_changed(self):
        self.apply_filters()

    def _selected_message_id(self):
        selected = self.message_table.selectionModel().selectedRows() if self.message_table.selectionModel() else []
        if not selected:
            return None
        item = self.message_table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def apply_filters(self):
        message_query = self.message_filter_edit.text().strip().lower()
        signal_query = self.signal_filter_edit.text().strip().lower()

        for row in range(self.message_table.rowCount()):
            row_text = " ".join(
                self.message_table.item(row, column).text().lower()
                for column in range(self.message_table.columnCount())
                if self.message_table.item(row, column) is not None
            )
            self.message_table.setRowHidden(row, bool(message_query and message_query not in row_text))

        selected_message_id = self._selected_message_id() if self.follow_message_checkbox.isChecked() else None
        for row in range(self.signal_table.rowCount()):
            item = self.signal_table.item(row, 0)
            row_message_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            row_text = " ".join(
                self.signal_table.item(row, column).text().lower()
                for column in range(self.signal_table.columnCount())
                if self.signal_table.item(row, column) is not None
            )
            hidden = False
            if selected_message_id is not None and row_message_id != selected_message_id:
                hidden = True
            if signal_query and signal_query not in row_text:
                hidden = True
            self.signal_table.setRowHidden(row, hidden)

    def set_status(self, text, failed=False):
        self.status_label.setText(str(text))
        self.status_label.setProperty("status", "danger" if failed else "info")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
