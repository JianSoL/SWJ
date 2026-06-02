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
    0: "\u521d\u59cb",
    1: "\u81ea\u68c0",
    2: "\u51c6\u5907",
    3: "\u9884\u5145",
    4: "\u9ad8\u538b\u5f85\u673a",
    5: "\u653e\u7535",
    6: "\u5145\u7535",
    7: "\u653e\u7a7a",
    8: "\u5145\u6ee1",
    9: "\u9519\u8bef",
    10: "\u5207\u65ad",
    11: "\u4f11\u7720",
}

WORK_MODE_TEXT = {
    0: "\u6b63\u5e38",
    1: "\u5de5\u88c5",
}


def _readonly_edit(width=110):
    widget = QLineEdit()
    widget.setReadOnly(True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(width)
    widget.setMinimumHeight(34)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


def _format_scaled(value, divisor=1.0, digits=1, suffix=""):
    if value is None:
        return "--"
    scaled = float(value) / float(divisor)
    text = f"{scaled:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _format_int(value, suffix=""):
    if value is None:
        return "--"
    return f"{int(value)}{suffix}"


class StateDot(QFrame):
    def __init__(self, label_text):
        super().__init__()
        self._active = None
        self._label_text = str(label_text)
        self.setObjectName("stateBadge")
        self.setMinimumHeight(34)
        self.setMinimumWidth(118)
        self.setToolTip(self._label_text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
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
                border-radius: 10px;
            }}
            QFrame#stateDotIcon {{
                background: {dot_color};
                border: 1px solid {dot_border_color};
                border-radius: 7px;
            }}
            QLabel#stateBadgeLabel {{
                color: {text_color};
                font-weight: 600;
                background: transparent;
                border: none;
            }}
            """
        )


class IndexMonitorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = None
        self.value_fields = {}
        self.metric_labels = {}
        self.input_dots = []
        self.output_dots = []
        self.rt_fields = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("\u5b9e\u65f6\u76d1\u63a7", self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.cluster_label = QLabel("\u5f53\u524d\u7c07: -", self)
        self.cluster_label.setObjectName("contextLabel")
        layout.addWidget(self.cluster_label)

        self.status_label = QLabel(
            "\u76d1\u63a7\u6570\u636e\u901a\u8fc7\u8bf7\u6c42\u7d22\u5f15\u8f6e\u8be2\u66f4\u65b0\u3002",
            self,
        )
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        top_layout = QGridLayout()
        top_layout.setHorizontalSpacing(12)
        top_layout.setVerticalSpacing(12)
        top_layout.setColumnStretch(0, 1)
        top_layout.setColumnStretch(1, 1)
        top_layout.setColumnStretch(2, 1)
        top_layout.setRowStretch(0, 0)
        top_layout.setRowStretch(1, 0)
        layout.addLayout(top_layout, stretch=1)

        top_layout.addWidget(self._build_system_group(), 0, 0)
        top_layout.addWidget(self._build_state_group(), 0, 1)
        top_layout.addWidget(self._build_soc_group(), 0, 2)
        top_layout.addWidget(self._build_extrema_group(), 1, 0)
        top_layout.addWidget(self._build_statistics_group(), 1, 1)
        top_layout.addWidget(self._build_temperature_group(), 1, 2)

    def _create_metric_label(self, text, parent, width=110):
        label = QLabel(str(text), parent)
        label.setObjectName("metricLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(width)
        label.setMinimumHeight(34)
        return label

    def _populate_metric_grid(
        self,
        layout,
        parent,
        fields,
        *,
        columns=1,
        label_width=110,
        value_width=110,
    ):
        column_count = max(int(columns), 1)
        items_per_column = max(1, math.ceil(len(fields) / column_count))
        for index, (key, label_text) in enumerate(fields):
            column_index = index // items_per_column
            row_index = index % items_per_column
            label = self._create_metric_label(label_text, parent, label_width)
            widget = _readonly_edit(value_width)
            row_widget = QWidget(parent)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)
            row_layout.addWidget(label)
            row_layout.addWidget(widget, 1)
            layout.addWidget(row_widget, row_index, column_index)
            self.metric_labels[key] = label
            self.value_fields[key] = widget
        for column_index in range(column_count):
            layout.setColumnStretch(column_index, 1)

    def _build_system_group(self):
        group = QGroupBox("\u7cfb\u7edf\u4fe1\u606f", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        fields = (
            ("work_mode", "\u5de5\u88c5\u6a21\u5f0f"),
            ("run_status", "\u8fd0\u884c\u72b6\u6001"),
            ("system_current", "\u7efc\u5408\u7535\u6d41"),
            ("hall_current", "\u970d\u5c14\u7535\u6d41"),
            ("shunt_current", "\u5206\u6d41\u7535\u6d41"),
            ("battery_voltage", "\u7535\u6c60\u603b\u538b"),
            ("system_voltage", "\u7efc\u5408\u603b\u538b"),
            ("pack_voltage", "\u8f93\u51fa\u603b\u538b"),
            ("soc", "\u7cfb\u7edfSOC"),
            ("display_soc", "\u5728\u7ebf\u663e\u793aSOC"),
            ("soh", "\u7cfb\u7edfSOH"),
            ("diff_voltage", "\u5355\u4f53\u538b\u5dee"),
            ("diff_temp", "\u5355\u4f53\u6e29\u5dee"),
            ("avg_voltage", "\u5e73\u5747\u5355\u4f53\u7535\u538b"),
            ("avg_temp", "\u5e73\u5747\u5355\u4f53\u6e29\u5ea6"),
            ("module_count", "\u5728\u7ebf\u6a21\u7ec4\u6570"),
            ("afe_count", "\u6bcf\u6a21\u7ec4AFE"),
            ("online_lecu_num", "\u5728\u7ebfLECU\u6570"),
        )
        self._populate_metric_grid(
            layout,
            group,
            fields,
            columns=2,
            label_width=110,
            value_width=120,
        )
        return group

    def _build_state_group(self):
        group = QGroupBox("\u8f93\u5165 / \u8f93\u51fa\u72b6\u6001", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        di_box = QGroupBox("DI\u8f93\u5165\u72b6\u6001", group)
        di_layout = QGridLayout(di_box)
        di_layout.setHorizontalSpacing(12)
        di_layout.setVerticalSpacing(8)
        di_layout.setContentsMargins(10, 10, 10, 10)
        for index in range(12):
            dot = StateDot(f"DI{index + 1}")
            self.input_dots.append(dot)
            di_layout.addWidget(dot, index // 6, index % 6)
        for column in range(6):
            di_layout.setColumnStretch(column, 1)
        layout.addWidget(di_box)

        output_box = QGroupBox("\u8f93\u51fa\u72b6\u6001", group)
        output_layout = QGridLayout(output_box)
        output_layout.setHorizontalSpacing(12)
        output_layout.setVerticalSpacing(8)
        output_layout.setContentsMargins(10, 10, 10, 10)
        names = [f"HSD{index}" for index in range(1, 9)] + ["LSD1", "LSD2"]
        for index, name in enumerate(names):
            dot = StateDot(name)
            self.output_dots.append(dot)
            output_layout.addWidget(dot, index // 5, index % 5)
        for column in range(5):
            output_layout.setColumnStretch(column, 1)
        layout.addWidget(output_box)
        layout.addStretch(1)
        return group

    def _build_soc_group(self):
        group = QGroupBox("SOC", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.soc_display = QLabel("-- %", group)
        self.soc_display.setObjectName("sectionTitle")
        self.soc_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.soc_display.setStyleSheet(
            "font-size: 30px; font-weight: bold; color: #0f172a;"
            "background: #eef4ff; border: 1px solid #c8dafc; border-radius: 12px;"
            "padding: 18px 12px;"
        )
        layout.addWidget(self.soc_display)

        metrics_widget = QWidget(group)
        metrics_layout = QGridLayout(metrics_widget)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(8)
        extra_fields = (
            ("pure_soc", "\u539f\u59cbSOC"),
            ("revise_soc", "\u4fee\u6b63SOC"),
            ("revise_soc_temp", "\u6e29\u5ea6\u4fee\u6b63SOC"),
            ("fuzzy_soc", "\u6a21\u7ccaSOC"),
            ("cell_max_soc", "\u5355\u4f53\u6700\u9ad8SOC"),
            ("cell_min_soc", "\u5355\u4f53\u6700\u4f4eSOC"),
            ("cell_max_soc_temp", "\u6700\u9ad8SOC\u6e29\u5ea6"),
            ("cell_min_soc_temp", "\u6700\u4f4eSOC\u6e29\u5ea6"),
        )
        self._populate_metric_grid(
            metrics_layout,
            metrics_widget,
            extra_fields,
            columns=2,
            label_width=126,
            value_width=120,
        )
        layout.addWidget(metrics_widget)
        return group

    def _build_extrema_group(self):
        group = QGroupBox("\u6781\u503c\u4fe1\u606f", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        fields = (
            ("max_cell_voltage", "\u6700\u9ad8\u5355\u4f53\u7535\u538b"),
            ("max_cell_voltage_module", "\u6700\u9ad8\u7535\u538b\u6a21\u7ec4"),
            ("max_cell_voltage_index", "\u6700\u9ad8\u7535\u538b\u4f4d\u7f6e"),
            ("min_cell_voltage", "\u6700\u4f4e\u5355\u4f53\u7535\u538b"),
            ("min_cell_voltage_module", "\u6700\u4f4e\u7535\u538b\u6a21\u7ec4"),
            ("min_cell_voltage_index", "\u6700\u4f4e\u7535\u538b\u4f4d\u7f6e"),
            ("max_cell_temp", "\u6700\u9ad8\u5355\u4f53\u6e29\u5ea6"),
            ("max_cell_temp_module", "\u6700\u9ad8\u6e29\u5ea6\u6a21\u7ec4"),
            ("max_cell_temp_index", "\u6700\u9ad8\u6e29\u5ea6\u4f4d\u7f6e"),
            ("min_cell_temp", "\u6700\u4f4e\u5355\u4f53\u6e29\u5ea6"),
            ("min_cell_temp_module", "\u6700\u4f4e\u6e29\u5ea6\u6a21\u7ec4"),
            ("min_cell_temp_index", "\u6700\u4f4e\u6e29\u5ea6\u4f4d\u7f6e"),
        )
        self._populate_metric_grid(
            layout,
            group,
            fields,
            columns=2,
            label_width=110,
            value_width=120,
        )
        return group

    def _build_statistics_group(self):
        group = QGroupBox("\u7edf\u8ba1\u4fe1\u606f", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        fields = (
            ("remaining_discharge_kwh", "\u5269\u4f59\u53ef\u653e\u7535"),
            ("remaining_charge_kwh", "\u5269\u4f59\u53ef\u5145\u7535"),
            ("single_charge_kwh", "\u5355\u6b21\u5145\u7535\u7535\u91cf"),
            ("single_discharge_kwh", "\u5355\u6b21\u653e\u7535\u7535\u91cf"),
            ("total_charge_kwh", "\u7d2f\u8ba1\u5145\u7535\u7535\u91cf"),
            ("total_discharge_kwh", "\u7d2f\u8ba1\u653e\u7535\u7535\u91cf"),
            ("continuous_discharge_power", "\u6700\u5927\u653e\u7535\u529f\u7387"),
            ("continuous_charge_power", "\u6700\u5927\u5145\u7535\u529f\u7387"),
            ("continuous_discharge_current", "\u6700\u5927\u653e\u7535\u7535\u6d41"),
            ("continuous_charge_current", "\u6700\u5927\u5145\u7535\u7535\u6d41"),
            ("hvil_pwm_freq", "HVIL\u9891\u7387"),
            ("hvil_pwm_duty", "HVIL\u5360\u7a7a\u6bd4"),
        )
        self._populate_metric_grid(
            layout,
            group,
            fields,
            columns=2,
            label_width=104,
            value_width=118,
        )
        return group

    def _build_temperature_group(self):
        group = QGroupBox("RT\u6e29\u5ea6", self)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)
        fields = [(f"rt_{index + 1:02d}", f"RT{index + 1:02d}") for index in range(10)] + [
            ("board_temp1", "BCU\u677f\u6e291"),
            ("board_temp2", "BCU\u677f\u6e292"),
        ]
        self._populate_metric_grid(
            layout,
            group,
            fields,
            columns=2,
            label_width=92,
            value_width=96,
        )
        self.rt_fields = [
            self.value_fields[f"rt_{index + 1:02d}"]
            for index in range(10)
        ]
        return group

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = cluster_index
        self.current_address = address
        if cluster_index is None or not address:
            self.cluster_label.setText("\u5f53\u524d\u7c07: -")
            return
        self.cluster_label.setText(
            f"\u5f53\u524d\u7c07: \u7c07{cluster_index} / \u5730\u5740 {address}"
        )

    def set_status_text(self, text):
        self.status_label.setText("" if text is None else str(text))

    def clear_values(self):
        self.soc_display.setText("-- %")
        for widget in self.value_fields.values():
            widget.setText("--")
        for widget in self.rt_fields:
            widget.setText("--")
        for dot in self.input_dots + self.output_dots:
            dot.set_active(None)

    def update_snapshot(self, snapshot):
        if not snapshot:
            self.clear_values()
            return

        work_mode = snapshot.get("work_mode")
        run_status = snapshot.get("run_status")
        self.value_fields["work_mode"].setText(
            "--"
            if work_mode is None
            else f"{work_mode} {WORK_MODE_TEXT.get(work_mode, '')}".strip()
        )
        self.value_fields["run_status"].setText(
            "--"
            if run_status is None
            else f"{run_status} {RUN_STATUS_TEXT.get(run_status, '')}".strip()
        )
        self.value_fields["system_current"].setText(
            _format_scaled(snapshot.get("system_current"), 10, 1, " A")
        )
        self.value_fields["hall_current"].setText(
            _format_scaled(snapshot.get("hall_current"), 10, 1, " A")
        )
        self.value_fields["shunt_current"].setText(
            _format_scaled(snapshot.get("shunt_current"), 10, 1, " A")
        )
        self.value_fields["battery_voltage"].setText(
            _format_scaled(snapshot.get("battery_voltage"), 10, 1, " V")
        )
        self.value_fields["system_voltage"].setText(
            _format_scaled(snapshot.get("system_voltage"), 10, 1, " V")
        )
        self.value_fields["pack_voltage"].setText(
            _format_scaled(snapshot.get("pack_voltage"), 10, 1, " V")
        )
        self.value_fields["soc"].setText(
            _format_scaled(snapshot.get("soc"), 10, 1, " %")
        )
        self.value_fields["display_soc"].setText(
            _format_scaled(snapshot.get("display_soc"), 10, 1, " %")
        )
        self.value_fields["soh"].setText(
            _format_scaled(snapshot.get("soh"), 10, 1, " %")
        )
        self.value_fields["diff_voltage"].setText(
            _format_int(snapshot.get("diff_voltage"), " mV")
        )
        self.value_fields["diff_temp"].setText(
            _format_scaled(snapshot.get("diff_temp"), 10, 1, " C")
        )
        self.value_fields["avg_voltage"].setText(
            _format_int(snapshot.get("avg_voltage"), " mV")
        )
        self.value_fields["avg_temp"].setText(
            _format_scaled(snapshot.get("avg_temp"), 10, 1, " C")
        )
        self.value_fields["module_count"].setText(
            _format_int(snapshot.get("module_count"))
        )
        self.value_fields["afe_count"].setText(_format_int(snapshot.get("afe_count")))
        self.value_fields["online_lecu_num"].setText(
            _format_int(snapshot.get("online_lecu_num"))
        )

        self.soc_display.setText(_format_scaled(snapshot.get("soc"), 10, 1, " %"))
        for key in (
            "pure_soc",
            "revise_soc",
            "revise_soc_temp",
            "fuzzy_soc",
            "cell_max_soc",
            "cell_min_soc",
            "cell_max_soc_temp",
            "cell_min_soc_temp",
        ):
            self.value_fields[key].setText(
                _format_scaled(snapshot.get(key), 10, 1, " %")
            )

        self.value_fields["max_cell_voltage"].setText(
            _format_int(snapshot.get("max_cell_voltage"), " mV")
        )
        self.value_fields["max_cell_voltage_module"].setText(
            _format_int(snapshot.get("max_cell_voltage_module"))
        )
        self.value_fields["max_cell_voltage_index"].setText(
            _format_int(snapshot.get("max_cell_voltage_index"))
        )
        self.value_fields["min_cell_voltage"].setText(
            _format_int(snapshot.get("min_cell_voltage"), " mV")
        )
        self.value_fields["min_cell_voltage_module"].setText(
            _format_int(snapshot.get("min_cell_voltage_module"))
        )
        self.value_fields["min_cell_voltage_index"].setText(
            _format_int(snapshot.get("min_cell_voltage_index"))
        )
        self.value_fields["max_cell_temp"].setText(
            _format_scaled(snapshot.get("max_cell_temp"), 10, 1, " C")
        )
        self.value_fields["max_cell_temp_module"].setText(
            _format_int(snapshot.get("max_cell_temp_module"))
        )
        self.value_fields["max_cell_temp_index"].setText(
            _format_int(snapshot.get("max_cell_temp_index"))
        )
        self.value_fields["min_cell_temp"].setText(
            _format_scaled(snapshot.get("min_cell_temp"), 10, 1, " C")
        )
        self.value_fields["min_cell_temp_module"].setText(
            _format_int(snapshot.get("min_cell_temp_module"))
        )
        self.value_fields["min_cell_temp_index"].setText(
            _format_int(snapshot.get("min_cell_temp_index"))
        )

        self.value_fields["remaining_discharge_kwh"].setText(
            _format_scaled(snapshot.get("remaining_discharge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["remaining_charge_kwh"].setText(
            _format_scaled(snapshot.get("remaining_charge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["single_charge_kwh"].setText(
            _format_scaled(snapshot.get("single_charge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["single_discharge_kwh"].setText(
            _format_scaled(snapshot.get("single_discharge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["total_charge_kwh"].setText(
            _format_scaled(snapshot.get("total_charge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["total_discharge_kwh"].setText(
            _format_scaled(snapshot.get("total_discharge_kwh"), 100, 2, " kWh")
        )
        self.value_fields["continuous_discharge_power"].setText(
            _format_int(snapshot.get("continuous_discharge_power"), " W")
        )
        self.value_fields["continuous_charge_power"].setText(
            _format_int(snapshot.get("continuous_charge_power"), " W")
        )
        self.value_fields["continuous_discharge_current"].setText(
            _format_scaled(snapshot.get("continuous_discharge_current"), 10, 1, " A")
        )
        self.value_fields["continuous_charge_current"].setText(
            _format_scaled(snapshot.get("continuous_charge_current"), 10, 1, " A")
        )
        self.value_fields["hvil_pwm_freq"].setText(
            _format_scaled(snapshot.get("hvil_pwm_freq"), 10, 1, " Hz")
        )
        self.value_fields["hvil_pwm_duty"].setText(
            _format_scaled(snapshot.get("hvil_pwm_duty"), 10, 1, " %")
        )

        self.value_fields["board_temp1"].setText(
            _format_scaled(snapshot.get("board_temp1"), 10, 1, " C")
        )
        self.value_fields["board_temp2"].setText(
            _format_scaled(snapshot.get("board_temp2"), 10, 1, " C")
        )
        for index, value in enumerate(snapshot.get("rt_values", [])):
            if index >= len(self.rt_fields):
                break
            self.rt_fields[index].setText(_format_scaled(value, 10, 1, " C"))

        for dot, state in zip(self.input_dots, snapshot.get("di_states", [])):
            dot.set_active(state)
        for dot, state in zip(self.output_dots, snapshot.get("relay_states", [])):
            dot.set_active(state)
