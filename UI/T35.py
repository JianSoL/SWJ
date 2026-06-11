from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ActiveAlarmPage(QWidget):
    def __init__(self):
        super().__init__()
        self.active_alarm_records = []
        self.current_cluster_index = 0
        self.current_cluster_address = ""
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        title = QLabel("实时告警", self)
        title.setObjectName("pageTitle")
        root_layout.addWidget(title)

        self.cluster_label = QLabel("当前簇：--", self)
        self.cluster_label.setObjectName("contextLabel")
        root_layout.addWidget(self.cluster_label)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.summary_label = QLabel("实时告警总数：--", self)
        self.summary_label.setObjectName("sectionHint")
        toolbar.addWidget(self.summary_label)
        toolbar.addStretch(1)

        self.auto_refresh_checkbox = QCheckBox("自动刷新", self)
        self.auto_refresh_checkbox.setChecked(True)
        toolbar.addWidget(self.auto_refresh_checkbox)

        toolbar.addWidget(QLabel("间隔", self))
        self.interval_spinbox = QSpinBox(self)
        self.interval_spinbox.setRange(1, 60)
        self.interval_spinbox.setValue(2)
        self.interval_spinbox.setSuffix(" s")
        self.interval_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.interval_spinbox.setFixedWidth(88)
        toolbar.addWidget(self.interval_spinbox)

        self.read_button = QPushButton("刷新一次", self)
        self.read_button.setObjectName("primaryButton")
        toolbar.addWidget(self.read_button)

        self.clear_button = QPushButton("清空表格", self)
        toolbar.addWidget(self.clear_button)
        root_layout.addLayout(toolbar)

        self.status_label = QLabel("进入页面后自动读取当前簇实时告警。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)

        table_group = QGroupBox("实时告警列表", self)
        table_layout = QVBoxLayout(table_group)
        self.active_alarm_table = QTableWidget(table_group)
        self.active_alarm_table.setColumnCount(8)
        self.active_alarm_table.setHorizontalHeaderLabels(
            ["序号", "告警ID", "告警名称", "告警级别", "位置", "设备类型", "半簇", "发生时间"]
        )
        self.active_alarm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.active_alarm_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.active_alarm_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.active_alarm_table.verticalHeader().setVisible(False)
        self.active_alarm_table.setAlternatingRowColors(True)
        self.active_alarm_table.setColumnWidth(0, 58)
        self.active_alarm_table.setColumnWidth(1, 76)
        self.active_alarm_table.setColumnWidth(2, 260)
        self.active_alarm_table.setColumnWidth(3, 90)
        self.active_alarm_table.setColumnWidth(4, 200)
        self.active_alarm_table.setColumnWidth(5, 90)
        self.active_alarm_table.setColumnWidth(6, 90)
        self.active_alarm_table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.active_alarm_table)
        root_layout.addWidget(table_group, 1)

        self.clear_button.clicked.connect(self.clear_active_alarm_records)

    def set_cluster_context(self, cluster_index=None, address=None):
        self.current_cluster_index = 0 if cluster_index is None else int(cluster_index)
        self.current_cluster_address = "" if address is None else str(address).upper()
        if self.current_cluster_index == 0:
            text = f"当前簇：00 / 地址 {self.current_cluster_address or '--'}"
        else:
            text = f"当前簇：簇{self.current_cluster_index} / 地址 {self.current_cluster_address or '--'}"
        self.cluster_label.setText(text)

    def set_status_text(self, text, failed=False):
        self.status_label.setText("" if text is None else str(text))
        self.status_label.setProperty("status", "danger" if failed else "info")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_reading(self, reading):
        self.read_button.setEnabled(not bool(reading))

    def auto_refresh_enabled(self):
        return self.auto_refresh_checkbox.isChecked()

    def refresh_interval_ms(self):
        return int(self.interval_spinbox.value()) * 1000

    def set_active_alarm_status(self, total_count=None, read_count=None, failed=False):
        if total_count is None:
            text = "实时告警总数：--"
        elif read_count is None:
            text = f"实时告警总数：{int(total_count)}"
        else:
            text = f"实时告警总数：{int(total_count)} / 已读取：{int(read_count)}"
        self.summary_label.setText(text)
        self.summary_label.setProperty("status", "danger" if failed else "info")
        self.summary_label.style().unpolish(self.summary_label)
        self.summary_label.style().polish(self.summary_label)

    def set_active_alarm_records(self, records, total_count=None):
        self.active_alarm_records = list(records or [])
        self.active_alarm_table.setRowCount(len(self.active_alarm_records))
        for row, record in enumerate(self.active_alarm_records):
            values = [
                record.get("index", row + 1),
                record.get("alarm_id", ""),
                record.get("alarm_name", ""),
                record.get("alarm_level_text", record.get("alarm_level", "")),
                record.get("position", ""),
                record.get("equip_type", ""),
                record.get("bat_text", record.get("bat_no", "")),
                record.get("start_time", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col in (0, 1, 3, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.active_alarm_table.setItem(row, col, item)
        self.set_active_alarm_status(
            len(self.active_alarm_records) if total_count is None else total_count,
            len(self.active_alarm_records),
        )

    def clear_active_alarm_records(self):
        self.active_alarm_records = []
        self.active_alarm_table.setRowCount(0)
        self.set_active_alarm_status(0, 0)
        self.set_status_text("实时告警表格已清空。")
