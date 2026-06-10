from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistoryLogPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("历史日志", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton("刷新文件", self)
        self.load_button = QPushButton("加载选中", self)
        self.export_button = QPushButton("另存当前表格", self)
        self.open_dir_button = QPushButton("打开目录", self)
        self.clear_button = QPushButton("清空表格", self)
        for button in (
            self.refresh_button,
            self.load_button,
            self.export_button,
            self.open_dir_button,
            self.clear_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.status_label = QLabel("显示 hisData 目录下保存的运行数据。", self)
        self.status_label.setObjectName("sectionHint")
        root.addWidget(self.status_label)

        body = QHBoxLayout()
        body.setSpacing(10)
        root.addLayout(body, 1)

        file_panel = QFrame(self)
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(QLabel("日志文件", file_panel))
        self.file_list = QListWidget(file_panel)
        file_layout.addWidget(self.file_list, 1)
        body.addWidget(file_panel, 2)

        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        body.addWidget(self.table, 7)

    def set_status_text(self, text):
        self.status_label.setText(str(text))

    def set_files(self, files):
        self.file_list.clear()
        for path in files:
            self.file_list.addItem(path)
        if files:
            self.file_list.setCurrentRow(0)

    def selected_file(self):
        item = self.file_list.currentItem()
        return item.text() if item is not None else ""

    def set_table_data(self, columns, rows):
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([str(column) for column in columns])
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column_index, item)
        self.table.resizeColumnsToContents()

    def clear_table(self):
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

    def choose_export_path(self):
        return QFileDialog.getSaveFileName(
            self,
            "另存历史日志",
            "history_log.csv",
            "CSV Files (*.csv);;All Files (*)",
        )[0]
