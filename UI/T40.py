from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from application.cluster_overview import RUN_STATUS_TEXT


FULL_STATE_TEXT = {0: "无", 1: "满充", 2: "满放"}


def _readonly_value():
    widget = QLineEdit()
    widget.setReadOnly(True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumHeight(34)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class ClusterOverviewPage(QWidget):
    GROUPS = (
        (
            "系统状态",
            (
                ("run_status", "运行状态", "status"),
                ("soc", "系统SOC", "%"),
                ("display_soc", "显示SOC", "%"),
                ("soh", "系统SOH", "%"),
                ("allow_high_voltage", "允许上高压", "bool"),
                ("full_charge_discharge", "满充满放", "full"),
                ("alarm_level", "最严重告警", "级"),
                ("active_alarm_count", "实时告警", "条"),
                ("history_log_count", "历史日志", "条"),
            ),
        ),
        (
            "电气参数",
            (
                ("system_current", "系统电流", "A"),
                ("battery_voltage", "B端电压", "V"),
                ("pack_voltage", "P端电压", "V"),
                ("positive_insulation_resistance", "正对地电阻", "kΩ"),
                ("negative_insulation_resistance", "负对地电阻", "kΩ"),
                ("insulation_finished", "绝缘检测", "finish"),
                ("max_charge_current", "最大允许充电", "A"),
                ("max_discharge_current", "最大允许放电", "A"),
                ("rated_capacity", "额定容量", "Ah"),
            ),
        ),
        (
            "单体统计",
            (
                ("max_cell_voltage", "最高单体电压", "mV"),
                ("max_cell_voltage_position", "最高电压位置", "text"),
                ("min_cell_voltage", "最低单体电压", "mV"),
                ("min_cell_voltage_position", "最低电压位置", "text"),
                ("average_cell_voltage", "平均单体电压", "mV"),
                ("voltage_delta", "单体压差", "mV"),
                ("max_cell_temperature", "最高单体温度", "℃"),
                ("max_cell_temperature_position", "最高温度位置", "text"),
                ("min_cell_temperature", "最低单体温度", "℃"),
                ("min_cell_temperature_position", "最低温度位置", "text"),
                ("average_cell_temperature", "平均单体温度", "℃"),
                ("temperature_delta", "单体温差", "℃"),
                ("max_terminal_temperature", "最高极柱温度", "℃"),
                ("max_terminal_temperature_position", "最高极柱位置", "text"),
            ),
        ),
        (
            "能量与时间",
            (
                ("remaining_charge_energy", "剩余可充电量", "kWh"),
                ("remaining_discharge_energy", "剩余可放电量", "kWh"),
                ("single_charge_energy", "单次充电量", "kWh"),
                ("single_discharge_energy", "单次放电量", "kWh"),
                ("total_charge_energy", "累计充电量", "kWh"),
                ("total_discharge_energy", "累计放电量", "kWh"),
                ("remaining_charge_time", "剩余充电时间", "s"),
                ("remaining_discharge_time", "剩余放电时间", "s"),
            ),
        ),
        (
            "配置与I/O",
            (
                ("valid_cell_voltage_count", "有效电压数", "个"),
                ("valid_cell_temperature_count", "有效温度数", "个"),
                ("online_module_count", "在线模组数", "个"),
                ("configured_cell_count", "配置单体数", "个"),
                ("charge_cycle_count", "循环次数", "次"),
                ("di_active_text", "有效DI", "text"),
                ("fire_module_text", "消防触发模组", "text"),
            ),
        ),
    )

    HALF_FIELDS = (
        ("run_status", "运行状态", "status"),
        ("soc", "SOC", "%"),
        ("battery_voltage", "B端电压", "V"),
        ("pack_voltage", "P端电压", "V"),
        ("current", "电流", "A"),
        ("allow_high_voltage", "允许上高压", "bool"),
        ("full_charge_discharge", "满充满放", "full"),
        ("max_cell_voltage", "最高单体电压", "mV"),
        ("min_cell_voltage", "最低单体电压", "mV"),
        ("max_charge_current", "最大允许充电", "A"),
        ("max_discharge_current", "最大允许放电", "A"),
        ("remaining_charge_energy", "剩余可充电量", "kWh"),
        ("remaining_discharge_energy", "剩余可放电量", "kWh"),
    )

    def __init__(self):
        super().__init__()
        self.current_cluster_index = 0
        self.current_address = ""
        self.has_neutral = None
        self.snapshot = {}
        self.value_fields = {}
        self.groups = []
        self.layout_column_count = 0
        self._build_ui()
        self.clear_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("簇数据总览", self)
        title.setObjectName("pageTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.protocol_label = QLabel("703 / BAU广播协议", self)
        self.protocol_label.setObjectName("statusPill")
        self.protocol_label.setProperty("status", "info")
        title_row.addWidget(self.protocol_label)
        root.addLayout(title_row)

        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        root.addWidget(self.cluster_label)

        self.status_label = QLabel("等待703簇广播数据。", self)
        self.status_label.setObjectName("sectionHint")
        root.addWidget(self.status_label)

        self.summary_band = QFrame(self)
        self.summary_band.setObjectName("diagnosticMetricBand")
        summary_layout = QGridLayout(self.summary_band)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(4)
        self.summary_values = {}
        for column, (key, label_text) in enumerate((
            ("run_status", "运行状态"),
            ("soc", "SOC"),
            ("system_current", "系统电流"),
            ("pack_voltage", "P端电压"),
            ("active_alarm_count", "实时告警"),
            ("online_module_count", "在线模组"),
        )):
            label = QLabel(label_text, self.summary_band)
            label.setObjectName("fieldCaption")
            value = QLabel("--", self.summary_band)
            value.setObjectName("diagnosticMetricValue")
            summary_layout.addWidget(label, 0, column)
            summary_layout.addWidget(value, 1, column)
            summary_layout.setColumnStretch(column, 1)
            self.summary_values[key] = value
        root.addWidget(self.summary_band)

        self.scroll = QScrollArea(self)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, 1)

        self.content = QWidget(self.scroll)
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 4, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.scroll.setWidget(self.content)
        self.scroll.viewport().installEventFilter(self)

        for title_text, fields in self.GROUPS:
            self.groups.append(self._build_group(title_text, fields))
        self.upper_group = self._build_half_group("上半簇", "upper_")
        self.lower_group = self._build_half_group("下半簇", "lower_")
        self.groups.extend((self.upper_group, self.lower_group))
        self._relayout(3)

    def _build_group(self, title, fields):
        group = QGroupBox(title, self.content)
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        for row, (key, label_text, kind) in enumerate(fields):
            label = QLabel(label_text, group)
            label.setObjectName("metricLabel")
            value = _readonly_value()
            layout.addWidget(label, row, 0)
            layout.addWidget(value, row, 1)
            layout.setColumnStretch(1, 1)
            self.value_fields[key] = (value, kind)
        return group

    def _build_half_group(self, title, prefix):
        fields = []
        for suffix, label, kind in self.HALF_FIELDS:
            key = f"{prefix}{suffix}"
            if suffix == "current":
                key = "hall_current" if prefix == "upper_" else "shunt_current"
            fields.append((key, label, kind))
        return self._build_group(title, tuple(fields))

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            width = event.size().width()
            self._relayout(3 if width >= 1500 else 2 if width >= 980 else 1)
        return super().eventFilter(watched, event)

    def _relayout(self, columns):
        columns = max(1, min(int(columns), 3))
        if columns == self.layout_column_count:
            return
        while self.grid.count():
            self.grid.takeAt(0)
        visible_groups = [group for group in self.groups if not group.isHidden()]
        for index, group in enumerate(visible_groups):
            self.grid.addWidget(group, index // columns, index % columns)
        for column in range(3):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self.layout_column_count = columns

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = int(cluster_index or 0)
        self.current_address = str(address or "")
        if self.current_cluster_index <= 0:
            text = "当前簇: 00（未编制）"
        else:
            text = f"当前簇: 簇{self.current_cluster_index} / 地址 {self.current_address}"
        if self.cluster_label.text() != text:
            self.cluster_label.setText(text)

    def set_has_neutral(self, has_neutral):
        normalized = bool(has_neutral)
        if self.has_neutral is normalized:
            return
        self.has_neutral = normalized
        self.upper_group.setVisible(self.has_neutral)
        self.lower_group.setVisible(self.has_neutral)
        self.layout_column_count = 0
        width = self.scroll.viewport().width()
        self._relayout(3 if width >= 1500 else 2 if width >= 980 else 1)

    def set_status_text(self, text):
        text = str(text or "")
        if self.status_label.text() != text:
            self.status_label.setText(text)

    def clear_values(self):
        self.snapshot = {}
        for widget, _kind in self.value_fields.values():
            widget.setText("--")
        for label in self.summary_values.values():
            label.setText("--")

    def update_snapshot(self, snapshot):
        self.snapshot = dict(snapshot or {})
        for key, (widget, kind) in self.value_fields.items():
            text = self._format_value(self.snapshot.get(key), kind)
            if widget.text() != text:
                widget.setText(text)

        summary_formats = {
            "run_status": "status",
            "soc": "%",
            "system_current": "A",
            "pack_voltage": "V",
            "active_alarm_count": "条",
            "online_module_count": "个",
        }
        for key, label in self.summary_values.items():
            text = self._format_value(self.snapshot.get(key), summary_formats[key])
            if label.text() != text:
                label.setText(text)

    def _format_value(self, value, kind):
        if value is None:
            return "--"
        if kind == "status":
            try:
                number = int(value)
            except (TypeError, ValueError):
                return str(value)
            return f"{number} {RUN_STATUS_TEXT.get(number, '未知')}"
        if kind == "bool":
            return "允许" if bool(value) else "禁止"
        if kind == "finish":
            return "完成" if bool(value) else "未完成"
        if kind == "full":
            try:
                return FULL_STATE_TEXT.get(int(value), f"状态{int(value)}")
            except (TypeError, ValueError):
                return str(value)
        if kind == "text":
            return str(value)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        text = f"{number:.2f}".rstrip("0").rstrip(".")
        if kind:
            text = f"{text} {kind}"
        return text
