from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from application.index_catalog import IndexCatalog
from .conf import config
from .index_browser_dialog import IndexBrowserDialog


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
    def __init__(self, index_catalog=None, runtime_config=None):
        super().__init__()
        self.runtime_config = runtime_config if runtime_config is not None else config
        self.index_catalog = index_catalog or IndexCatalog.load_default()
        self.current_cluster_index = None
        self.current_address = None
        self.index_edits = []
        self.index_hex_labels = []
        self.index_value_edits = []
        self.index_name_labels = []
        self.index_resolutions = []
        self.index_raw_values = []
        self._index_edit_rows = {}
        self.active_index_row = 0
        self._index_browser_dialog = None
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

        self.body_scroll = QScrollArea(self)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setWidgetResizable(True)
        root.addWidget(self.body_scroll, 1)

        body_content = QWidget(self.body_scroll)
        # Preserve readable control widths on compact displays; the surrounding
        # scroll area provides horizontal access instead of squeezing fields.
        body_content.setMinimumWidth(1220)
        body = QHBoxLayout(body_content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        body.addWidget(self._build_index_group(), stretch=4)
        body.addWidget(self._build_output_group(), stretch=3)
        body.addWidget(self._build_parameter_group(), stretch=4)
        self.body_scroll.setWidget(body_content)

    def _build_index_group(self):
        group = QGroupBox("请求索引读写", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        self.read_indexes_button = QPushButton("读取索引", group)
        self.write_indexes_button = QPushButton("写入索引", group)
        self.browse_indexes_button = QPushButton("浏览索引", group)
        self.browse_indexes_button.setToolTip("搜索下位机索引定义或导入自定义索引配置")
        buttons.addWidget(self.read_indexes_button)
        buttons.addWidget(self.write_indexes_button)
        buttons.addWidget(self.browse_indexes_button)
        layout.addLayout(buttons)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("名称", group), 0, 0)
        grid.addWidget(QLabel("索引", group), 0, 1)
        grid.addWidget(QLabel("HEX", group), 0, 2)
        grid.addWidget(QLabel("原始值", group), 0, 3)

        for row in range(10):
            name_label = QLabel(f"索引{row + 1}", group)
            name_label.setMinimumWidth(116)
            name_label.setToolTip("")
            self.index_name_labels.append(name_label)
            self.index_resolutions.append(None)
            self.index_raw_values.append("")
            grid.addWidget(name_label, row + 1, 0)

            index_edit = QLineEdit(DEFAULT_REQUEST_INDEXES[row], group)
            index_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            index_edit.textChanged.connect(
                lambda _text, row_index=row: self._on_index_text_changed(row_index)
            )
            index_edit.installEventFilter(self)
            self._index_edit_rows[index_edit] = row
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

            self._on_index_text_changed(row)

        layout.addLayout(grid)

        self.index_detail_panel = QFrame(group)
        self.index_detail_panel.setObjectName("indexDetailPanel")
        detail_layout = QVBoxLayout(self.index_detail_panel)
        detail_layout.setContentsMargins(10, 8, 10, 8)
        detail_layout.setSpacing(3)
        self.index_detail_title = QLabel("索引详情", self.index_detail_panel)
        self.index_detail_title.setObjectName("sectionTitle")
        self.index_detail_meta = QLabel("", self.index_detail_panel)
        self.index_detail_meta.setObjectName("sectionHint")
        self.index_detail_meta.setWordWrap(True)
        self.index_detail_description = QLabel("", self.index_detail_panel)
        self.index_detail_description.setWordWrap(True)
        self.index_detail_value = QLabel("", self.index_detail_panel)
        self.index_detail_value.setObjectName("contextLabel")
        self.index_detail_value.setWordWrap(True)
        detail_layout.addWidget(self.index_detail_title)
        detail_layout.addWidget(self.index_detail_meta)
        detail_layout.addWidget(self.index_detail_description)
        detail_layout.addWidget(self.index_detail_value)
        layout.addWidget(self.index_detail_panel)
        self.browse_indexes_button.clicked.connect(self.open_index_browser)
        self._show_index_detail(0)
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

    def _on_index_text_changed(self, row_index):
        self._update_index_hex_label(row_index)
        self._update_index_resolution(row_index)

    def _update_index_resolution(self, row_index):
        text = self.index_edits[row_index].text().strip()
        resolution = None
        if text:
            try:
                data_id = int(text, 0)
            except ValueError:
                data_id = None
            if data_id is not None and self.index_catalog is not None:
                resolution = self.index_catalog.resolve(data_id, self.runtime_config)
        self.index_resolutions[row_index] = resolution

        label = self.index_name_labels[row_index]
        if not text:
            label.setText(f"索引{row_index + 1}")
            label.setToolTip("")
            label.setStyleSheet("")
        elif resolution is None or not resolution.known:
            label.setText("未识别索引")
            label.setToolTip("" if resolution is None else resolution.description)
            label.setStyleSheet("color: #b42318;")
        else:
            label.setText(
                label.fontMetrics().elidedText(
                    resolution.short_name,
                    Qt.TextElideMode.ElideRight,
                    150,
                )
            )
            label.setToolTip(
                f"{resolution.symbol}\n{resolution.description}\n"
                f"{resolution.category_label} / {resolution.type_label} / {resolution.access_label}"
            )
            label.setStyleSheet("")
        if row_index == self.active_index_row:
            self._show_index_detail(row_index)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn and watched in self._index_edit_rows:
            self.active_index_row = self._index_edit_rows[watched]
            self._show_index_detail(self.active_index_row)
        return super().eventFilter(watched, event)

    def _show_index_detail(self, row_index):
        if not hasattr(self, "index_detail_title"):
            return
        resolution = self.index_resolutions[row_index]
        text = self.index_edits[row_index].text().strip()
        raw_text = self.index_raw_values[row_index]
        if not text:
            self.index_detail_title.setText(f"索引{row_index + 1}: 未填写")
            self.index_detail_meta.setText("")
            self.index_detail_description.setText("")
            self.index_detail_value.setText("")
            return
        if resolution is None:
            self.index_detail_title.setText(f"索引{row_index + 1}: 输入格式错误")
            self.index_detail_meta.setText("")
            self.index_detail_description.setText("请输入十进制或以 0x 开头的十六进制索引。")
            self.index_detail_value.setText("")
            return
        self.index_detail_title.setText(
            f"{resolution.data_id} / {resolution.hex_id}    {resolution.short_name}"
        )
        custom = "    自定义" if resolution.custom else ""
        self.index_detail_meta.setText(
            f"{resolution.symbol}    {resolution.category_label}    "
            f"{resolution.type_label}    单位 {resolution.display_unit or resolution.unit or '--'}    "
            f"{resolution.access_label}{custom}"
        )
        source = f"    来源 {resolution.source_label}" if resolution.source_label else ""
        self.index_detail_description.setText(f"{resolution.description or '--'}{source}")
        if not raw_text:
            self.index_detail_value.setText("读取值: --")
            return
        try:
            raw_value = int(str(raw_text).strip(), 0)
        except ValueError:
            self.index_detail_value.setText(f"读取值: {raw_text}")
            return
        self.index_detail_value.setText(
            f"原始值 {raw_value} / 0x{raw_value & 0xFFFF:04X}    "
            f"解析值 {resolution.format_physical_value(raw_value)}"
        )

    def create_index_browser_dialog(self):
        if self.index_catalog is None or self.index_catalog.is_empty:
            return None
        dialog = IndexBrowserDialog(self.index_catalog, self.runtime_config, parent=self)
        dialog.indexSelected.connect(self._apply_browser_selection)
        dialog.catalogChanged.connect(self._refresh_index_resolutions)
        current_text = self.index_edits[self.active_index_row].text().strip()
        if current_text and current_text != "0":
            dialog.set_initial_query(current_text)
        return dialog

    def open_index_browser(self):
        dialog = self.create_index_browser_dialog()
        if dialog is None:
            self.set_status_text("索引目录不可用，请检查发布资源 index_catalog.json。", failed=True)
            return
        self._index_browser_dialog = dialog
        dialog.exec()

    def _apply_browser_selection(self, data_id):
        edit = self.index_edits[self.active_index_row]
        edit.setText(str(int(data_id)))
        edit.setFocus()
        edit.selectAll()

    def _refresh_index_resolutions(self):
        for row_index in range(len(self.index_edits)):
            self._update_index_resolution(row_index)

    def get_index_resolution(self, row_index):
        return self.index_resolutions[int(row_index)]

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
        value_text = "" if value_text is None else str(value_text)
        self.index_raw_values[row_index] = value_text
        self.index_value_edits[row_index].setText(value_text)
        if row_index == self.active_index_row:
            self._show_index_detail(row_index)

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
