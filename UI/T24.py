from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


DEFAULT_REQUEST_INDEXES = ("0",) * 10


def _readonly_edit(width=96):
    widget = QLineEdit()
    widget.setReadOnly(True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(width)
    return widget


def _editable_edit(width=96):
    widget = QLineEdit()
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(width)
    return widget


def _make_spinbox(maximum=65535):
    widget = QSpinBox()
    widget.setRange(0, maximum)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget


def _format_scaled(value, divisor=1.0, digits=1, suffix=""):
    if value is None:
        return "--"
    scaled = float(value) / float(divisor)
    text = f"{scaled:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}{suffix}"


class HostControlPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = None
        self.index_edits = []
        self.index_hex_labels = []
        self.index_value_edits = []
        self.channel_checks = {}
        self._build_ui()
        self.update_snapshot({})

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("主机控制", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        root.addWidget(self.cluster_label)

        self.status_label = QLabel("索引读取与主机控制均通过请求索引/诊断命令执行。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, stretch=1)

        body.addWidget(self._build_index_group(), stretch=4)
        body.addWidget(self._build_output_group(), stretch=3)
        body.addWidget(self._build_parameter_group(), stretch=4)

    def _build_index_group(self):
        group = QGroupBox("请求索引读写", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        self.read_indexes_button = QPushButton("读取索引", group)
        self.write_indexes_button = QPushButton("写入索引", group)
        buttons.addWidget(self.read_indexes_button)
        buttons.addWidget(self.write_indexes_button)
        layout.addLayout(buttons)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("名称", group), 0, 0)
        grid.addWidget(QLabel("索引", group), 0, 1)
        grid.addWidget(QLabel("HEX", group), 0, 2)
        grid.addWidget(QLabel("值", group), 0, 3)

        for row in range(10):
            grid.addWidget(QLabel(f"索引{row + 1}", group), row + 1, 0)

            index_edit = QLineEdit(DEFAULT_REQUEST_INDEXES[row], group)
            index_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            index_edit.textChanged.connect(
                lambda _text, row_index=row: self._update_index_hex_label(row_index)
            )
            self.index_edits.append(index_edit)
            grid.addWidget(index_edit, row + 1, 1)

            hex_label = QLabel("--", group)
            hex_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.index_hex_labels.append(hex_label)
            grid.addWidget(hex_label, row + 1, 2)

            value_edit = _editable_edit(110)
            value_edit.setStyleSheet("background-color: #f0fff0;")
            self.index_value_edits.append(value_edit)
            grid.addWidget(value_edit, row + 1, 3)

            self._update_index_hex_label(row)

        layout.addLayout(grid)
        layout.addStretch(1)
        return group

    def _build_output_group(self):
        group = QGroupBox("高低边控制", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.work_mode_label = QLabel("工装模式: --", group)
        self.work_mode_label.setStyleSheet("font-weight: 800;")
        layout.addWidget(self.work_mode_label)

        outputs_box = QGroupBox("输出控制", group)
        outputs_layout = QGridLayout(outputs_box)
        outputs_layout.setHorizontalSpacing(12)
        outputs_layout.setVerticalSpacing(8)

        names = [f"HSD{index}" for index in range(1, 9)] + ["LSD1", "LSD2"]
        for channel_id, name in enumerate(names, start=1):
            checkbox = QCheckBox(name, outputs_box)
            self.channel_checks[channel_id] = checkbox
            outputs_layout.addWidget(checkbox, (channel_id - 1) % 5, (channel_id - 1) // 5)

        layout.addWidget(outputs_box)

        self.restore_product_info_button = QPushButton("恢复产品信息", group)
        self.sync_time_button = QPushButton("同步系统时间", group)
        layout.addWidget(self.restore_product_info_button)
        layout.addWidget(self.sync_time_button)
        layout.addStretch(1)
        return group

    def _build_parameter_group(self):
        group = QGroupBox("参数写入", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        hvil_group = QGroupBox("HVIL PWM", group)
        hvil_layout = QGridLayout(hvil_group)
        hvil_layout.setHorizontalSpacing(8)
        hvil_layout.setVerticalSpacing(8)

        self.hvil_freq_current = _readonly_edit()
        self.hvil_duty_current = _readonly_edit()
        self.hvil_freq_target = _make_spinbox()
        self.hvil_duty_target = _make_spinbox()
        self.write_hvil_button = QPushButton("写入PWM", hvil_group)

        hvil_layout.addWidget(QLabel("当前频率", hvil_group), 0, 0)
        hvil_layout.addWidget(self.hvil_freq_current, 0, 1)
        hvil_layout.addWidget(QLabel("当前占空比", hvil_group), 1, 0)
        hvil_layout.addWidget(self.hvil_duty_current, 1, 1)
        hvil_layout.addWidget(QLabel("目标频率", hvil_group), 2, 0)
        hvil_layout.addWidget(self.hvil_freq_target, 2, 1)
        hvil_layout.addWidget(QLabel("目标占空比", hvil_group), 3, 0)
        hvil_layout.addWidget(self.hvil_duty_target, 3, 1)
        hvil_layout.addWidget(self.write_hvil_button, 4, 0, 1, 2)
        layout.addWidget(hvil_group)

        soc_group = QGroupBox("SOC设置", group)
        soc_layout = QGridLayout(soc_group)
        soc_layout.setHorizontalSpacing(8)
        soc_layout.setVerticalSpacing(8)

        self.soc_current = _readonly_edit()
        self.soc_target = _make_spinbox()
        self.write_soc_button = QPushButton("设置SOC", soc_group)
        soc_layout.addWidget(QLabel("当前SOC", soc_group), 0, 0)
        soc_layout.addWidget(self.soc_current, 0, 1)
        soc_layout.addWidget(QLabel("目标SOC", soc_group), 1, 0)
        soc_layout.addWidget(self.soc_target, 1, 1)
        soc_layout.addWidget(self.write_soc_button, 2, 0, 1, 2)
        layout.addWidget(soc_group)

        self.restore_run_button = QPushButton("恢复全局运行参数", group)
        self.restore_factory_button = QPushButton("恢复全站出厂参数", group)
        self.save_flash_button = QPushButton("保存参数到FLASH", group)
        layout.addWidget(self.restore_run_button)
        layout.addWidget(self.restore_factory_button)
        layout.addWidget(self.save_flash_button)

        layout.addStretch(1)
        return group

    def _update_index_hex_label(self, row_index):
        text = self.index_edits[row_index].text().strip()
        if not text:
            self.index_hex_labels[row_index].setText("--")
            return
        try:
            data_id = int(text, 0)
        except ValueError:
            self.index_hex_labels[row_index].setText("ERR")
            return
        self.index_hex_labels[row_index].setText(f"0x{data_id:X}")

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = cluster_index
        self.current_address = address
        if cluster_index is None or not address:
            self.cluster_label.setText("当前簇: -")
            return
        self.cluster_label.setText(f"当前簇: 簇{cluster_index} / 地址 {address}")

    def set_status_text(self, text, failed=False):
        self.status_label.setText("" if text is None else str(text))
        self.status_label.setProperty("status", "danger" if failed else "info")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def get_request_indexes(self):
        result = []
        for row_index, edit in enumerate(self.index_edits, start=1):
            text = edit.text().strip()
            if not text:
                result.append(None)
                continue
            try:
                result.append(int(text, 0))
            except ValueError as exc:
                raise ValueError(f"索引{row_index} 不是有效的十进制或十六进制数值。") from exc
        return result

    def get_request_write_entries(self):
        indexes = self.get_request_indexes()
        result = []
        for row_index, (data_id, value_edit) in enumerate(
            zip(indexes, self.index_value_edits),
            start=1,
        ):
            value_text = value_edit.text().strip()
            if not value_text:
                continue
            if data_id is None:
                raise ValueError(f"索引{row_index} 未填写索引，无法写入数值。")
            try:
                value = int(value_text, 0)
            except ValueError as exc:
                raise ValueError(f"索引{row_index} 的值不是有效的十进制或十六进制数值。") from exc
            result.append((row_index - 1, data_id, value))
        return result

    def set_request_value(self, row_index, data_id, value_text):
        self.index_hex_labels[row_index].setText(
            "--" if data_id is None else f"0x{int(data_id):X}"
        )
        self.index_value_edits[row_index].setText("" if value_text is None else str(value_text))

    def set_channel_states(self, states):
        for channel_id, checkbox in self.channel_checks.items():
            desired = False
            if states and channel_id - 1 < len(states):
                desired = bool(states[channel_id - 1])
            checkbox.blockSignals(True)
            checkbox.setChecked(desired)
            checkbox.blockSignals(False)

    def update_snapshot(self, snapshot):
        snapshot = snapshot or {}
        work_mode = snapshot.get("work_mode")
        if work_mode is None:
            self.work_mode_label.setText("工装模式: --")
        elif int(work_mode) == 1:
            self.work_mode_label.setText("工装模式: 开")
        else:
            self.work_mode_label.setText("工装模式: 关")

        self.hvil_freq_current.setText(
            _format_scaled(snapshot.get("hvil_pwm_freq"), 10, 1, " Hz")
        )
        self.hvil_duty_current.setText(
            _format_scaled(snapshot.get("hvil_pwm_duty"), 10, 1, " %")
        )
        self.soc_current.setText(_format_scaled(snapshot.get("soc"), 10, 1, " %"))
        self.set_channel_states(snapshot.get("relay_states", []))


Ui_Form = HostControlPage
