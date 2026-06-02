from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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

from domain.models import AlarmParameterRecord


def _spin_box(minimum, maximum):
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumWidth(80)
    return widget


def _field_label(caption, field_name=None, alignment=None):
    widget = QLabel()
    widget.setWordWrap(True)
    if alignment is not None:
        widget.setAlignment(alignment)
    widget.setText(caption)
    if field_name:
        widget.setToolTip(field_name)
    return widget


class AlarmParameterPage(QWidget):
    def __init__(self, alarm_definitions, alarm_fields):
        super().__init__()
        self.alarm_definitions = list(alarm_definitions)
        self.definition_by_id = {
            definition.alarm_id: definition
            for definition in self.alarm_definitions
        }
        self.alarm_fields = list(alarm_fields)
        self.summary_fields = [field for field in self.alarm_fields if field.summary]
        self.summary_items = {}
        self.record_cache = {}
        self.current_cluster_index = None
        self.current_address = None
        self.current_record_complete = False
        self._ignore_table_selection = False

        self._build_ui()
        self._populate_alarm_rows()

    @staticmethod
    def default_status_text():
        return (
            "选中告警后自动读取完整参数。字段映射：阈值=s16LevelN，回差=u16Hysteresis_N，"
            "产生延时=u16AlarmOnDelayN，消除延时=u16AlarmOffDelayN，继电器关联=u16Relay，"
            "继电器延时=u16RelayOnDelayN，降额=u16DerateLvN，使能=u16DisLevel。"
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title_label = QLabel("告警参数", self)
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        toolbar.addWidget(self.cluster_label)
        toolbar.addStretch(1)

        self.read_summary_button = QPushButton("读取表格参数", self)
        toolbar.addWidget(self.read_summary_button)
        self.write_current_button = QPushButton("写入选中告警", self)
        toolbar.addWidget(self.write_current_button)
        self.save_flash_button = QPushButton("保存参数到FLASH", self)
        toolbar.addWidget(self.save_flash_button)
        layout.addLayout(toolbar)

        self.status_label = QLabel(self.default_status_text(), self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        table_panel = QWidget(splitter)
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)
        table_layout.addWidget(QLabel("告警列表", table_panel))

        self.alarm_table = QTableWidget(table_panel)
        self.alarm_table.setColumnCount(2 + len(self.summary_fields))
        self.alarm_table.setHorizontalHeaderLabels(
            ["序号", "告警名称"] + [field.label for field in self.summary_fields]
        )
        self.alarm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.alarm_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.alarm_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.alarm_table.verticalHeader().setVisible(False)
        self.alarm_table.setAlternatingRowColors(True)
        self.alarm_table.horizontalHeader().setDefaultSectionSize(92)
        self.alarm_table.horizontalHeader().setStretchLastSection(True)
        self.alarm_table.setColumnWidth(0, 60)
        self.alarm_table.setColumnWidth(1, 220)
        table_layout.addWidget(self.alarm_table)
        splitter.addWidget(table_panel)

        detail_scroll = QScrollArea(splitter)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)

        detail_root = QWidget(detail_scroll)
        detail_layout = QVBoxLayout(detail_root)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        detail_header = QGroupBox("当前告警", detail_root)
        detail_header_layout = QVBoxLayout(detail_header)
        detail_header_layout.setSpacing(6)

        self.selected_alarm_label = QLabel("未选择告警", detail_header)
        self.selected_alarm_label.setObjectName("sectionTitle")
        detail_header_layout.addWidget(self.selected_alarm_label)

        self.alarm_id_label = QLabel("告警ID / u16AlarmId: -", detail_header)
        self.alarm_id_label.setObjectName("sectionHint")
        detail_header_layout.addWidget(self.alarm_id_label)
        detail_layout.addWidget(detail_header)

        section_layout = QGridLayout()
        section_layout.setHorizontalSpacing(12)
        section_layout.setVerticalSpacing(12)

        self.summary_group = QGroupBox("阈值与回差", detail_root)
        summary_layout = QGridLayout(self.summary_group)
        summary_layout.setHorizontalSpacing(8)
        summary_layout.setVerticalSpacing(8)
        self.level_boxes = {}
        self.hysteresis_boxes = {}
        for level in range(1, 6):
            summary_layout.addWidget(
                _field_label(f"{level}级告警", f"s16Level{level}"),
                level - 1,
                0,
            )
            self.level_boxes[level] = _spin_box(-32768, 32767)
            summary_layout.addWidget(self.level_boxes[level], level - 1, 1)

            summary_layout.addWidget(
                _field_label(f"{level}级回差", f"u16Hysteresis_{level}"),
                level - 1,
                2,
            )
            self.hysteresis_boxes[level] = _spin_box(0, 65535)
            summary_layout.addWidget(self.hysteresis_boxes[level], level - 1, 3)
        section_layout.addWidget(self.summary_group, 0, 0)

        self.delay_group = QGroupBox("延时参数", detail_root)
        delay_layout = QGridLayout(self.delay_group)
        delay_layout.setHorizontalSpacing(8)
        delay_layout.setVerticalSpacing(8)
        self.alarm_on_delay_boxes = {}
        self.alarm_off_delay_boxes = {}
        for level in range(1, 6):
            delay_layout.addWidget(
                _field_label(
                    f"{level}级产生延时",
                    f"u16AlarmOnDelay{level}",
                ),
                level - 1,
                0,
            )
            self.alarm_on_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.alarm_on_delay_boxes[level], level - 1, 1)

            delay_layout.addWidget(
                _field_label(
                    f"{level}级消除延时",
                    f"u16AlarmOffDelay{level}",
                ),
                level - 1,
                2,
            )
            self.alarm_off_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.alarm_off_delay_boxes[level], level - 1, 3)

        self.relay_on_delay_boxes = {}
        for level in range(1, 4):
            delay_layout.addWidget(
                _field_label(
                    f"{level}级继电器延时",
                    f"u16RelayOnDelay{level}",
                ),
                level - 1,
                4,
            )
            self.relay_on_delay_boxes[level] = _spin_box(0, 65535)
            delay_layout.addWidget(self.relay_on_delay_boxes[level], level - 1, 5)
        section_layout.addWidget(self.delay_group, 0, 1)

        self.option_group = QGroupBox("降额 / 使能 / 继电器关联", detail_root)
        option_layout = QGridLayout(self.option_group)
        option_layout.setHorizontalSpacing(10)
        option_layout.setVerticalSpacing(8)

        option_layout.addWidget(_field_label("级别"), 0, 0)
        option_layout.addWidget(
            _field_label("充电降额", "u16DerateLvN 高字节", Qt.AlignmentFlag.AlignCenter),
            0,
            1,
        )
        option_layout.addWidget(
            _field_label("放电降额", "u16DerateLvN 低字节", Qt.AlignmentFlag.AlignCenter),
            0,
            2,
        )
        option_layout.addWidget(
            _field_label("使能", "u16DisLevel bitN", Qt.AlignmentFlag.AlignCenter),
            0,
            3,
        )
        option_layout.addWidget(
            _field_label("放电关联", "u16Relay bit0/4/8", Qt.AlignmentFlag.AlignCenter),
            0,
            4,
        )
        option_layout.addWidget(
            _field_label("断路器关联", "u16Relay bit1/5/9", Qt.AlignmentFlag.AlignCenter),
            0,
            5,
        )
        option_layout.addWidget(
            _field_label("充电关联", "u16Relay bit2/6/10", Qt.AlignmentFlag.AlignCenter),
            0,
            6,
        )

        self.derate_charge_boxes = {}
        self.derate_discharge_boxes = {}
        self.display_level_checks = {}
        self.relay_checks = {}
        relay_names = ("放电", "断路器", "充电")
        for level in range(1, 6):
            row = level
            option_layout.addWidget(_field_label(f"{level}级"), row, 0)
            self.derate_charge_boxes[level] = _spin_box(0, 255)
            option_layout.addWidget(self.derate_charge_boxes[level], row, 1)
            self.derate_discharge_boxes[level] = _spin_box(0, 255)
            option_layout.addWidget(self.derate_discharge_boxes[level], row, 2)

            self.display_level_checks[level] = QCheckBox("", self.option_group)
            option_layout.addWidget(self.display_level_checks[level], row, 3)

            for relay_offset, relay_name in enumerate(relay_names):
                checkbox = QCheckBox("", self.option_group)
                checkbox.setEnabled(level <= 3)
                option_layout.addWidget(checkbox, row, 4 + relay_offset)
                self.relay_checks[(level, relay_name)] = checkbox
        section_layout.addWidget(self.option_group, 1, 0, 1, 2)

        detail_layout.addLayout(section_layout)
        detail_layout.addStretch(1)

        detail_scroll.setWidget(detail_root)
        splitter.addWidget(detail_scroll)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 7)
        layout.addWidget(splitter, stretch=1)
        self._set_record_complete(False)

    def _populate_alarm_rows(self):
        self.alarm_table.setRowCount(len(self.alarm_definitions))
        for row_index, definition in enumerate(self.alarm_definitions):
            row_label = QTableWidgetItem(definition.code)
            row_label.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            row_label.setFlags(row_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.alarm_table.setItem(row_index, 0, row_label)

            name_item = QTableWidgetItem(definition.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.alarm_table.setItem(row_index, 1, name_item)

            self.summary_items[definition.alarm_id] = {}
            for column_offset, field in enumerate(self.summary_fields, start=2):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.alarm_table.setItem(row_index, column_offset, item)
                self.summary_items[definition.alarm_id][field.key] = item

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = cluster_index
        self.current_address = address
        if cluster_index is None or not address:
            self.cluster_label.setText("当前簇: -")
            return
        self.cluster_label.setText(f"当前簇: 簇{cluster_index} / 地址 {address}")

    def set_status_text(self, text):
        self.status_label.setText("" if text is None else str(text))

    def clear_cached_values(self):
        self.record_cache = {}
        for summary_map in self.summary_items.values():
            for item in summary_map.values():
                item.setText("")
        self.alarm_table.clearSelection()
        self.clear_detail()

    def clear_detail(self):
        self.current_record_complete = False
        self.selected_alarm_label.setText("未选择告警")
        self.alarm_id_label.setText("告警ID / u16AlarmId: -")
        for level in range(1, 6):
            self.level_boxes[level].setValue(0)
            self.hysteresis_boxes[level].setValue(0)
        self._clear_detail_only_inputs()
        self._set_record_complete(False)

    def has_complete_current_record(self):
        return self.current_record_complete

    def _clear_detail_only_inputs(self):
        for level in range(1, 6):
            self.alarm_on_delay_boxes[level].setValue(0)
            self.alarm_off_delay_boxes[level].setValue(0)
            self.derate_charge_boxes[level].setValue(0)
            self.derate_discharge_boxes[level].setValue(0)
            self.display_level_checks[level].setChecked(False)

        for level in range(1, 4):
            self.relay_on_delay_boxes[level].setValue(0)

        for checkbox in self.relay_checks.values():
            checkbox.setChecked(False)

    def _set_record_complete(self, complete):
        self.current_record_complete = bool(complete)
        self.delay_group.setEnabled(self.current_record_complete)
        self.option_group.setEnabled(self.current_record_complete)

    def set_summary_records(self, records):
        self.clear_cached_values()
        for record in records:
            self._cache_record(record)
            self._update_summary_row(record)
        if records:
            self.select_alarm(records[0].alarm_id)

    def set_detail_record(self, record):
        self._cache_record(record)
        self._update_summary_row(record)
        self.select_alarm(record.alarm_id)
        self._apply_record_to_inputs(record)

    def current_alarm_id(self):
        selection_model = self.alarm_table.selectionModel()
        if selection_model is None:
            return None
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        if row < 0 or row >= len(self.alarm_definitions):
            return None
        return self.alarm_definitions[row].alarm_id

    def select_alarm(self, alarm_id):
        for row_index, definition in enumerate(self.alarm_definitions):
            if definition.alarm_id != int(alarm_id):
                continue
            self._ignore_table_selection = True
            self.alarm_table.selectRow(row_index)
            self._ignore_table_selection = False
            cached_record = self.record_cache.get(int(alarm_id))
            if cached_record is not None:
                self._apply_record_to_inputs(cached_record)
            else:
                self.selected_alarm_label.setText(
                    f"{definition.code} {definition.name} - 未读取"
                )
                self.alarm_id_label.setText(
                    f"告警ID / u16AlarmId: {definition.alarm_id} / 序号 {definition.code}"
                )
            break

    def on_table_selection_changed(self):
        if self._ignore_table_selection:
            return
        alarm_id = self.current_alarm_id()
        if alarm_id is None:
            return
        definition = self.definition_by_id[alarm_id]
        cached_record = self.record_cache.get(alarm_id)
        if cached_record is None:
            self.clear_detail()
            self.selected_alarm_label.setText(
                f"{definition.code} {definition.name} - 未读取"
            )
            self.alarm_id_label.setText(
                f"告警ID / u16AlarmId: {definition.alarm_id} / 序号 {definition.code}"
            )
            return
        self._apply_record_to_inputs(cached_record)

    def build_current_record(self):
        alarm_id = self.current_alarm_id()
        if alarm_id is None:
            return None

        definition = self.definition_by_id[alarm_id]
        values = {}
        for level in range(1, 6):
            values[f"level{level}"] = self.level_boxes[level].value()
            values[f"hysteresis{level}"] = self.hysteresis_boxes[level].value()

        if not self.current_record_complete:
            return AlarmParameterRecord(
                alarm_id=definition.alarm_id,
                code=definition.code,
                name=definition.name,
                values=values,
                is_complete=False,
            )

        for level in range(1, 6):
            values[f"alarm_on_delay{level}"] = self.alarm_on_delay_boxes[level].value()
            values[f"alarm_off_delay{level}"] = self.alarm_off_delay_boxes[level].value()
            values[f"derate{level}"] = (
                (self.derate_charge_boxes[level].value() & 0xFF) << 8
            ) | (self.derate_discharge_boxes[level].value() & 0xFF)

        relay_mask = 0
        relay_names = ("放电", "断路器", "充电")
        for level in range(1, 4):
            values[f"relay_on_delay{level}"] = self.relay_on_delay_boxes[level].value()
            bit_base = (level - 1) * 4
            for relay_offset, relay_name in enumerate(relay_names):
                if self.relay_checks[(level, relay_name)].isChecked():
                    relay_mask |= 1 << (bit_base + relay_offset)
        values["relay_mask"] = relay_mask

        display_level = 0
        for level in range(1, 6):
            if self.display_level_checks[level].isChecked():
                display_level |= 1 << (level - 1)
        values["display_level"] = display_level

        return AlarmParameterRecord(
            alarm_id=definition.alarm_id,
            code=definition.code,
            name=definition.name,
            values=values,
            is_complete=self.current_record_complete,
        )

    def validate_record(self, record):
        errors = []
        if record is None:
            return errors
        for level in range(1, 6):
            key = f"alarm_on_delay{level}"
            if key in record.values and int(record.values[key]) < 10:
                errors.append(f"{level}级产生延时不能小于 10。")
        return errors

    def _cache_record(self, record):
        self.record_cache[record.alarm_id] = record

    def _update_summary_row(self, record):
        summary_map = self.summary_items.get(record.alarm_id, {})
        for field in self.summary_fields:
            item = summary_map.get(field.key)
            if item is None:
                continue
            value = record.values.get(field.key, "")
            item.setText("" if value is None else str(value))

    def _apply_record_to_inputs(self, record):
        self.alarm_id_label.setText(
            f"告警ID / u16AlarmId: {record.alarm_id} / 序号 {record.code}"
        )
        for level in range(1, 6):
            self.level_boxes[level].setValue(int(record.values.get(f"level{level}", 0)))
            self.hysteresis_boxes[level].setValue(
                int(record.values.get(f"hysteresis{level}", 0))
            )
        if not record.is_complete:
            self._clear_detail_only_inputs()
            self._set_record_complete(False)
            self.selected_alarm_label.setText(
                f"{record.code} {record.name} - 仅已读取表格参数"
            )
            return

        self.selected_alarm_label.setText(f"{record.code} {record.name}")
        self._set_record_complete(True)
        for level in range(1, 6):
            self.alarm_on_delay_boxes[level].setValue(
                int(record.values.get(f"alarm_on_delay{level}", 0))
            )
            self.alarm_off_delay_boxes[level].setValue(
                int(record.values.get(f"alarm_off_delay{level}", 0))
            )
            derate_value = int(record.values.get(f"derate{level}", 0))
            self.derate_charge_boxes[level].setValue((derate_value >> 8) & 0xFF)
            self.derate_discharge_boxes[level].setValue(derate_value & 0xFF)

        for level in range(1, 4):
            self.relay_on_delay_boxes[level].setValue(
                int(record.values.get(f"relay_on_delay{level}", 0))
            )

        display_level = int(record.values.get("display_level", 0))
        for level in range(1, 6):
            self.display_level_checks[level].setChecked(
                bool(display_level & (1 << (level - 1)))
            )

        relay_mask = int(record.values.get("relay_mask", 0))
        relay_names = ("放电", "断路器", "充电")
        for level in range(1, 4):
            bit_base = (level - 1) * 4
            for relay_offset, relay_name in enumerate(relay_names):
                self.relay_checks[(level, relay_name)].setChecked(
                    bool(relay_mask & (1 << (bit_base + relay_offset)))
                )
