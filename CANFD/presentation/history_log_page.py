import csv

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


HISTORY_LOG_COLUMNS = (
    ("序号", "sequence"),
    ("时间", "timestamp"),
    ("日志类型", "log_type"),
    ("系统运行状态", "run_status"),
    ("继电器状态", "relay_status"),
    ("告警总个数", "alarm_count"),
    ("双字节内容", "raw_word"),
    ("告警ID", "alarm_id"),
    ("告警名称", "alarm_name"),
    ("告警级别", "alarm_level"),
    ("告警位置", "alarm_position"),
    ("总电压[V]", "total_voltage"),
    ("总电流[A]", "total_current"),
    ("SOC[%]", "soc"),
    ("SOH[%]", "soh"),
    ("正对地电阻", "p_bus_resistance"),
    ("负对地电阻", "n_bus_resistance"),
    ("单体压差[mV]", "diff_voltage"),
    ("单体温差[℃]", "diff_temperature"),
    ("最高单体电压[mV]", "max_cell_voltage"),
    ("最高电压位置", "max_cell_voltage_position"),
    ("最低单体电压[mV]", "min_cell_voltage"),
    ("最低电压位置", "min_cell_voltage_position"),
    ("最高单体温度[℃]", "max_cell_temperature"),
    ("最高温度位置", "max_cell_temperature_position"),
    ("最低单体温度[℃]", "min_cell_temperature"),
    ("最低温度位置", "min_cell_temperature_position"),
    ("阈值", "threshold_value"),
    ("触发值", "actual_value"),
    ("子类型", "log_subtype"),
)


def _format_cell_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


class HistoryLogPage(QWidget):
    LOG_TYPE_ALARM = 1
    LOG_TYPE_OTHER = 2

    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = None
        self.records = []
        self._build_ui()
        self.set_reading(False)
        self.set_counts(0, 0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.title_label = QLabel("历史日志数据", self)
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        layout.addWidget(self.cluster_label)

        control_panel = QFrame(self)
        control_panel.setObjectName("dataSectionCard")
        control_layout = QGridLayout(control_panel)
        control_layout.setContentsMargins(16, 14, 16, 14)
        control_layout.setHorizontalSpacing(12)
        control_layout.setVerticalSpacing(10)

        type_group = QGroupBox("日志类型", control_panel)
        type_layout = QHBoxLayout(type_group)
        type_layout.setContentsMargins(12, 8, 12, 8)
        self.alarm_radio = QRadioButton("告警", type_group)
        self.other_radio = QRadioButton("其他", type_group)
        self.alarm_radio.setChecked(True)
        self.log_type_group = QButtonGroup(type_group)
        self.log_type_group.addButton(self.alarm_radio, self.LOG_TYPE_ALARM)
        self.log_type_group.addButton(self.other_radio, self.LOG_TYPE_OTHER)
        type_layout.addWidget(self.alarm_radio)
        type_layout.addWidget(self.other_radio)
        control_layout.addWidget(type_group, 0, 0, 2, 1)

        self.read_button = QPushButton("读取日志", control_panel)
        self.stop_button = QPushButton("停止读取", control_panel)
        self.save_button = QPushButton("保存日志", control_panel)
        self.clear_table_button = QPushButton("清除表格数据", control_panel)
        self.clear_device_button = QPushButton("清空日志", control_panel)

        control_layout.addWidget(self.read_button, 0, 1)
        control_layout.addWidget(self.stop_button, 1, 1)
        control_layout.addWidget(self.save_button, 0, 2)
        control_layout.addWidget(self.clear_table_button, 0, 3)
        control_layout.addWidget(self.clear_device_button, 0, 4)

        count_panel = QWidget(control_panel)
        count_layout = QGridLayout(count_panel)
        count_layout.setContentsMargins(0, 0, 0, 0)
        count_layout.setHorizontalSpacing(8)
        count_layout.setVerticalSpacing(6)
        count_layout.addWidget(QLabel("日志总数", count_panel), 0, 0)
        self.total_count_edit = self._readonly_count_edit(count_panel)
        count_layout.addWidget(self.total_count_edit, 0, 1)
        count_layout.addWidget(QLabel("读取第", count_panel), 1, 0)
        self.read_count_edit = self._readonly_count_edit(count_panel)
        count_layout.addWidget(self.read_count_edit, 1, 1)
        count_layout.addWidget(QLabel("条", count_panel), 0, 2)
        count_layout.addWidget(QLabel("条", count_panel), 1, 2)
        control_layout.addWidget(count_panel, 0, 5, 2, 1)

        status_panel = QWidget(control_panel)
        status_layout = QGridLayout(status_panel)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setHorizontalSpacing(8)
        status_layout.setVerticalSpacing(6)
        status_layout.addWidget(QLabel("日志读取状态", status_panel), 0, 0)
        self.status_edit = QLineEdit(status_panel)
        self.status_edit.setReadOnly(True)
        self.status_edit.setMinimumWidth(280)
        self.status_edit.setText("未读取")
        status_layout.addWidget(self.status_edit, 0, 1)
        control_layout.addWidget(status_panel, 1, 2, 1, 3)

        control_layout.setColumnStretch(6, 1)
        layout.addWidget(control_panel)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(HISTORY_LOG_COLUMNS))
        self.table.setHorizontalHeaderLabels([header for header, _ in HISTORY_LOG_COLUMNS])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setDefaultSectionSize(118)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnWidth(0, 72)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(4, 180)
        self.table.setColumnWidth(8, 180)
        self.table.setColumnWidth(10, 260)
        self.table.setColumnWidth(20, 170)
        self.table.setColumnWidth(22, 170)
        self.table.setColumnWidth(24, 170)
        self.table.setColumnWidth(26, 170)
        layout.addWidget(self.table, stretch=1)

    @staticmethod
    def _readonly_count_edit(parent):
        widget = QLineEdit(parent)
        widget.setReadOnly(True)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setFixedWidth(72)
        return widget

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = cluster_index
        self.current_address = address
        if cluster_index is None:
            text = "当前簇: -"
        else:
            text = f"当前簇: 簇{cluster_index} / 地址 {address}"
        self.cluster_label.setText(text)

    def selected_log_type(self):
        return self.log_type_group.checkedId()

    def set_reading(self, reading):
        reading = bool(reading)
        self.read_button.setEnabled(not reading)
        self.stop_button.setEnabled(reading)
        self.save_button.setEnabled(not reading and bool(self.records))
        self.clear_table_button.setEnabled(not reading and bool(self.records))
        self.clear_device_button.setEnabled(not reading)
        self.alarm_radio.setEnabled(not reading)
        self.other_radio.setEnabled(not reading)

    def set_counts(self, total, read_count):
        self.total_count_edit.setText(str(int(total)))
        self.read_count_edit.setText(str(int(read_count)))

    def set_status(self, text, failed=False):
        self.status_edit.setText(str(text))
        style = "color: #c62828; font-weight: 700;" if failed else ""
        if self.status_edit.styleSheet() != style:
            self.status_edit.setStyleSheet(style)

    def clear_records(self):
        self.records = []
        self.table.setRowCount(0)
        self.set_counts(0, 0)
        self.set_status("表格已清空")
        self.set_reading(False)

    def append_record(self, record):
        self.records.append(record)
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        for column_index, (_, field_name) in enumerate(HISTORY_LOG_COLUMNS):
            value = getattr(record, field_name, "")
            text = _format_cell_value(value)
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            if isinstance(value, (int, float)):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row_index, column_index, item)
        self.save_button.setEnabled(True)
        self.clear_table_button.setEnabled(True)

    def save_records_to_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow([header for header, _ in HISTORY_LOG_COLUMNS])
            for record in self.records:
                writer.writerow(
                    [
                        _format_cell_value(getattr(record, field_name, ""))
                        for _, field_name in HISTORY_LOG_COLUMNS
                    ]
                )

    def choose_save_path(self):
        return QFileDialog.getSaveFileName(
            self,
            "保存历史日志",
            "history_log.csv",
            "CSV Files (*.csv);;All Files (*)",
        )[0]
