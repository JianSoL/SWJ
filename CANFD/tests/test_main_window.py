import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QComboBox, QMessageBox


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from domain.models import (
    AlarmParameterDefinition,
    AlarmParameterField,
    AlarmParameterRecord,
    BusConfig,
    HistoryLogRecord,
    LegacySignalUpdate,
    PeriodicSignalUpdate,
    PollResult,
)
from presentation.main_window import MainWindow


class FakeService:
    def __init__(self, snapshot_logging_enabled=True):
        self.cluster_indices = [0, 1, 2]
        self.cluster_addresses = ["00", "A0", "A1"]
        self.snapshot_logging_enabled = snapshot_logging_enabled
        self.snapshot_logging_updates = []
        self.active_cluster_calls = []
        self.opened = False
        self.closed = False
        self.open_calls = 0
        self.reopen_calls = 0
        self.query_calls = []
        self.balance_query_calls = []
        self.monitor_query_calls = []
        self.work_mode_calls = []
        self.read_factory_test_mode_calls = []
        self.control_channel_calls = []
        self.read_data_u16_calls = []
        self.write_data_u16_calls = []
        self.write_hvil_calls = []
        self.write_soc_calls = []
        self.restore_factory_calls = []
        self.restore_run_calls = []
        self.restore_product_info_calls = []
        self.save_all_flash_calls = []
        self.sync_time_calls = []
        self.factory_mode_states = {0: 0, 1: 1, 2: 0}
        self.snapshot_calls = 0
        self.snapshot_targets = []
        self.alarm_summary_calls = []
        self.alarm_record_calls = []
        self.alarm_write_calls = []
        self.alarm_save_flash_calls = []
        self.history_count_calls = []
        self.history_entry_calls = []
        self.history_clear_calls = []
        self.dbc_runtime_updates = []
        self.bus_config = BusConfig(
            can_type=41,
            device_index=0,
            channel_index=0,
            arbitration_baud=500000,
            data_baud=2000000,
        )
        self.dbc_runtime = SimpleNamespace(dbc_path="default.dbc")
        self.dbc_catalog_by_address = {
            address: [
                {
                    "row_key": f"{address}.sig",
                    "message_name": f"MSG_{address}",
                    "signal_name": "SIG",
                    "unit": "V",
                }
            ]
            for address in self.cluster_addresses
        }
        self.periodic_voltage = {"00": [100, 200], "A0": [300, 400], "A1": [500, 600]}
        self.periodic_temperature = {"00": [30, 31], "A0": [32, 33], "A1": [34, 35]}
        self.legacy_balance = {"00": [("M1-001", 1), ("M1-002", 0)], "A0": [], "A1": []}
        self.periodic_alarm = {"00": [("001", 2), ("002", 0)], "A0": [], "A1": []}
        self.periodic_terminal_temperature = {
            "00": [("01_1", 21.5), ("01_2", 18.5)],
            "A0": [],
            "A1": [],
        }
        self.alarm_parameter_fields = [
            AlarmParameterField("level1", "一级告警", 0, signed=True, summary=True),
            AlarmParameterField("level2", "二级告警", 1, signed=True, summary=True),
            AlarmParameterField("level3", "三级告警", 2, signed=True, summary=True),
            AlarmParameterField("level4", "四级告警", 3, signed=True, summary=True),
            AlarmParameterField("level5", "五级告警", 4, signed=True, summary=True),
            AlarmParameterField("hysteresis1", "一级回差", 5, summary=True),
            AlarmParameterField("hysteresis2", "二级回差", 6, summary=True),
            AlarmParameterField("hysteresis3", "三级回差", 7, summary=True),
            AlarmParameterField("hysteresis4", "四级回差", 8, summary=True),
            AlarmParameterField("hysteresis5", "五级回差", 9, summary=True),
        ]
        self.alarm_parameter_definitions = [
            AlarmParameterDefinition(0, "001", "单体电压过高"),
            AlarmParameterDefinition(1, "002", "单体电压过低"),
        ]

        self.monitor_snapshots = {
            0: {
                "work_mode": 0,
                "run_status": 5,
                "soc": 880,
                "user_set_soc": 900,
                "hvil_pwm_freq": 100,
                "hvil_pwm_duty": 250,
                "di_states": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                "relay_states": [1, 0, 0, 1, 0, 0, 1, 0, 1, 0],
                "rt_values": [250] * 10,
            },
            1: {
                "work_mode": 1,
                "run_status": 6,
                "soc": 650,
                "user_set_soc": 660,
                "hvil_pwm_freq": 150,
                "hvil_pwm_duty": 300,
                "di_states": [0] * 12,
                "relay_states": [0] * 10,
                "rt_values": [260] * 10,
            },
            2: {
                "work_mode": 0,
                "run_status": 4,
                "soc": 500,
                "user_set_soc": 500,
                "hvil_pwm_freq": 80,
                "hvil_pwm_duty": 200,
                "di_states": [0] * 12,
                "relay_states": [0] * 10,
                "rt_values": [240] * 10,
            },
        }
        self.request_index_values = {
            (0, 0x10): 2000,
            (0, 0x20): 3000,
            (1, 0x10): 2100,
        }

    def open(self):
        self.open_calls += 1
        self.opened = True

    def reopen(self):
        self.reopen_calls += 1
        self.opened = True

    def update_bus_config(self, **kwargs):
        self.bus_config = replace(self.bus_config, **kwargs)
        return self.bus_config

    def close(self):
        self.closed = True

    def get_dbc_catalog(self, address):
        return list(self.dbc_catalog_by_address.get(address, []))

    def set_dbc_runtime(self, dbc_runtime):
        self.dbc_runtime = dbc_runtime
        self.dbc_runtime_updates.append(dbc_runtime)
        catalog_by_address = getattr(dbc_runtime, "catalog_by_address", {})
        self.dbc_catalog_by_address = {
            address: list(catalog_by_address.get(address, []))
            for address in self.cluster_addresses
        }
        self.periodic_voltage = {address: [] for address in self.cluster_addresses}
        self.periodic_temperature = {address: [] for address in self.cluster_addresses}
        self.periodic_alarm = {address: [] for address in self.cluster_addresses}
        self.periodic_terminal_temperature = {
            address: []
            for address in self.cluster_addresses
        }
        return dbc_runtime

    def poll(self):
        return PollResult(
            legacy_updates=[
                LegacySignalUpdate(
                    cluster_index=0,
                    signal_id=0x1,
                    signal_name="SOC",
                    value="88",
                    unit="%",
                    table_index=0,
                    row_index=0,
                    source_kind="can",
                )
            ],
            periodic_updates=[
                PeriodicSignalUpdate(
                    address="00",
                    row_key="00.sig",
                    message_name="MSG_00",
                    signal_name="SIG",
                    value="12.3",
                    unit="V",
                )
            ],
            periodic_status={"00": "updated"},
            had_rx_frame=True,
        )

    def send_next_query(self, active_tab_index):
        self.query_calls.append(active_tab_index)
        return 1

    def send_next_balance_query(self, active_tab_index):
        self.balance_query_calls.append(active_tab_index)
        return 1

    def send_next_monitor_query(self, cluster_index):
        self.monitor_query_calls.append(cluster_index)
        return 1

    def write_legacy_snapshots(self, cluster_index=None):
        self.snapshot_calls += 1
        self.snapshot_targets.append(cluster_index)

    def set_active_cluster(self, cluster_index):
        self.active_cluster_calls.append(cluster_index)

    def set_snapshot_logging_enabled(self, enabled):
        self.snapshot_logging_enabled = bool(enabled)
        self.snapshot_logging_updates.append(self.snapshot_logging_enabled)

    def set_factory_test_mode(self, cluster_index, enabled):
        self.work_mode_calls.append((cluster_index, bool(enabled)))
        self.factory_mode_states[cluster_index] = 1 if enabled else 0
        return self.factory_mode_states[cluster_index]

    def read_factory_test_mode(self, cluster_index):
        self.read_factory_test_mode_calls.append(cluster_index)
        return self.factory_mode_states[cluster_index]

    def get_index_monitor_snapshot(self, cluster_index):
        return dict(self.monitor_snapshots.get(cluster_index, {}))

    def control_channel(self, cluster_index, channel_id, enabled, timeout_s=1.0):
        self.control_channel_calls.append((cluster_index, channel_id, bool(enabled), timeout_s))
        snapshot = self.monitor_snapshots.setdefault(cluster_index, {})
        states = list(snapshot.get("relay_states", [0] * 10))
        states[channel_id - 1] = 1 if enabled else 0
        snapshot["relay_states"] = states
        return True

    def read_data_u16(self, cluster_index, data_id, timeout_s=1.0):
        self.read_data_u16_calls.append((cluster_index, data_id, timeout_s))
        return self.request_index_values.get((cluster_index, data_id), 0)

    def write_data_u16(self, cluster_index, data_id, value, timeout_s=1.0):
        self.write_data_u16_calls.append((cluster_index, data_id, value, timeout_s))
        self.request_index_values[(cluster_index, data_id)] = int(value) & 0xFFFF
        return True

    def write_hvil_pwm_config(self, cluster_index, freq, duty, timeout_s=1.0):
        self.write_hvil_calls.append((cluster_index, freq, duty, timeout_s))
        snapshot = self.monitor_snapshots.setdefault(cluster_index, {})
        snapshot["hvil_pwm_freq"] = freq
        snapshot["hvil_pwm_duty"] = duty
        return True

    def write_user_set_soc(self, cluster_index, soc_value, timeout_s=1.0):
        self.write_soc_calls.append((cluster_index, soc_value, timeout_s))
        snapshot = self.monitor_snapshots.setdefault(cluster_index, {})
        snapshot["user_set_soc"] = soc_value
        return True

    def restore_factory_parameters(self, cluster_index, timeout_s=1.0):
        self.restore_factory_calls.append((cluster_index, timeout_s))
        return True

    def restore_run_parameters(self, cluster_index, timeout_s=1.0):
        self.restore_run_calls.append((cluster_index, timeout_s))
        return True

    def restore_product_info(self, cluster_index, timeout_s=1.0):
        self.restore_product_info_calls.append((cluster_index, timeout_s))
        return True

    def save_all_parameters_to_flash(self, cluster_index, timeout_s=1.0):
        self.save_all_flash_calls.append((cluster_index, timeout_s))
        return True

    def sync_system_time(self, cluster_index, dt=None, timeout_s=1.0):
        self.sync_time_calls.append((cluster_index, timeout_s))
        return True

    def get_alarm_parameter_fields(self):
        return list(self.alarm_parameter_fields)

    def get_alarm_parameter_definitions(self):
        return list(self.alarm_parameter_definitions)

    def _alarm_values(self, base_value=3600):
        values = {}
        for level in range(1, 6):
            values[f"level{level}"] = base_value - (level - 1) * 100
            values[f"hysteresis{level}"] = level * 10
            values[f"alarm_on_delay{level}"] = 100
            values[f"alarm_off_delay{level}"] = 300
            values[f"derate{level}"] = 0x6464
        values["relay_mask"] = 0x0047
        values["relay_on_delay1"] = 10
        values["relay_on_delay2"] = 10
        values["relay_on_delay3"] = 10
        values["display_level"] = 0x001F
        return values

    def read_alarm_parameter_summary(self, cluster_index):
        self.alarm_summary_calls.append(cluster_index)
        return [
            AlarmParameterRecord(
                0,
                "001",
                "单体电压过高",
                self._alarm_values(3600),
                is_complete=False,
            ),
            AlarmParameterRecord(
                1,
                "002",
                "单体电压过低",
                self._alarm_values(2700),
                is_complete=False,
            ),
        ]

    def read_alarm_parameter_record(self, cluster_index, alarm_id, timeout_s=1.0):
        self.alarm_record_calls.append((cluster_index, alarm_id, timeout_s))
        definition = self.alarm_parameter_definitions[alarm_id]
        return AlarmParameterRecord(
            definition.alarm_id,
            definition.code,
            definition.name,
            self._alarm_values(3600 if alarm_id == 0 else 2700),
        )

    def write_alarm_parameter_record(self, cluster_index, record):
        self.alarm_write_calls.append((cluster_index, record))
        return True

    def save_alarm_parameters_to_flash(self, cluster_index):
        self.alarm_save_flash_calls.append(cluster_index)
        return True

    def read_history_log_count(self, cluster_index, log_type=1):
        self.history_count_calls.append((cluster_index, log_type))
        return 2

    def read_history_log_entry(self, cluster_index, log_index, log_type=1):
        self.history_entry_calls.append((cluster_index, log_index, log_type))
        return HistoryLogRecord(
            sequence=log_index,
            timestamp=f"2026-06-02 10:00:0{log_index}",
            log_type="告警日志",
            log_subtype="告警产生",
            run_status=2,
            relay_status="1继电器闭合",
            alarm_count=1,
            raw_word=0,
            alarm_id=32,
            alarm_name="高压互锁故障",
            alarm_level=3,
            alarm_position="BCU: 000---CSU: 000---Cell: 004---Bat: 0",
            total_voltage=315.6,
            total_current=0.0,
            soc=83.8,
            soh=100.0,
            p_bus_resistance=20000,
            n_bus_resistance=20000,
            diff_voltage=0,
            diff_temperature=0.0,
            max_cell_voltage=3450,
            max_cell_voltage_position="BCU:000|CSU:000|Cell:004",
            min_cell_voltage=3300,
            min_cell_voltage_position="BCU:000|CSU:000|Cell:005",
            max_cell_temperature=30.0,
            max_cell_temperature_position="BCU:000|CSU:000|Cell:004",
            min_cell_temperature=25.0,
            min_cell_temperature_position="BCU:000|CSU:000|Cell:005",
            threshold_value=2000,
            actual_value=2100,
        )

    def clear_history_logs(self, cluster_index):
        self.history_clear_calls.append(cluster_index)
        return True

    def get_periodic_voltage_values(self, address):
        return self.periodic_voltage[address]

    def get_periodic_temperature_values(self, address):
        return self.periodic_temperature[address]

    def get_legacy_balance_state_values(self, address):
        return self.legacy_balance[address]

    def get_periodic_alarm_state_values(self, address):
        return self.periodic_alarm[address]

    def get_periodic_terminal_temperature_values(self, address):
        return self.periodic_terminal_temperature[address]


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_window_builds_and_applies_updates(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        self.assertTrue(window.can_ready)
        self.assertEqual(window.tabWidget.count(), 12)
        self.assertEqual(window.cluster_selector.count(), 3)
        self.assertEqual(window.cluster_selector.currentIndex(), 1)
        self.assertEqual(window.selected_cluster_index, 1)
        self.assertEqual(service.active_cluster_calls[-1], 1)
        self.assertEqual(window.save_scope_selector.currentData(), "current")
        self.assertEqual(window.alarm_parameter_page.cluster_label.text(), "当前簇: 簇1 / 地址 A0")
        self.assertTrue(window.query_timer.isActive())
        self.assertEqual(window.voltage_page.findChildren(QComboBox), [])
        self.assertEqual(window.temperature_page.findChildren(QComboBox), [])
        self.assertEqual(window.balance_page.findChildren(QComboBox), [])
        self.assertEqual(window.device_index_spinbox.value(), 0)
        self.assertEqual(window.channel_index_spinbox.value(), 0)
        self.assertEqual(window.save_interval_spinbox.value(), 500)
        self.assertEqual(window.save_timer.interval(), 500)
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5f00")
        self.assertEqual(service.read_factory_test_mode_calls, [1])
        self.assertEqual(
            window.bus_status_label.text(),
            "\u5df2\u8fde\u63a5: dev 0 / ch 0",
        )

        window.cluster_selector.setCurrentIndex(0)
        self.assertEqual(window.selected_cluster_index, 0)
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5173")
        self.assertEqual(service.read_factory_test_mode_calls[-1], 0)

        window.on_poll_timer()
        self.assertEqual(window.TW[1][0].item(0, 1).text(), "88")
        self.assertEqual(window.dbc_value_items["00.sig"].text(), "12.3")
        self.assertEqual(window.dbc_status_label.text(), "updated")

        window.tabWidget.setCurrentIndex(window.TEMPERATURE_TAB_INDEX)
        self.assertEqual(window.temperature_page.lineEdits[0].text(), "30.0")

        window.tabWidget.setCurrentIndex(window.BALANCE_TAB_INDEX)
        self.assertEqual(window.balance_page.lineEdits[0].text(), "1")
        self.assertEqual(window.balance_page.lineEdits[1].text(), "0")
        window.on_query_timer()
        self.assertEqual(service.query_calls[-1], 0)
        self.assertEqual(service.balance_query_calls[-1], 0)
        self.assertTrue(window.query_timer.isActive())

        window.tabWidget.setCurrentIndex(window.ALARM_TAB_INDEX)
        self.assertEqual(window.alarm_page.entries[0][1].text(), "2")

        window.tabWidget.setCurrentIndex(window.TERMINAL_TEMPERATURE_TAB_INDEX)
        self.assertEqual(window.terminal_temperature_page.entries[0][1].text(), "21.5")

        window.tabWidget.setCurrentIndex(window.REQUEST_TAB_INDEX)
        window.on_query_timer()
        window.on_save_timer()
        self.assertEqual(service.query_calls[-1], 0)
        self.assertEqual(service.balance_query_calls[-1], 0)
        self.assertEqual(service.snapshot_calls, 1)
        self.assertEqual(service.snapshot_targets[-1], 0)
        self.assertTrue(window.query_timer.isActive())

        window.tabWidget.setCurrentIndex(0)
        self.assertTrue(window.query_timer.isActive())

        window.cluster_selector.setCurrentIndex(2)
        self.assertEqual(window.selected_cluster_index, 2)
        self.assertEqual(service.active_cluster_calls[-1], 2)
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5173")
        self.assertEqual(service.read_factory_test_mode_calls[-1], 2)
        window.on_query_timer()
        window.on_save_timer()
        self.assertEqual(service.query_calls[-1], 2)
        self.assertEqual(service.balance_query_calls[-1], 2)
        self.assertEqual(service.snapshot_targets[-1], 2)
        self.assertTrue(window.overview_label.text())
        self.assertTrue(window._change_factory_mode(False, show_dialog=False))
        self.assertEqual(service.work_mode_calls[-1], (2, False))

        window.device_index_spinbox.setValue(2)
        window.channel_index_spinbox.setValue(1)
        window.on_apply_bus_settings()
        self.assertEqual(service.reopen_calls, 1)
        self.assertEqual(service.bus_config.device_index, 2)
        self.assertEqual(service.bus_config.channel_index, 1)
        self.assertEqual(runtime_config["DEVICE_INDEX"], 2)
        self.assertEqual(runtime_config["CHANNEL_INDEX"], 1)
        self.assertEqual(
            window.bus_status_label.text(),
            "\u5df2\u8fde\u63a5: dev 2 / ch 1",
        )

        window.close()
        self.assertTrue(service.closed)

    def test_request_page_uses_group_tabs_and_wider_columns(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        self.assertEqual(window.request_group_tabs.count(), 3)
        self.assertEqual(
            window.request_group_tabs.tabText(0),
            "请求分组 1",
        )

        request_table = window.TW[window.REQUEST_TAB_INDEX][0]
        self.assertEqual(request_table.horizontalHeaderItem(2).text(), "单位/说明")
        self.assertEqual(request_table.columnWidth(0), 280)
        self.assertEqual(request_table.columnWidth(1), 100)
        self.assertEqual(request_table.columnWidth(2), 420)

        window.close()

    def test_index_pages_refresh_and_send_control_actions(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)

        self.assertEqual(
            [edit.text() for edit in window.index_control_page.index_edits],
            ["0"] * 10,
        )

        window.tabWidget.setCurrentIndex(window.REALTIME_MONITOR_TAB_INDEX)
        window.on_query_timer()
        self.assertEqual(service.monitor_query_calls[-1], 0)
        self.assertIn("88", window.index_monitor_page.soc_display.text())
        self.assertEqual(window.index_monitor_page.metric_labels["pure_soc"].text(), "原始SOC")
        self.assertEqual(window.index_monitor_page.metric_labels["revise_soc_temp"].text(), "温度修正SOC")
        self.assertEqual(window.index_monitor_page.metric_labels["board_temp1"].text(), "BCU板温1")
        self.assertEqual(window.index_monitor_page.input_dots[0].text_label.text(), "DI1")
        self.assertEqual(window.index_monitor_page.output_dots[-1].text_label.text(), "LSD2")

        window._set_factory_mode_status(1)
        window.tabWidget.setCurrentIndex(window.HOST_CONTROL_TAB_INDEX)
        self.assertEqual(window.index_control_page.soc_current.text(), "88 %")
        window.index_control_page.channel_checks[1].setChecked(False)
        self.assertEqual(service.control_channel_calls[-1][:3], (0, 1, False))

        window.index_control_page.hvil_freq_target.setValue(123)
        window.index_control_page.hvil_duty_target.setValue(456)
        window.on_index_control_write_hvil()
        self.assertEqual(service.write_hvil_calls[-1][:3], (0, 123, 456))

        window.index_control_page.soc_target.setValue(789)
        window.on_index_control_write_soc()
        self.assertEqual(service.write_soc_calls[-1][:2], (0, 789))
        self.assertEqual(window.index_control_page.soc_current.text(), "88 %")

        window.on_index_control_restore_factory()
        window.on_index_control_restore_run()
        window.on_index_control_restore_product_info()
        window.on_index_control_save_flash()
        window.on_index_control_sync_time()
        self.assertEqual(service.restore_factory_calls[-1][0], 0)
        self.assertEqual(service.restore_run_calls[-1][0], 0)
        self.assertEqual(service.restore_product_info_calls[-1][0], 0)
        self.assertEqual(service.save_all_flash_calls[-1][0], 0)
        self.assertEqual(service.sync_time_calls[-1][0], 0)

        window.close()

    def test_index_control_request_indexes_can_read_and_write_values(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)
        page = window.index_control_page

        self.assertFalse(page.index_value_edits[0].isReadOnly())

        for row_index in range(10):
            page.index_edits[row_index].setText("")
            page.index_value_edits[row_index].setText("")

        page.index_edits[0].setText("0x10")
        page.index_edits[1].setText("0x20")
        window.on_index_control_read_indexes()

        self.assertEqual(
            service.read_data_u16_calls[-2:],
            [(0, 0x10, 0.2), (0, 0x20, 0.2)],
        )
        self.assertEqual(page.index_value_edits[0].text(), "2000")
        self.assertEqual(page.index_value_edits[1].text(), "3000")

        page.index_value_edits[0].setText("0x1234")
        page.index_value_edits[1].setText("-1")
        window._set_factory_mode_status(1)
        window.on_index_control_write_indexes()

        self.assertEqual(
            service.write_data_u16_calls[-2:],
            [(0, 0x10, 0x1234, 1.0), (0, 0x20, -1, 1.0)],
        )
        self.assertEqual(service.request_index_values[(0, 0x10)], 0x1234)
        self.assertEqual(service.request_index_values[(0, 0x20)], 0xFFFF)

        window.close()

    def test_periodic_pages_follow_lecu_num_runtime_config(self):
        runtime_config = {
            "BCU_NUM": 2,
            "SAVE_INTERVAL_MS": 500,
            "LECU_NUM": 1,
            "CELL_NUM": 8,
            "CELL_Tem_NUM": 6,
        }
        service = FakeService()
        window = MainWindow(service, runtime_config)

        self.assertEqual(window.voltage_page.group_count, 1)
        self.assertEqual(window.voltage_page.values_per_group, 8)
        self.assertEqual(window.temperature_page.group_count, 1)
        self.assertEqual(window.temperature_page.values_per_group, 6)
        self.assertEqual(window.balance_page.group_count, 1)
        self.assertEqual(window.balance_page.values_per_group, 8)

        window.close()

    def test_window_skips_save_timer_when_snapshot_logging_disabled(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_LOG": 0, "SAVE_INTERVAL_MS": 500}
        service = FakeService(snapshot_logging_enabled=False)
        window = MainWindow(service, runtime_config)

        self.assertFalse(window.save_log_checkbox.isChecked())
        self.assertEqual(window.save_interval_spinbox.value(), 500)
        self.assertFalse(window.save_timer.isActive())

        window.on_save_timer()
        self.assertEqual(service.snapshot_calls, 0)

        window.close()

    def test_window_can_toggle_save_log_from_ui(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_LOG": 0, "SAVE_INTERVAL_MS": 500}
        service = FakeService(snapshot_logging_enabled=False)
        window = MainWindow(service, runtime_config)

        self.assertFalse(window.save_log_checkbox.isChecked())
        self.assertFalse(window.save_timer.isActive())

        window.save_log_checkbox.setChecked(True)
        self.assertTrue(window.snapshot_logging_enabled)
        self.assertTrue(service.snapshot_logging_enabled)
        self.assertEqual(service.snapshot_logging_updates[-1], True)
        self.assertEqual(runtime_config["SAVE_LOG"], 1)
        self.assertTrue(window.save_timer.isActive())
        self.assertEqual(window.save_timer.interval(), 500)
        self.assertIn("\u65e5\u5fd7\u4fdd\u5b58: \u5f00", window.overview_label.text())

        window.save_log_checkbox.setChecked(False)
        self.assertFalse(window.snapshot_logging_enabled)
        self.assertFalse(service.snapshot_logging_enabled)
        self.assertEqual(service.snapshot_logging_updates[-1], False)
        self.assertEqual(runtime_config["SAVE_LOG"], 0)
        self.assertFalse(window.save_timer.isActive())
        self.assertIn("\u65e5\u5fd7\u4fdd\u5b58: \u5173", window.overview_label.text())

        window.close()

    def test_window_can_change_save_interval_from_ui(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_LOG": 1, "SAVE_INTERVAL_MS": 500}
        service = FakeService(snapshot_logging_enabled=True)
        window = MainWindow(service, runtime_config)

        self.assertTrue(window.save_timer.isActive())
        self.assertEqual(window.save_timer.interval(), 500)

        window.save_interval_spinbox.setValue(1200)

        self.assertEqual(window.save_interval_ms, 1200)
        self.assertEqual(runtime_config["SAVE_INTERVAL_MS"], 1200)
        self.assertEqual(window.save_timer.interval(), 1200)
        self.assertIn("\u4fdd\u5b58\u95f4\u9694: 1200 ms", window.overview_label.text())

        window.close()

    def test_window_can_load_dbc_file_from_ui(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)
        fake_runtime = SimpleNamespace(
            dbc_path=r"D:\dbc\custom.dbc",
            catalog_by_address={
                "00": [
                    {
                        "row_key": "custom.row",
                        "message_name": "CUSTOM_MSG",
                        "signal_name": "CUSTOM_SIG",
                        "unit": "A",
                    }
                ],
                "A0": [],
                "A1": [],
            },
        )

        with patch(
            "presentation.main_window.QFileDialog.getOpenFileName",
            return_value=(r"D:\dbc\custom.dbc", "DBC Files (*.dbc)"),
        ), patch(
            "presentation.main_window.DbcRuntime",
            return_value=fake_runtime,
        ):
            window.on_load_dbc_file()

        self.assertIs(service.dbc_runtime_updates[-1], fake_runtime)
        self.assertEqual(window.dbc_table.rowCount(), 1)
        self.assertEqual(window.dbc_table.item(0, 0).text(), "CUSTOM_MSG")
        self.assertEqual(window.dbc_table.item(0, 1).text(), "CUSTOM_SIG")
        self.assertIn(r"D:\dbc\custom.dbc", window.dbc_source_label.text())
        self.assertEqual(runtime_config["DBC_PATH"], r"D:\dbc\custom.dbc")

        window.close()

    def test_query_timer_only_requests_selected_cluster(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        window.cluster_selector.setCurrentIndex(2)
        self.assertEqual(window.selected_cluster_index, 2)

        window.on_query_timer()
        window.on_query_timer()
        window.on_query_timer()
        self.assertEqual(service.query_calls[-3:], [2, 2, 2])
        self.assertEqual(service.balance_query_calls[-3:], [2, 2, 2])

        window.close()

    def test_all_cluster_log_scope_collects_and_saves_all_clusters(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        self.assertEqual(service.active_cluster_calls[-1], 1)

        window.save_scope_selector.setCurrentIndex(1)
        self.assertEqual(window.save_scope_selector.currentData(), "all")
        self.assertEqual(runtime_config["SAVE_LOG_SCOPE"], "all")
        self.assertIsNone(service.active_cluster_calls[-1])

        window.on_query_timer()
        window.on_query_timer()
        window.on_query_timer()
        self.assertEqual(service.query_calls[-3:], [0, 1, 2])
        self.assertEqual(service.balance_query_calls[-3:], [0, 1, 2])

        window.on_save_timer()
        self.assertIsNone(service.snapshot_targets[-1])
        self.assertIn("日志范围: 所有簇", window.overview_label.text())

        window.save_scope_selector.setCurrentIndex(0)
        self.assertEqual(window.save_scope_selector.currentData(), "current")
        self.assertEqual(runtime_config["SAVE_LOG_SCOPE"], "current")
        self.assertEqual(service.active_cluster_calls[-1], window.selected_cluster_index)

        window.on_query_timer()
        self.assertEqual(service.query_calls[-1], window.selected_cluster_index)
        window.on_save_timer()
        self.assertEqual(service.snapshot_targets[-1], window.selected_cluster_index)

        window.close()

    def test_query_timer_slows_down_after_extended_idle_and_recovers_on_rx(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        self.assertEqual(window.query_timer.interval(), window.QUERY_INTERVAL_MS)

        service.poll = lambda: PollResult()
        for _ in range(window.IDLE_QUERY_BACKOFF_POLLS):
            window.on_poll_timer()

        self.assertEqual(
            window.query_timer.interval(),
            window.IDLE_QUERY_INTERVAL_MS,
        )

        service.poll = lambda: PollResult(had_rx_frame=True)
        window.on_poll_timer()

        self.assertEqual(window.query_timer.interval(), window.QUERY_INTERVAL_MS)

        window.close()

    def test_alarm_parameter_page_reads_writes_and_saves_selected_cluster(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)

        window.on_alarm_parameter_read_summary()
        self.assertEqual(service.alarm_summary_calls, [0])
        self.assertEqual(window.alarm_parameter_page.alarm_table.item(0, 2).text(), "3600")
        self.assertEqual(window.alarm_parameter_page.level_boxes[1].value(), 3600)

        window.on_alarm_parameter_selection_changed()
        self.assertEqual(
            service.alarm_record_calls[-1],
            (0, 0, window.AUTO_ALARM_READ_TIMEOUT_S),
        )

        window.alarm_parameter_page.level_boxes[1].setValue(3700)
        window._set_factory_mode_status(1)
        window.on_alarm_parameter_write_current()

        self.assertEqual(service.alarm_write_calls[-1][0], 0)
        written_record = service.alarm_write_calls[-1][1]
        self.assertEqual(written_record.alarm_id, 0)
        self.assertEqual(written_record.values["level1"], 3700)
        self.assertEqual(written_record.values["alarm_on_delay1"], 100)
        self.assertEqual(written_record.values["relay_mask"], 0x0047)
        self.assertEqual(service.alarm_record_calls[-1], (0, 0, 1.0))

        window.on_alarm_parameter_save_flash()
        self.assertEqual(service.alarm_save_flash_calls, [0])

        window.close()

    def test_history_log_page_reads_latest_records_for_selected_cluster(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(2)

        window.on_history_log_read()

        self.assertEqual(service.history_count_calls, [(2, 1)])
        self.assertEqual(
            service.history_entry_calls,
            [(2, 2, 1), (2, 1, 1)],
        )
        self.assertEqual(window.history_log_page.table.rowCount(), 2)
        self.assertEqual(window.history_log_page.table.item(0, 0).text(), "2")
        self.assertEqual(window.history_log_page.table.item(0, 8).text(), "高压互锁故障")
        self.assertIn("成功 2 条", window.history_log_page.status_edit.text())

        window.close()

    def test_history_log_page_can_clear_device_logs(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window._set_factory_mode_status(1)

        with patch(
            "presentation.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.on_history_log_clear_device()

        self.assertEqual(service.history_clear_calls, [window.selected_cluster_index])
        self.assertEqual(window.history_log_page.table.rowCount(), 0)
        self.assertIn("已清空", window.history_log_page.status_edit.text())

        window.close()

    def test_alarm_parameter_buttons_follow_selection_and_factory_mode(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)

        self.assertTrue(window.alarm_parameter_page.read_summary_button.isEnabled())
        self.assertFalse(window.alarm_parameter_page.write_current_button.isEnabled())
        self.assertFalse(window.alarm_parameter_page.save_flash_button.isEnabled())

        window.on_alarm_parameter_read_summary()
        self.assertFalse(window.alarm_parameter_page.write_current_button.isEnabled())
        self.assertFalse(window.alarm_parameter_page.save_flash_button.isEnabled())

        window.on_alarm_parameter_selection_changed()
        self.assertEqual(
            service.alarm_record_calls[-1],
            (0, 0, window.AUTO_ALARM_READ_TIMEOUT_S),
        )
        self.assertTrue(window.alarm_parameter_page.write_current_button.isEnabled())
        self.assertTrue(window.alarm_parameter_page.save_flash_button.isEnabled())
        self.assertTrue(window.alarm_parameter_page.write_current_button.toolTip())

        window._set_factory_mode_status(1)
        self.assertTrue(window.alarm_parameter_page.write_current_button.isEnabled())
        self.assertTrue(window.alarm_parameter_page.save_flash_button.isEnabled())
        self.assertEqual(window.alarm_parameter_page.write_current_button.toolTip(), "")

        window.cluster_selector.setCurrentIndex(2)
        self.assertTrue(window.alarm_parameter_page.read_summary_button.isEnabled())
        self.assertFalse(window.alarm_parameter_page.write_current_button.isEnabled())
        self.assertFalse(window.alarm_parameter_page.save_flash_button.isEnabled())

        window.close()

    def test_alarm_parameter_write_can_auto_enable_factory_mode(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)

        window.on_alarm_parameter_read_summary()
        window.on_alarm_parameter_selection_changed()
        window.alarm_parameter_page.level_boxes[1].setValue(3700)

        with patch(
            "presentation.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.on_alarm_parameter_write_current()

        self.assertEqual(service.work_mode_calls[-1], (0, True))
        self.assertEqual(service.alarm_write_calls[-1][0], 0)
        self.assertEqual(service.alarm_write_calls[-1][1].values["level1"], 3700)
        self.assertEqual(window.factory_mode_status_value, 1)

        window.close()

    def test_alarm_parameter_tab_pauses_background_query_timer(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        self.assertTrue(window.query_timer.isActive())

        window.tabWidget.setCurrentIndex(window.ALARM_PARAMETER_TAB_INDEX)
        self.assertFalse(window.query_timer.isActive())

        window.tabWidget.setCurrentIndex(window.REQUEST_TAB_INDEX)
        self.assertTrue(window.query_timer.isActive())

        window.close()

    def test_alarm_parameter_page_writes_complete_delay_relay_derate_and_enable_fields(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)

        window.alarm_parameter_page.alarm_table.selectRow(0)
        self.app.processEvents()
        page = window.alarm_parameter_page
        page.alarm_on_delay_boxes[1].setValue(10)
        page.alarm_off_delay_boxes[1].setValue(0xFFFD)
        page.relay_on_delay_boxes[3].setValue(30)
        page.derate_charge_boxes[1].setValue(60)
        page.derate_discharge_boxes[1].setValue(40)

        for checkbox in page.relay_checks.values():
            checkbox.setChecked(False)
        page.relay_checks[(1, "放电")].setChecked(True)
        page.relay_checks[(2, "断路器")].setChecked(True)
        page.relay_checks[(3, "充电")].setChecked(True)

        for level in range(1, 6):
            page.display_level_checks[level].setChecked(level in (1, 3, 5))

        window._set_factory_mode_status(1)
        window.on_alarm_parameter_write_current()

        written_record = service.alarm_write_calls[-1][1]
        self.assertTrue(written_record.is_complete)
        self.assertEqual(written_record.values["alarm_on_delay1"], 10)
        self.assertEqual(written_record.values["alarm_off_delay1"], 0xFFFD)
        self.assertEqual(written_record.values["relay_on_delay3"], 30)
        self.assertEqual(written_record.values["derate1"], 0x3C28)
        self.assertEqual(written_record.values["relay_mask"], 0x0421)
        self.assertEqual(written_record.values["display_level"], 0x0015)
        self.assertEqual(len(written_record.values), 30)

        window.close()

    def test_factory_mode_buttons_use_selected_cluster(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}
        service = FakeService()
        window = MainWindow(service, runtime_config)
        window.cluster_selector.setCurrentIndex(0)

        self.assertTrue(window._change_factory_mode(True, show_dialog=False))
        self.assertEqual(service.work_mode_calls[-1], (0, True))
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5f00")

        window.cluster_selector.setCurrentIndex(1)
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5f00")
        self.assertTrue(window._change_factory_mode(False, show_dialog=False))
        self.assertEqual(service.work_mode_calls[-1], (1, False))
        self.assertEqual(window.factory_mode_status_label.text(), "\u5de5\u88c5\u72b6\u6001: \u5173")

        window.close()

    def test_window_repeated_open_close_is_stable(self):
        runtime_config = {"BCU_NUM": 2, "SAVE_INTERVAL_MS": 500}

        for _ in range(20):
            service = FakeService()
            window = MainWindow(service, runtime_config)
            window.show()
            self.app.processEvents()
            window.on_poll_timer()
            window.close()
            self.app.processEvents()
            self.assertTrue(service.closed)


if __name__ == "__main__":
    unittest.main()
