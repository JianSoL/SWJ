from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .conf import config


ALARM_PARAMETER_FIELDS = (
    ("level1", "一级告警", 0, True, True),
    ("level2", "二级告警", 1, True, True),
    ("level3", "三级告警", 2, True, True),
    ("level4", "四级告警", 3, True, True),
    ("level5", "五级告警", 4, True, True),
    ("hysteresis1", "一级回差", 5, False, True),
    ("hysteresis2", "二级回差", 6, False, True),
    ("hysteresis3", "三级回差", 7, False, True),
    ("hysteresis4", "四级回差", 8, False, True),
    ("hysteresis5", "五级回差", 9, False, True),
    ("alarm_on_delay1", "一级产生延时", 10, False, False),
    ("alarm_on_delay2", "二级产生延时", 11, False, False),
    ("alarm_on_delay3", "三级产生延时", 12, False, False),
    ("alarm_on_delay4", "四级产生延时", 13, False, False),
    ("alarm_on_delay5", "五级产生延时", 14, False, False),
    ("alarm_off_delay1", "一级消除延时", 15, False, False),
    ("alarm_off_delay2", "二级消除延时", 16, False, False),
    ("alarm_off_delay3", "三级消除延时", 17, False, False),
    ("alarm_off_delay4", "四级消除延时", 18, False, False),
    ("alarm_off_delay5", "五级消除延时", 19, False, False),
    ("relay_mask", "继电器关联", 20, False, False),
    ("relay_on_delay1", "一级继电器延时", 21, False, False),
    ("relay_on_delay2", "二级继电器延时", 22, False, False),
    ("relay_on_delay3", "三级继电器延时", 23, False, False),
    ("derate1", "一级降额", 24, False, False),
    ("derate2", "二级降额", 25, False, False),
    ("derate3", "三级降额", 26, False, False),
    ("derate4", "四级降额", 27, False, False),
    ("derate5", "五级降额", 28, False, False),
    ("display_level", "告警使能", 29, False, False),
)

ALARM_FIELDS_BY_KEY = {
    key: {
        "label": label,
        "index": index,
        "signed": signed,
        "summary": summary,
    }
    for key, label, index, signed, summary in ALARM_PARAMETER_FIELDS
}
SUMMARY_FIELDS = [
    (key, label)
    for key, label, _index, _signed, summary in ALARM_PARAMETER_FIELDS
    if summary
]


def _decode_signed_u16(value):
    value = int(value) & 0xFFFF
    if value & 0x8000:
        return value - 0x10000
    return value


def _encode_u16(value):
    return int(value) & 0xFFFF


def _spin_box(minimum, maximum):
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(82)
    return widget


def _field_label(text, tooltip=None, alignment=None):
    label = QLabel(text)
    label.setWordWrap(True)
    if tooltip:
        label.setToolTip(tooltip)
    if alignment is not None:
        label.setAlignment(alignment)
    return label


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.alarm_definitions = self._build_alarm_definitions()
        self.summary_items = {}
        self.record_cache = {}
        self.current_record_complete = False
        self._ignore_selection = False
        self._build_ui()
        self._populate_alarm_rows()
        self.alarm_table.itemSelectionChanged.connect(self.on_table_selection_changed)

    @staticmethod
    def default_status_text():
        return (
            "使用顶部“当前簇”选择目标簇后点击“读取告警参数”。左侧表格显示阈值/回差摘要，"
            "选中告警后可在右侧修改完整参数并写入当前告警。"
        )

    def _build_alarm_definitions(self):
        definitions = []
        alarm_name_map = config.get("Alarm_name_key", {})
        for alarm_id, (name, enabled) in enumerate(alarm_name_map.items()):
            definitions.append(
                {
                    "alarm_id": alarm_id,
                    "code": f"{alarm_id + 1:03d}",
                    "name": str(name),
                    "enabled": bool(enabled),
                }
            )
        return definitions

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        title = QLabel("告警参数", self)
        title.setObjectName("pageTitle")
        root_layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.cluster_caption = _field_label("目标簇")
        self.cluster_caption.hide()
        self.comboBox = QComboBox(self)
        for index, address in enumerate(config.get("ADDRESLIST", [])):
            if index == 0:
                label = f"00 / {address}"
            else:
                label = f"簇{index} / {address}"
            self.comboBox.addItem(label)
        self.comboBox.hide()

        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        self.cluster_label.hide()
        toolbar.addStretch(1)

        self.button = QPushButton("读取告警参数", self)
        toolbar.addWidget(self.button)

        self.modify_button = QPushButton("写入选中告警", self)
        self.modify_button.setObjectName("primaryButton")
        toolbar.addWidget(self.modify_button)

        self.submit_button = QPushButton("保存参数到FLASH", self)
        toolbar.addWidget(self.submit_button)

        self.read_summary_button = self.button
        self.write_current_button = self.modify_button
        self.save_flash_button = self.submit_button
        root_layout.addLayout(toolbar)

        self.status_label = QLabel(self.default_status_text(), self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        list_panel = QWidget(splitter)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        list_layout.addWidget(_field_label("告警列表"))

        self.alarm_table = QTableWidget(list_panel)
        self.table_widget = self.alarm_table
        self.alarm_table.setColumnCount(2 + len(SUMMARY_FIELDS))
        self.alarm_table.setHorizontalHeaderLabels(
            ["序号", "告警名称"] + [label for _key, label in SUMMARY_FIELDS]
        )
        self.alarm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.alarm_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.alarm_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.alarm_table.verticalHeader().setVisible(False)
        self.alarm_table.setAlternatingRowColors(True)
        self.alarm_table.horizontalHeader().setDefaultSectionSize(92)
        self.alarm_table.horizontalHeader().setStretchLastSection(True)
        self.alarm_table.setColumnWidth(0, 60)
        self.alarm_table.setColumnWidth(1, 220)
        list_layout.addWidget(self.alarm_table)
        splitter.addWidget(list_panel)

        detail_scroll = QScrollArea(splitter)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail_root = QWidget(detail_scroll)
        detail_layout = QVBoxLayout(detail_root)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        current_group = QGroupBox("当前告警", detail_root)
        current_layout = QVBoxLayout(current_group)
        self.selected_alarm_label = QLabel("未选择告警", current_group)
        self.selected_alarm_label.setObjectName("sectionTitle")
        current_layout.addWidget(self.selected_alarm_label)
        self.alarm_id_label = QLabel("告警ID / u16AlarmId: -", current_group)
        self.alarm_id_label.setObjectName("sectionHint")
        current_layout.addWidget(self.alarm_id_label)
        detail_layout.addWidget(current_group)

        section_grid = QGridLayout()
        section_grid.setHorizontalSpacing(12)
        section_grid.setVerticalSpacing(12)

        self.summary_group = QGroupBox("阈值与回差", detail_root)
        summary_layout = QGridLayout(self.summary_group)
        summary_layout.setHorizontalSpacing(8)
        summary_layout.setVerticalSpacing(8)
        self.level_boxes = {}
        self.hysteresis_boxes = {}
        for level in range(1, 6):
            summary_layout.addWidget(_field_label(f"{level}级告警", f"s16Level{level}"), level - 1, 0)
            self.level_boxes[level] = _spin_box(-32768, 32767)
            summary_layout.addWidget(self.level_boxes[level], level - 1, 1)
            summary_layout.addWidget(_field_label(f"{level}级回差", f"u16Hysteresis_{level}"), level - 1, 2)
            self.hysteresis_boxes[level] = _spin_box(0, 65535)
            summary_layout.addWidget(self.hysteresis_boxes[level], level - 1, 3)
        section_grid.addWidget(self.summary_group, 0, 0)

        self.delay_group = QGroupBox("延时参数", detail_root)
        delay_layout = QGridLayout(self.delay_group)
        delay_layout.setHorizontalSpacing(8)
        delay_layout.setVerticalSpacing(8)
        self.alarm_on_delay_boxes = {}
        self.alarm_off_delay_boxes = {}
        self.relay_on_delay_boxes = {}
        for level in range(1, 6):
            delay_layout.addWidget(_field_label(f"{level}级产生延时", f"u16AlarmOnDelay{level}"), level - 1, 0)
            self.alarm_on_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.alarm_on_delay_boxes[level], level - 1, 1)
            delay_layout.addWidget(_field_label(f"{level}级消除延时", f"u16AlarmOffDelay{level}"), level - 1, 2)
            self.alarm_off_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.alarm_off_delay_boxes[level], level - 1, 3)
        for level in range(1, 4):
            delay_layout.addWidget(_field_label(f"{level}级继电器延时", f"u16RelayOnDelay{level}"), level - 1, 4)
            self.relay_on_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.relay_on_delay_boxes[level], level - 1, 5)
        section_grid.addWidget(self.delay_group, 0, 1)

        self.option_group = QGroupBox("降额 / 使能 / 继电器关联", detail_root)
        option_layout = QGridLayout(self.option_group)
        option_layout.setHorizontalSpacing(10)
        option_layout.setVerticalSpacing(8)
        headers = ["级别", "充电降额", "放电降额", "使能", "放电关联", "断路器关联", "充电关联"]
        for col, text in enumerate(headers):
            option_layout.addWidget(_field_label(text, alignment=Qt.AlignmentFlag.AlignCenter), 0, col)

        self.derate_charge_boxes = {}
        self.derate_discharge_boxes = {}
        self.display_level_checks = {}
        self.relay_checks = {}
        relay_names = ("discharge", "breaker", "charge")
        for level in range(1, 6):
            option_layout.addWidget(_field_label(f"{level}级"), level, 0)
            self.derate_charge_boxes[level] = _spin_box(0, 255)
            option_layout.addWidget(self.derate_charge_boxes[level], level, 1)
            self.derate_discharge_boxes[level] = _spin_box(0, 255)
            option_layout.addWidget(self.derate_discharge_boxes[level], level, 2)
            self.display_level_checks[level] = QCheckBox("", self.option_group)
            option_layout.addWidget(self.display_level_checks[level], level, 3, Qt.AlignmentFlag.AlignCenter)
            for offset, relay_name in enumerate(relay_names):
                checkbox = QCheckBox("", self.option_group)
                checkbox.setEnabled(level <= 3)
                option_layout.addWidget(checkbox, level, 4 + offset, Qt.AlignmentFlag.AlignCenter)
                self.relay_checks[(level, relay_name)] = checkbox
        section_grid.addWidget(self.option_group, 1, 0, 1, 2)

        detail_layout.addLayout(section_grid)
        detail_layout.addStretch(1)
        detail_scroll.setWidget(detail_root)
        splitter.addWidget(detail_scroll)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 7)
        root_layout.addWidget(splitter, 1)
        self._set_record_complete(False)

    def _populate_alarm_rows(self):
        self.alarm_table.setRowCount(len(self.alarm_definitions))
        for row, definition in enumerate(self.alarm_definitions):
            code_item = QTableWidgetItem(definition["code"])
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item = QTableWidgetItem(definition["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if not definition["enabled"]:
                code_item.setBackground(QColor(224, 229, 236))
                name_item.setBackground(QColor(224, 229, 236))
            self.alarm_table.setItem(row, 0, code_item)
            self.alarm_table.setItem(row, 1, name_item)
            self.summary_items[row] = {}
            for col, (key, _label) in enumerate(SUMMARY_FIELDS, start=2):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if not definition["enabled"]:
                    item.setBackground(QColor(224, 229, 236))
                self.alarm_table.setItem(row, col, item)
                self.summary_items[row][key] = item

    def alarm_count(self):
        return len(self.alarm_definitions)

    def set_cluster_context(self, cluster_index=None, address=None):
        if cluster_index is None:
            cluster_index = self.comboBox.currentIndex()
        if address is None and 0 <= cluster_index < len(config.get("ADDRESLIST", [])):
            address = config["ADDRESLIST"][cluster_index]
        if cluster_index == 0:
            text = f"当前簇: 00 / 地址 {address}"
        else:
            text = f"当前簇: 簇{cluster_index} / 地址 {address}"
        self.cluster_label.setText(text)

    def set_status_text(self, text):
        self.status_label.setText("" if text is None else str(text))

    def clear_cached_values(self):
        self.record_cache.clear()
        for summary_map in self.summary_items.values():
            for item in summary_map.values():
                item.setText("")
        self.clear_detail()

    def clear_detail(self):
        self.current_record_complete = False
        self.selected_alarm_label.setText("未选择告警")
        self.alarm_id_label.setText("告警ID / u16AlarmId: -")
        for level in range(1, 6):
            self.level_boxes[level].setValue(0)
            self.hysteresis_boxes[level].setValue(0)
            self.alarm_on_delay_boxes[level].setValue(0)
            self.alarm_off_delay_boxes[level].setValue(0)
            self.derate_charge_boxes[level].setValue(0)
            self.derate_discharge_boxes[level].setValue(0)
            self.display_level_checks[level].setChecked(False)
        for level in range(1, 4):
            self.relay_on_delay_boxes[level].setValue(0)
        for checkbox in self.relay_checks.values():
            checkbox.setChecked(False)
        self._set_record_complete(False)

    def has_complete_current_record(self):
        return self.current_record_complete

    def _set_record_complete(self, complete):
        self.current_record_complete = bool(complete)
        self.delay_group.setEnabled(self.current_record_complete)
        self.option_group.setEnabled(self.current_record_complete)

    def current_alarm_id(self):
        selected = self.alarm_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self.alarm_definitions):
            return row
        return None

    def select_alarm(self, alarm_id):
        alarm_id = int(alarm_id)
        if not (0 <= alarm_id < len(self.alarm_definitions)):
            return
        self._ignore_selection = True
        self.alarm_table.selectRow(alarm_id)
        self._ignore_selection = False
        self._apply_cached_or_empty_detail(alarm_id)

    def on_table_selection_changed(self):
        if self._ignore_selection:
            return
        alarm_id = self.current_alarm_id()
        if alarm_id is None:
            return
        self._apply_cached_or_empty_detail(alarm_id)

    def _apply_cached_or_empty_detail(self, alarm_id):
        definition = self.alarm_definitions[alarm_id]
        values = self.record_cache.get(alarm_id)
        if values is None:
            self.clear_detail()
            self.selected_alarm_label.setText(f"{definition['code']} {definition['name']} - 未读取")
            self.alarm_id_label.setText(f"告警ID / u16AlarmId: {alarm_id} / 序号 {definition['code']}")
            return
        self._apply_values_to_detail(alarm_id, values)

    def _decode_field_value(self, key, raw_value):
        field = ALARM_FIELDS_BY_KEY[key]
        if field["signed"]:
            return _decode_signed_u16(raw_value)
        return int(raw_value) & 0xFFFF

    def update_alarm_row(self, row, raw_values):
        if row < 0 or row >= len(self.alarm_definitions):
            return
        values = {}
        for key, _label, field_index, _signed, _summary in ALARM_PARAMETER_FIELDS:
            raw_value = raw_values[field_index] if field_index < len(raw_values) else 0
            values[key] = self._decode_field_value(key, raw_value)
        self.record_cache[row] = values
        for key, item in self.summary_items.get(row, {}).items():
            item.setText(str(values.get(key, "")))
        if self.current_alarm_id() == row:
            self._apply_values_to_detail(row, values)

    def _apply_values_to_detail(self, alarm_id, values):
        definition = self.alarm_definitions[alarm_id]
        self.selected_alarm_label.setText(f"{definition['code']} {definition['name']}")
        self.alarm_id_label.setText(f"告警ID / u16AlarmId: {alarm_id} / 序号 {definition['code']}")
        for level in range(1, 6):
            self.level_boxes[level].setValue(int(values.get(f"level{level}", 0)))
            self.hysteresis_boxes[level].setValue(int(values.get(f"hysteresis{level}", 0)))
            self.alarm_on_delay_boxes[level].setValue(int(values.get(f"alarm_on_delay{level}", 0)))
            self.alarm_off_delay_boxes[level].setValue(int(values.get(f"alarm_off_delay{level}", 0)))
            derate_value = int(values.get(f"derate{level}", 0)) & 0xFFFF
            self.derate_charge_boxes[level].setValue((derate_value >> 8) & 0xFF)
            self.derate_discharge_boxes[level].setValue(derate_value & 0xFF)
        for level in range(1, 4):
            self.relay_on_delay_boxes[level].setValue(int(values.get(f"relay_on_delay{level}", 0)))
        display_level = int(values.get("display_level", 0))
        for level in range(1, 6):
            self.display_level_checks[level].setChecked(bool(display_level & (1 << (level - 1))))
        relay_mask = int(values.get("relay_mask", 0))
        relay_names = ("discharge", "breaker", "charge")
        for level in range(1, 4):
            bit_base = (level - 1) * 4
            for offset, relay_name in enumerate(relay_names):
                self.relay_checks[(level, relay_name)].setChecked(bool(relay_mask & (1 << (bit_base + offset))))
        self._set_record_complete(True)

    def build_current_record_values(self):
        alarm_id = self.current_alarm_id()
        if alarm_id is None:
            return None, {}
        values = {}
        for level in range(1, 6):
            values[f"level{level}"] = self.level_boxes[level].value()
            values[f"hysteresis{level}"] = self.hysteresis_boxes[level].value()
            values[f"alarm_on_delay{level}"] = self.alarm_on_delay_boxes[level].value()
            values[f"alarm_off_delay{level}"] = self.alarm_off_delay_boxes[level].value()
            values[f"derate{level}"] = (
                (self.derate_charge_boxes[level].value() & 0xFF) << 8
            ) | (self.derate_discharge_boxes[level].value() & 0xFF)
        relay_mask = 0
        relay_names = ("discharge", "breaker", "charge")
        for level in range(1, 4):
            values[f"relay_on_delay{level}"] = self.relay_on_delay_boxes[level].value()
            bit_base = (level - 1) * 4
            for offset, relay_name in enumerate(relay_names):
                if self.relay_checks[(level, relay_name)].isChecked():
                    relay_mask |= 1 << (bit_base + offset)
        values["relay_mask"] = relay_mask
        display_level = 0
        for level in range(1, 6):
            if self.display_level_checks[level].isChecked():
                display_level |= 1 << (level - 1)
        values["display_level"] = display_level
        return alarm_id, values

    def build_current_raw_fields(self):
        alarm_id, values = self.build_current_record_values()
        if alarm_id is None:
            return None, {}
        raw_fields = {}
        for key, field in ALARM_FIELDS_BY_KEY.items():
            if key not in values:
                continue
            raw_fields[field["index"]] = _encode_u16(values[key])
        return alarm_id, raw_fields

    def setItem(self, row, col, con):
        if row < 0 or row >= len(self.alarm_definitions):
            return
        if col == 0:
            item = self.alarm_table.item(row, 1)
            if item is not None:
                item.setText(str(con))
            return
        summary_key_by_col = {
            1: "level1",
            2: "level2",
            3: "level3",
            4: "level4",
            5: "level5",
            6: "hysteresis1",
            7: "hysteresis2",
            8: "hysteresis3",
            9: "hysteresis4",
            10: "hysteresis5",
        }
        key = summary_key_by_col.get(col)
        if key is None:
            return
        item = self.summary_items.get(row, {}).get(key)
        if item is not None:
            item.setText(str(con))

    def change_row_color(self, row_index, color):
        if row_index < 0 or row_index >= self.alarm_table.rowCount():
            return
        if not isinstance(color, QColor):
            color = QColor(color)
        for col in range(self.alarm_table.columnCount()):
            item = self.alarm_table.item(row_index, col)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.alarm_table.setItem(row_index, col, item)
            item.setBackground(color)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1400, 800)
    window.show()
    sys.exit(app.exec())
