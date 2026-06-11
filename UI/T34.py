import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


RUN_STATUS_TEXT = {
    0: "初始",
    1: "自测",
    2: "准备",
    3: "预充",
    4: "高压待机",
    5: "放电",
    6: "充电",
    7: "放空",
    8: "充满",
    9: "错误",
    10: "切断",
    11: "休眠",
}

WORK_MODE_TEXT = {
    0: "正常",
    1: "工装",
}


def _readonly_edit(width=108):
    widget = QLineEdit()
    widget.setReadOnly(True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(width)
    widget.setMinimumHeight(34)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


def _format_number(value, *, divisor=1.0, digits=1, suffix=""):
    if value is None:
        return "--"
    try:
        number = float(value) / float(divisor)
    except (TypeError, ValueError):
        text = str(value)
    else:
        text = f"{number:.{digits}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _format_int(value, suffix=""):
    if value is None:
        return "--"
    try:
        return f"{int(float(value))}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


class StateDot(QFrame):
    def __init__(self, label_text):
        super().__init__()
        self._active = None
        self._label_text = str(label_text)
        self.setObjectName("stateBadge")
        self.setMinimumHeight(34)
        self.setMinimumWidth(104)
        self.setToolTip(self._label_text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.dot_frame = QFrame(self)
        self.dot_frame.setObjectName("stateDotIcon")
        self.dot_frame.setFixedSize(14, 14)
        layout.addWidget(self.dot_frame, 0, Qt.AlignmentFlag.AlignVCenter)

        self.text_label = QLabel(self._label_text, self)
        self.text_label.setObjectName("stateBadgeLabel")
        layout.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.set_active(None)

    def set_active(self, active):
        if self._active == active:
            return
        self._active = active
        if active is None:
            badge_color = "#f8fafc"
            border_color = "#d7e0eb"
            text_color = "#64748b"
            dot_color = "#b0bec5"
            dot_border_color = "#94a3b8"
        elif active:
            badge_color = "#e8fff1"
            border_color = "#9ee6bb"
            text_color = "#116149"
            dot_color = "#3cb371"
            dot_border_color = "#2f8f5b"
        else:
            badge_color = "#f8fafc"
            border_color = "#d7e0eb"
            text_color = "#334155"
            dot_color = "#8c8c8c"
            dot_border_color = "#6b7280"
        self.setStyleSheet(
            f"""
            QFrame#stateBadge {{
                background: {badge_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#stateDotIcon {{
                background: {dot_color};
                border: 1px solid {dot_border_color};
                border-radius: 7px;
            }}
            QLabel#stateBadgeLabel {{
                color: {text_color};
                font-weight: 700;
                background: transparent;
                border: none;
            }}
            """
        )


class RealtimeMonitorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = None
        self.value_fields = {}
        self.input_dots = []
        self.output_dots = []
        self.rt_fields = []
        self._build_ui()
        self.clear_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("实时监控", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        root.addWidget(self.cluster_label)

        self.status_label = QLabel("监控数据由请求索引后台刷新。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        root.addLayout(grid, stretch=1)

        grid.addWidget(self._build_system_group(), 0, 0)
        grid.addWidget(self._build_state_group(), 0, 1)
        grid.addWidget(self._build_soc_group(), 0, 2)
        grid.addWidget(self._build_extrema_group(), 1, 0)
        grid.addWidget(self._build_statistics_group(), 1, 1)
        grid.addWidget(self._build_temperature_group(), 1, 2)

    def _metric_label(self, text, parent, width=108):
        label = QLabel(str(text), parent)
        label.setObjectName("metricLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(width)
        label.setMinimumHeight(34)
        return label

    def _populate_metric_grid(self, layout, parent, fields, *, columns=1, label_width=108, value_width=108):
        column_count = max(int(columns), 1)
        items_per_column = max(1, math.ceil(len(fields) / column_count))
        for index, (key, label_text) in enumerate(fields):
            column_index = index // items_per_column
            row_index = index % items_per_column
            row_widget = QWidget(parent)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            row_layout.addWidget(self._metric_label(label_text, parent, label_width))
            value_widget = _readonly_edit(value_width)
            row_layout.addWidget(value_widget, 1)
            layout.addWidget(row_widget, row_index, column_index)
            self.value_fields[key] = value_widget
        for column_index in range(column_count):
            layout.setColumnStretch(column_index, 1)

    def _build_system_group(self):
        group = QGroupBox("系统信息", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        fields = (
            ("work_mode", "工装模式"),
            ("run_status", "运行状态"),
            ("system_current", "综合电流"),
            ("hall_current", "霍尔电流"),
            ("shunt_current", "分流器电流"),
            ("battery_voltage", "电池总压"),
            ("system_voltage", "综合总压"),
            ("pack_voltage", "输出总压"),
            ("soc", "系统SOC"),
            ("display_soc", "在线显示SOC"),
            ("soh", "系统SOH"),
            ("diff_voltage", "单体压差"),
            ("diff_temp", "单体温差"),
            ("avg_voltage", "平均单体电压"),
            ("avg_temp", "平均单体温度"),
            ("module_count", "在线模组数"),
            ("afe_count", "每模组AFE"),
            ("online_lecu_num", "在线LECU数"),
        )
        self._populate_metric_grid(layout, group, fields, columns=2, label_width=116, value_width=116)
        return group

    def _build_state_group(self):
        group = QGroupBox("输入 / 输出状态", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        input_group = QGroupBox("DI输入状态", group)
        input_layout = QGridLayout(input_group)
        input_layout.setHorizontalSpacing(10)
        input_layout.setVerticalSpacing(8)
        input_layout.setContentsMargins(10, 10, 10, 10)
        for index in range(12):
            dot = StateDot(f"DI{index + 1}")
            self.input_dots.append(dot)
            input_layout.addWidget(dot, index // 6, index % 6)
        layout.addWidget(input_group)

        output_group = QGroupBox("输出状态", group)
        output_layout = QGridLayout(output_group)
        output_layout.setHorizontalSpacing(10)
        output_layout.setVerticalSpacing(8)
        output_layout.setContentsMargins(10, 10, 10, 10)
        names = [f"HSD{index}" for index in range(1, 9)] + ["LSD1", "LSD2"]
        for index, name in enumerate(names):
            dot = StateDot(name)
            self.output_dots.append(dot)
            output_layout.addWidget(dot, index // 5, index % 5)
        layout.addWidget(output_group)
        layout.addStretch(1)
        return group

    def _build_soc_group(self):
        group = QGroupBox("SOC", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.soc_display = QLabel("--", group)
        self.soc_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.soc_display.setStyleSheet(
            "font-size: 30px; font-weight: 800; color: #0f172a;"
            "background: #eef4ff; border: 1px solid #c8dafc; border-radius: 12px;"
            "padding: 22px 12px;"
        )
        layout.addWidget(self.soc_display)

        metrics = QWidget(group)
        metrics_layout = QGridLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(8)
        fields = (
            ("pure_soc", "原始SOC"),
            ("revise_soc", "修正SOC"),
            ("revise_soc_temp", "温度修正SOC"),
            ("fuzzy_soc", "模糊SOC"),
            ("cell_max_soc", "单体最高SOC"),
            ("cell_min_soc", "单体最低SOC"),
            ("cell_max_soc_temp", "最高SOC温度"),
            ("cell_min_soc_temp", "最低SOC温度"),
        )
        self._populate_metric_grid(metrics_layout, metrics, fields, columns=2, label_width=126, value_width=116)
        layout.addWidget(metrics)
        return group

    def _build_extrema_group(self):
        group = QGroupBox("极值信息", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        fields = (
            ("max_cell_voltage", "最高单体电压"),
            ("max_cell_voltage_module", "最高电压模组"),
            ("max_cell_voltage_index", "最高电压位置"),
            ("min_cell_voltage", "最低单体电压"),
            ("min_cell_voltage_module", "最低电压模组"),
            ("min_cell_voltage_index", "最低电压位置"),
            ("max_cell_temp", "最高单体温度"),
            ("max_cell_temp_module", "最高温度模组"),
            ("max_cell_temp_index", "最高温度位置"),
            ("min_cell_temp", "最低单体温度"),
            ("min_cell_temp_module", "最低温度模组"),
            ("min_cell_temp_index", "最低温度位置"),
        )
        self._populate_metric_grid(layout, group, fields, columns=2, label_width=116, value_width=116)
        return group

    def _build_statistics_group(self):
        group = QGroupBox("统计信息", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        fields = (
            ("remaining_discharge_kwh", "剩余可放电"),
            ("remaining_charge_kwh", "剩余可充电"),
            ("single_charge_kwh", "单次充电电量"),
            ("single_discharge_kwh", "单次放电电量"),
            ("total_charge_kwh", "累计充电电量"),
            ("total_discharge_kwh", "累计放电电量"),
            ("max_discharge_power", "最大放电功率"),
            ("max_charge_power", "最大充电功率"),
            ("max_discharge_current", "最大放电电流"),
            ("max_charge_current", "最大充电电流"),
            ("hvil_pwm_freq", "HVIL频率"),
            ("hvil_pwm_duty", "HVIL占空比"),
        )
        self._populate_metric_grid(layout, group, fields, columns=2, label_width=112, value_width=116)
        return group

    def _build_temperature_group(self):
        group = QGroupBox("RT温度", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        fields = [(f"rt_{index + 1:02d}", f"RT{index + 1:02d}") for index in range(10)]
        fields += (("board_temp1", "BCU板温1"), ("board_temp2", "BCU板温2"))
        self._populate_metric_grid(layout, group, fields, columns=2, label_width=92, value_width=116)
        self.rt_fields = [self.value_fields[f"rt_{index + 1:02d}"] for index in range(10)]
        return group

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = cluster_index
        self.current_address = address
        if cluster_index is None or not address:
            self.cluster_label.setText("当前簇: -")
            return
        self.cluster_label.setText(f"当前簇: 簇{cluster_index} / 地址 {address}")

    def set_status_text(self, text):
        self.status_label.setText("" if text is None else str(text))

    def clear_values(self):
        self.soc_display.setText("--")
        for widget in self.value_fields.values():
            widget.setText("--")
        for dot in self.input_dots + self.output_dots:
            dot.set_active(None)

    def update_snapshot(self, snapshot):
        if not snapshot:
            self.clear_values()
            return

        self._set_mode_field("work_mode", snapshot.get("work_mode"), WORK_MODE_TEXT)
        self._set_mode_field("run_status", snapshot.get("run_status"), RUN_STATUS_TEXT)
        for key, divisor, suffix in (
            ("system_current", 1, " A"),
            ("hall_current", 1, " A"),
            ("shunt_current", 1, " A"),
            ("battery_voltage", 1, " V"),
            ("system_voltage", 1, " V"),
            ("pack_voltage", 1, " V"),
            ("soc", 10, " %"),
            ("display_soc", 10, " %"),
            ("soh", 10, " %"),
            ("diff_temp", 10, " ℃"),
            ("avg_temp", 10, " ℃"),
            ("pure_soc", 10, " %"),
            ("revise_soc", 10, " %"),
            ("revise_soc_temp", 10, " %"),
            ("fuzzy_soc", 10, " %"),
            ("cell_max_soc", 10, " %"),
            ("cell_min_soc", 10, " %"),
            ("cell_max_soc_temp", 10, " %"),
            ("cell_min_soc_temp", 10, " %"),
            ("max_cell_temp", 1, " ℃"),
            ("min_cell_temp", 1, " ℃"),
            ("remaining_discharge_kwh", 100, " kWh"),
            ("remaining_charge_kwh", 100, " kWh"),
            ("single_charge_kwh", 100, " kWh"),
            ("single_discharge_kwh", 100, " kWh"),
            ("total_charge_kwh", 10, " kWh"),
            ("total_discharge_kwh", 10, " kWh"),
            ("max_discharge_power", 1, " kW"),
            ("max_charge_power", 1, " kW"),
            ("max_discharge_current", 1, " A"),
            ("max_charge_current", 1, " A"),
            ("hvil_pwm_freq", 10, " Hz"),
            ("hvil_pwm_duty", 10, " %"),
            ("board_temp1", 10, " ℃"),
            ("board_temp2", 10, " ℃"),
        ):
            self._set_value(key, _format_number(snapshot.get(key), divisor=divisor, suffix=suffix))

        for key, suffix in (
            ("diff_voltage", " mV"),
            ("avg_voltage", " mV"),
            ("module_count", ""),
            ("afe_count", ""),
            ("online_lecu_num", ""),
            ("max_cell_voltage", " mV"),
            ("max_cell_voltage_module", ""),
            ("max_cell_voltage_index", ""),
            ("min_cell_voltage", " mV"),
            ("min_cell_voltage_module", ""),
            ("min_cell_voltage_index", ""),
            ("max_cell_temp_module", ""),
            ("max_cell_temp_index", ""),
            ("min_cell_temp_module", ""),
            ("min_cell_temp_index", ""),
        ):
            self._set_value(key, _format_int(snapshot.get(key), suffix))

        self.soc_display.setText(_format_number(snapshot.get("soc"), divisor=10, suffix=" %"))
        for index, value in enumerate(snapshot.get("rt_values", [])):
            if index >= len(self.rt_fields):
                break
            self.rt_fields[index].setText(_format_number(value, divisor=10, suffix=" ℃"))
        for dot, state in zip(self.input_dots, snapshot.get("di_states", [])):
            dot.set_active(state)
        for dot, state in zip(self.output_dots, snapshot.get("relay_states", [])):
            dot.set_active(state)

    def _set_mode_field(self, key, value, mapping):
        if value is None:
            self._set_value(key, "--")
            return
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            self._set_value(key, str(value))
            return
        self._set_value(key, f"{number} {mapping.get(number, '')}".strip())

    def _set_value(self, key, text):
        widget = self.value_fields.get(key)
        if widget is not None:
            widget.setText(text)
