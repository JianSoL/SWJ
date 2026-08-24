import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.can_service import CanApplicationService, security_seed_to_key
from domain.dbc_runtime import DbcRuntime
from domain.legacy_catalog import LegacySignalCatalog
from domain.models import AlarmParameterRecord, BusConfig, LegacySignalDefinition, RawFrame
from infrastructure.cxcanfd_driver import VCI_USBCAN2


class FakeDriver:
    def __init__(self):
        self.sent_can = []
        self.sent_canfd = []
        self.can_frames = []
        self.canfd_frames = []
        self.opened = False
        self.closed = False
        self.open_calls = 0
        self.close_calls = 0
        self.receive_can_args = []
        self.receive_canfd_args = []

    def open(self, config):
        self.open_calls += 1
        self.opened = True
        self.closed = False
        self.config = config

    def close(self):
        self.close_calls += 1
        self.closed = True

    def send_can(self, frame):
        self.sent_can.append(frame)
        return 1

    def send_canfd(self, frame):
        self.sent_canfd.append(frame)
        return 1

    def receive_can(self, max_count=200, timeout_ms=None):
        self.receive_can_args.append((max_count, timeout_ms))
        frames = self.can_frames[:max_count]
        self.can_frames = self.can_frames[max_count:]
        return frames

    def receive_canfd(self, max_count=200, timeout_ms=None):
        self.receive_canfd_args.append((max_count, timeout_ms))
        frames = self.canfd_frames[:max_count]
        self.canfd_frames = self.canfd_frames[max_count:]
        return frames


class NullLogManager:
    def __init__(self):
        self.tx_rows = []
        self.rx_rows = []
        self.dbc_rows = []
        self.cluster_rows = []
        self.voltage_rows = []
        self.temperature_rows = []
        self.balance_temperature_rows = []
        self.balance_rows = []
        self.layout_updates = []

    def log_tx(self, frame_kind, target_index, frame, result):
        self.tx_rows.append((frame_kind, target_index, frame.frame_id, result))

    def log_rx(self, frame_kind, frame, extra_fields=None):
        self.rx_rows.append((frame_kind, frame.frame_id, list(frame.data), list(extra_fields or [])))

    def log_dbc(self, frame_kind, frame, decoded):
        self.dbc_rows.append((frame_kind, frame.frame_id, decoded["frame_id"], decoded["message_name"], len(decoded["signals"])))

    def write_cluster_snapshot(self, cluster_index, signal_state):
        self.cluster_rows.append((cluster_index, dict(signal_state)))

    def write_voltage_snapshot(self, address, values):
        self.voltage_rows.append((address, list(values)))

    def write_temperature_snapshot(self, address, values):
        self.temperature_rows.append((address, list(values)))

    def write_balance_temperature_snapshot(self, address, values):
        self.balance_temperature_rows.append((address, list(values)))

    def write_balance_snapshot(self, address, values):
        self.balance_rows.append((address, list(values)))

    def update_layout(
        self,
        cluster_indices,
        cluster_addresses,
        legacy_signal_names=None,
        voltage_count=0,
        temperature_count=0,
        balance_module_count=0,
        balance_cells_per_module=0,
        balance_temperature_per_module=0,
    ):
        self.layout_updates.append(
            {
                "cluster_indices": list(cluster_indices),
                "cluster_addresses": list(cluster_addresses),
                "legacy_signal_names": (
                    None
                    if legacy_signal_names is None
                    else list(legacy_signal_names)
                ),
                "voltage_count": voltage_count,
                "temperature_count": temperature_count,
                "balance_module_count": balance_module_count,
                "balance_cells_per_module": balance_cells_per_module,
                "balance_temperature_per_module": balance_temperature_per_module,
            }
        )

    def update_legacy_signal_names(self, legacy_signal_names):
        self.legacy_signal_names = list(legacy_signal_names)


def build_legacy_catalog():
    definitions = [
        LegacySignalDefinition(
            signal_id=0x12345678,
            name="SOC",
            unit="%",
            table_index=0,
            row_index=0,
            bit_start=0,
            bit_length=16,
            signed=False,
            save_to_log=True,
        ),
        LegacySignalDefinition(
            signal_id=0x12345678,
            name="SOH",
            unit="%",
            table_index=1,
            row_index=1,
            bit_start=8,
            bit_length=8,
            signed=False,
            save_to_log=False,
        ),
    ]
    return LegacySignalCatalog(definitions)


class CanServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbc_runtime = DbcRuntime(PROJECT_DIR.parent / "DCFDV1.3.dbc")

    def setUp(self):
        self.driver = FakeDriver()
        self.logger = NullLogManager()
        self.runtime_config = {
            "BCU_NUM": 2,
            "ADDRESLIST": ["00", "A0", "A1"],
        }
        self.bus_config = BusConfig(
            can_type=VCI_USBCAN2,
            device_index=0,
            channel_index=0,
            arbitration_baud=500000,
            data_baud=2000000,
        )
        self.service = CanApplicationService(
            runtime_config=self.runtime_config,
            bus_config=self.bus_config,
            driver=self.driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=self.logger,
        )
        self.service.open()

    @staticmethod
    def _read_var_response(frame_id, data_id, value, success=1):
        return RawFrame(
            frame_id=frame_id,
            data=(
                int(data_id).to_bytes(4, byteorder="little", signed=False)
                + (int(value) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
                + bytes((int(success), 0x00))
            ),
            is_fd=True,
            extern_flag=True,
            remote_flag=False,
            brs=True,
        )

    @staticmethod
    def _write_var_response(frame_id, data_id, success=1):
        return RawFrame(
            frame_id=frame_id,
            data=(
                int(data_id).to_bytes(4, byteorder="little", signed=False)
                + int(success).to_bytes(2, byteorder="little", signed=False)
                + b"\x00\x00"
            ),
            is_fd=True,
            extern_flag=True,
            remote_flag=False,
            brs=True,
        )

    @staticmethod
    def _history_time(year, month, day, hour, minute, second):
        return (
            ((int(year) - 2000) & 0x3F)
            | ((int(month) & 0x0F) << 6)
            | ((int(day) & 0x1F) << 10)
            | ((int(hour) & 0x1F) << 15)
            | ((int(minute) & 0x3F) << 20)
            | ((int(second) & 0x3F) << 26)
        )

    @staticmethod
    def _cell_voltage_info(voltage, bcu, csu, cell):
        return (
            (int(voltage) & 0x3FFF)
            | ((int(bcu) & 0x3F) << 14)
            | ((int(csu) & 0x3F) << 20)
            | ((int(cell) & 0x3F) << 26)
        )

    @staticmethod
    def _cell_temperature_position(bcu, csu, cell):
        return (
            (int(bcu) & 0x1F)
            | ((int(csu) & 0x1F) << 5)
            | ((int(cell) & 0x3F) << 10)
        )

    def _history_log_payload(self, sequence=7):
        payload = bytearray(52)
        payload[0:2] = int(sequence).to_bytes(2, "little")
        payload[2] = 3
        payload[3] = 2
        payload[4:8] = self._history_time(2026, 6, 2, 16, 5, 32).to_bytes(4, "little")
        payload[8] = 0b00001001
        payload[9] = 1
        payload[10:12] = (34).to_bytes(2, "little")
        alarm_info = (4) | (0 << 7) | (0 << 14) | (3 << 18) | (32 << 24)
        payload[12:16] = alarm_info.to_bytes(4, "little")
        payload[16:18] = (3156).to_bytes(2, "little")
        payload[18:20] = (0).to_bytes(2, "little", signed=True)
        payload[20:22] = (838).to_bytes(2, "little")
        payload[22:24] = (1000).to_bytes(2, "little")
        payload[24:26] = (20000).to_bytes(2, "little")
        payload[26:28] = (20000).to_bytes(2, "little")
        payload[28:30] = (181).to_bytes(2, "little")
        payload[30:32] = (101).to_bytes(2, "little")
        payload[32:36] = self._cell_voltage_info(3452, 1, 2, 11).to_bytes(4, "little")
        payload[36:40] = self._cell_voltage_info(3283, 1, 2, 82).to_bytes(4, "little")
        payload[40:42] = (391).to_bytes(2, "little", signed=True)
        payload[42:44] = self._cell_temperature_position(1, 2, 11).to_bytes(2, "little")
        payload[44:46] = (274).to_bytes(2, "little", signed=True)
        payload[46:48] = self._cell_temperature_position(1, 2, 82).to_bytes(2, "little")
        payload[48:50] = (2000).to_bytes(2, "little", signed=True)
        payload[50:52] = (2100).to_bytes(2, "little", signed=True)
        return bytes(payload)

    def test_send_next_query_supports_cluster_zero(self):
        result = self.service.send_next_query(0)
        self.assertEqual(result, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        frame = self.driver.sent_can[0]
        self.assertEqual(frame.frame_id, 0x188000F2)
        self.assertEqual(frame.data[:4], bytes.fromhex("78563412"))

    def test_send_next_query_uses_cluster_address(self):
        result = self.service.send_next_query(1)
        self.assertEqual(result, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        frame = self.driver.sent_can[0]
        self.assertEqual(frame.frame_id, 0x1880A0F2)
        self.assertEqual(frame.data[:4], bytes.fromhex("78563412"))

    def test_request_and_balance_queries_use_configured_addresses_without_cluster_zero(self):
        driver = FakeDriver()
        service = CanApplicationService(
            runtime_config={"BCU_NUM": 2, "ADDRESLIST": ["A0", "A1"]},
            bus_config=self.bus_config,
            driver=driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=NullLogManager(),
        )
        service.open()

        service.send_next_query(0)
        service.send_next_balance_query(1)

        self.assertEqual(driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(driver.sent_can[1].frame_id, 0x1880A1F2)

    def test_send_next_query_maintains_independent_cursor_per_cluster(self):
        catalog = LegacySignalCatalog(
            [
                LegacySignalDefinition(
                    signal_id=0x11111111,
                    name="SIG_A",
                    unit="",
                    table_index=0,
                    row_index=0,
                    bit_start=0,
                    bit_length=16,
                    signed=False,
                    save_to_log=False,
                ),
                LegacySignalDefinition(
                    signal_id=0x22222222,
                    name="SIG_B",
                    unit="",
                    table_index=0,
                    row_index=1,
                    bit_start=0,
                    bit_length=16,
                    signed=False,
                    save_to_log=False,
                ),
            ]
        )
        service = CanApplicationService(
            runtime_config=self.runtime_config,
            bus_config=self.bus_config,
            driver=self.driver,
            legacy_catalog=catalog,
            dbc_runtime=self.dbc_runtime,
            log_manager=self.logger,
        )
        service.open()

        service.send_next_query(0)
        service.send_next_query(1)
        service.send_next_query(0)
        service.send_next_query(1)

        self.assertEqual(self.driver.sent_can[0].data[:4], bytes.fromhex("11111111"))
        self.assertEqual(self.driver.sent_can[1].data[:4], bytes.fromhex("11111111"))
        self.assertEqual(self.driver.sent_can[2].data[:4], bytes.fromhex("22222222"))
        self.assertEqual(self.driver.sent_can[3].data[:4], bytes.fromhex("22222222"))

    def test_custom_request_groups_drive_query_and_decode(self):
        driver = FakeDriver()
        logger = NullLogManager()
        runtime_config = dict(self.runtime_config)
        runtime_config["REQUEST_GROUPS"] = [
            [
                {
                    "index": "0x315",
                    "name": "Hall current",
                    "unit": "0.1A",
                    "signed": True,
                }
            ],
            [
                {
                    "index": 0x90401,
                    "name": "LECU count",
                    "unit": "",
                    "signed": False,
                }
            ],
        ]
        service = CanApplicationService(
            runtime_config=runtime_config,
            bus_config=self.bus_config,
            driver=driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=logger,
        )
        service.open()

        service.send_next_query(1)
        driver.can_frames.append(self._read_var_response(0x1881F2A0, 0x315, 0xFFFE))
        poll_result = service.poll()

        self.assertEqual(driver.sent_can[0].data[:4], bytes.fromhex("15030000"))
        update = next(
            item
            for item in poll_result.legacy_updates
            if item.table_index == 0 and item.row_index == 0
        )
        self.assertEqual(update.signal_name, "Hall current")
        self.assertEqual(update.value, "-2")
        self.assertEqual(update.unit, "0.1A")
        self.assertEqual(update.table_index, 0)
        self.assertEqual(update.row_index, 0)

    def test_custom_request_group_is_added_to_snapshot_log(self):
        driver = FakeDriver()
        logger = NullLogManager()
        runtime_config = dict(self.runtime_config)
        runtime_config["REQUEST_GROUPS"] = [
            [
                {
                    "index": 0x12345678,
                    "name": "Renamed SOC",
                    "unit": "custom",
                    "bit_start": 8,
                    "bit_length": 8,
                    "signed": False,
                }
            ]
        ]
        service = CanApplicationService(
            runtime_config=runtime_config,
            bus_config=self.bus_config,
            driver=driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=logger,
        )
        service.open()

        driver.can_frames.append(
            self._read_var_response(0x1881F200, 0x12345678, 0x1234)
        )
        poll_result = service.poll()
        service.write_legacy_snapshots(0)

        self.assertEqual(len(poll_result.legacy_updates), 1)
        self.assertEqual(poll_result.legacy_updates[0].signal_name, "Renamed SOC")
        self.assertEqual(poll_result.legacy_updates[0].value, "18")
        self.assertEqual(service.legacy_signal_state[0]["SOC"], "4660")
        self.assertEqual(service.legacy_signal_state[0]["Renamed SOC"], "18")
        self.assertEqual(logger.cluster_rows[0][1]["SOC"], "4660")
        self.assertEqual(logger.cluster_rows[0][1]["Renamed SOC"], "18")
        self.assertEqual(logger.legacy_signal_names, ["SOC", "Renamed SOC"])

    def test_send_next_balance_query_uses_balance_signal_id(self):
        result = self.service.send_next_balance_query(1)

        self.assertEqual(result, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        frame = self.driver.sent_can[0]
        self.assertEqual(frame.frame_id, 0x1880A0F2)
        self.assertEqual(frame.data[:4], bytes.fromhex("1E100000"))

    def test_send_next_balance_query_uses_module_stride_from_table(self):
        for _ in range(8):
            self.service.send_next_balance_query(1)

        frame = self.driver.sent_can[-1]
        self.assertEqual(frame.data[:4], bytes.fromhex("25100000"))

        self.service.send_next_balance_query(1)
        frame = self.driver.sent_can[-1]
        self.assertEqual(frame.data[:4], bytes.fromhex("D6140000"))

    def test_balance_module_count_defaults_to_lecu_num_when_present(self):
        runtime_config = dict(self.runtime_config)
        runtime_config["LECU_NUM"] = 1
        service = CanApplicationService(
            runtime_config=runtime_config,
            bus_config=self.bus_config,
            driver=self.driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=self.logger,
        )

        self.assertEqual(service.balance_module_count, 1)
        self.assertEqual(len(service.balance_request_signal_ids), 8)

    def test_runtime_request_group_change_rebuilds_snapshot_log_columns(self):
        self.service.set_active_cluster(0)
        self.service.update_runtime_config(
            {
                "REQUEST_GROUPS": [
                    [],
                    [],
                    [
                        {
                            "index": 803,
                            "name": "请求分组3-803",
                            "unit": "",
                            "signed": False,
                        }
                    ],
                ]
            }
        )

        self.driver.can_frames.append(
            self._read_var_response(0x1881F200, 803, 12)
        )
        self.service.poll()
        self.service.write_legacy_snapshots(0)

        self.assertEqual(
            self.logger.legacy_signal_names,
            ["SOC", "请求分组3-803"],
        )
        self.assertEqual(
            self.logger.cluster_rows[-1][1]["请求分组3-803"],
            "12",
        )
        self.assertEqual(self.logger.layout_updates, [])

    def test_update_runtime_config_rebuilds_cluster_and_balance_layout(self):
        self.service.set_active_cluster(2)

        self.service.update_runtime_config(
            {
                "BCU_NUM": 1,
                "LECU_NUM": 2,
                "CELL_NUM": 12,
                "CELL_Tem_NUM": 7,
                "BALANCE_CELLS_PER_MODULE": 10,
                "BALANCE_TEMP_PER_MODULE": 6,
                "ADDRESLIST": ["00", "B0"],
                "ADDRESLIST0x": ["0xB0"],
            }
        )

        self.assertEqual(self.service.cluster_indices, [0, 1])
        self.assertEqual(self.service.cluster_addresses, ["00", "B0"])
        self.assertEqual(self.service.response_id_to_cluster[0x1881F2B0], 1)
        self.assertEqual(self.service.balance_module_count, 2)
        self.assertEqual(self.service.balance_cells_per_module, 10)
        self.assertEqual(self.service.balance_temperature_per_module, 6)
        self.assertEqual(len(self.service.balance_request_signal_ids), 16)
        self.assertIsNone(self.service.active_cluster_index)
        self.assertEqual(
            self.logger.layout_updates[-1],
            {
                "cluster_indices": [0, 1],
                "cluster_addresses": ["00", "B0"],
                "legacy_signal_names": ["SOC"],
                "voltage_count": 12,
                "temperature_count": 7,
                "balance_module_count": 2,
                "balance_cells_per_module": 10,
                "balance_temperature_per_module": 6,
            },
        )

    def test_bcu_num_is_the_exact_cluster_count(self):
        self.service.update_runtime_config(
            {
                "BCU_NUM": 2,
                "ADDRESLIST": ["A0", "A1", "A2"],
            }
        )

        self.assertEqual(self.service.cluster_indices, [0, 1])
        self.assertEqual(self.service.cluster_addresses, ["A0", "A1"])
        self.assertEqual(
            self.service.cluster_index_to_address,
            {0: "A0", 1: "A1"},
        )
        self.assertNotIn(0x1881F2A2, self.service.response_id_to_cluster)

    def test_optional_address_00_does_not_consume_cluster_count(self):
        self.service.update_runtime_config(
            {
                "BCU_NUM": 2,
                "ADDRESLIST": ["00", "A0", "A1", "A2"],
            }
        )

        self.assertEqual(self.service.cluster_indices, [0, 1, 2])
        self.assertEqual(self.service.cluster_addresses, ["00", "A0", "A1"])
        self.assertEqual(
            self.service.cluster_index_to_address,
            {0: "00", 1: "A0", 2: "A1"},
        )
        self.assertNotIn(0x1881F2A2, self.service.response_id_to_cluster)

    def test_read_factory_test_mode_reads_var_11(self):
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x1881F2A0,
                data=bytes([0x0B, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00]),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        work_mode = self.service.read_factory_test_mode(1)

        self.assertEqual(work_mode, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data, bytes.fromhex("0B00000000000000"))

    def test_read_alarm_parameter_record_uses_alarm_parameter_ids(self):
        response_frame_id = 0x1881F2A0
        fields = self.service.get_alarm_parameter_fields()
        self.service.flush_rx_backlog = lambda *args, **kwargs: 0
        for field in fields:
            data_id = 0x94900 + field.index
            value = 0xFF6A if field.key == "level1" else field.index
            self.driver.canfd_frames.append(
                self._read_var_response(response_frame_id, data_id, value)
            )

        record = self.service.read_alarm_parameter_record(1, 0)

        self.assertEqual(record.alarm_id, 0)
        self.assertEqual(record.code, "001")
        self.assertEqual(record.values["level1"], -150)
        self.assertEqual(record.values["hysteresis1"], 5)
        self.assertEqual(len(self.driver.sent_can), len(fields))
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:4], (0x94900).to_bytes(4, "little"))

    def test_new_alarm_fields_replace_reserved_alarm_definitions(self):
        definitions = self.service.get_alarm_parameter_definitions()

        self.assertEqual(
            definitions[46].name,
            "电池簇充电电池模块电压极差",
        )
        self.assertEqual(
            definitions[47].name,
            "电池簇放电电池模块电压极差",
        )
        self.assertEqual(definitions[48].name, "高压箱风扇故障")

    def test_read_alarm_parameter_record_uses_relaxed_profile_for_downstream_cluster(self):
        calls = []

        def fake_read_data_u16(cluster_index, data_id, timeout_s=1.0, retries=0):
            calls.append((cluster_index, data_id, timeout_s, retries))
            return 0

        self.service.read_data_u16 = fake_read_data_u16

        record = self.service.read_alarm_parameter_record(1, 0, timeout_s=0.5)

        self.assertEqual(record.alarm_id, 0)
        self.assertTrue(calls)
        self.assertEqual(calls[0][0], 1)
        self.assertGreaterEqual(calls[0][2], 1.8)
        self.assertEqual(calls[0][3], 3)

    def test_read_alarm_parameter_record_uses_same_profile_for_another_downstream_cluster(self):
        calls = []

        def fake_read_data_u16(cluster_index, data_id, timeout_s=1.0, retries=0):
            calls.append((cluster_index, data_id, timeout_s, retries))
            return 0

        self.service.read_data_u16 = fake_read_data_u16

        record = self.service.read_alarm_parameter_record(2, 0, timeout_s=0.5)

        self.assertEqual(record.alarm_id, 0)
        self.assertTrue(calls)
        self.assertEqual(calls[0][0], 2)
        self.assertGreaterEqual(calls[0][2], 1.8)
        self.assertEqual(calls[0][3], 3)

    def test_read_data_u16_retries_once_after_timeout(self):
        response_frame_id = 0x1881F2A0
        wait_results = [
            None,
            self._read_var_response(response_frame_id, 0x1234, 0x4567),
        ]
        drain_calls = []
        flush_calls = []

        self.service._wait_for_can_frame = lambda *args, **kwargs: wait_results.pop(0)
        self.service._drain_queued_rx_frames = lambda *args, **kwargs: drain_calls.append(True)
        self.service.flush_rx_backlog = lambda *args, **kwargs: flush_calls.append(True)

        value = self.service.read_data_u16(1, 0x1234, timeout_s=0.01, retries=1)

        self.assertEqual(value, 0x4567)
        self.assertEqual(len(self.driver.sent_can), 2)
        self.assertEqual(len(drain_calls), 1)
        self.assertEqual(len(flush_calls), 1)

    def test_read_data_u16_many_collects_out_of_order_batch_responses(self):
        response_frame_id = 0x1881F2A0
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(response_frame_id, 0x102, 0x22),
                self._read_var_response(response_frame_id, 0x100, 0x20),
                self._read_var_response(response_frame_id, 0x101, 0x21),
            ]
        )

        values = self.service.read_data_u16_many(
            1,
            [0x100, 0x101, 0x102],
            timeout_s=0.05,
            batch_size=3,
        )

        self.assertEqual(values, {0x100: 0x20, 0x101: 0x21, 0x102: 0x22})
        self.assertEqual(len(self.driver.sent_can), 3)

    def test_alarm_parameter_summary_uses_remote_batch_profile(self):
        calls = []

        def fake_read_many(cluster_index, data_ids, **kwargs):
            data_ids = list(data_ids)
            calls.append((cluster_index, data_ids, kwargs))
            return {data_id: data_id & 0xFFFF for data_id in data_ids}

        self.service.read_data_u16_many = fake_read_many

        records = self.service.read_alarm_parameter_summary(1, timeout_s=0.5)

        self.assertEqual(len(records), 64)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 1)
        self.assertEqual(len(calls[0][1]), 640)
        self.assertEqual(calls[0][2]["batch_size"], 4)
        self.assertGreaterEqual(calls[0][2]["timeout_s"], 1.2)
        self.assertEqual(calls[0][2]["retries"], 2)

    def test_poll_uses_nonblocking_receive_when_idle(self):
        self.service.poll()

        self.assertEqual(
            self.driver.receive_can_args[-1],
            (self.service.rx_batch_size, 0),
        )
        self.assertEqual(
            self.driver.receive_canfd_args[-1],
            (self.service.rx_batch_size, 0),
        )

    def test_bus_activity_snapshot_tracks_selected_cluster_tx_and_rx(self):
        initial = self.service.get_bus_activity_snapshot(1)
        self.assertTrue(initial["is_open"])
        self.assertEqual(initial["tx_count"], 0)
        self.assertEqual(initial["rx_count"], 0)

        self.service.send_signal_query(1, 0x12345678)
        after_tx = self.service.get_bus_activity_snapshot(1)
        self.assertEqual(after_tx["tx_attempt_count"], 1)
        self.assertEqual(after_tx["tx_count"], 1)
        self.assertEqual(after_tx["tx_failure_count"], 0)
        self.assertIsNotNone(after_tx["last_tx_age_s"])

        self.driver.canfd_frames.append(
            self._read_var_response(0x1881F2A0, 0x12345678, 88)
        )
        self.service.poll()
        after_rx = self.service.get_bus_activity_snapshot(1)

        self.assertEqual(after_rx["rx_count"], 1)
        self.assertEqual(after_rx["rx_handled_count"], 1)
        self.assertEqual(after_rx["last_rx_frame_id"], 0x1881F2A0)
        self.assertIsNotNone(after_rx["last_rx_age_s"])
        self.assertTrue(after_rx["last_rx_time"])

    def test_poll_drains_multiple_batches_and_coalesces_latest_updates(self):
        self.service.rx_batch_size = 64
        self.service.rx_max_frames_per_poll = 512
        self.service.rx_poll_budget_s = 1.0
        self.driver.canfd_frames.extend(
            self._read_var_response(0x1881F2A0, 0x12345678, value)
            for value in range(300)
        )

        result = self.service.poll()

        self.assertEqual(result.received_frame_count, 300)
        self.assertEqual(result.handled_frame_count, 300)
        self.assertEqual(result.update_count_before_coalesce, 600)
        self.assertEqual(len(result.legacy_updates), 2)
        self.assertEqual(
            {
                update.signal_name: update.value
                for update in result.legacy_updates
            },
            {"SOC": "299", "SOH": "1"},
        )
        self.assertFalse(self.driver.canfd_frames)
        self.assertGreater(len(self.driver.receive_canfd_args), 1)

    def test_read_data_u16_wait_uses_nonblocking_receive(self):
        with self.assertRaises(RuntimeError):
            self.service.read_data_u16(1, 0x1234, timeout_s=0.01)

        self.assertTrue(self.driver.receive_can_args)
        self.assertTrue(self.driver.receive_canfd_args)
        self.assertTrue(all(timeout_ms == 0 for _, timeout_ms in self.driver.receive_can_args))
        self.assertTrue(all(timeout_ms == 0 for _, timeout_ms in self.driver.receive_canfd_args))

    def test_alarm_parameter_field_layout_matches_alarm_struct_payload(self):
        fields = self.service.get_alarm_parameter_fields()

        self.assertEqual(
            [(field.key, field.index, field.signed) for field in fields],
            [
                ("level1", 0, True),
                ("level2", 1, True),
                ("level3", 2, True),
                ("level4", 3, True),
                ("level5", 4, True),
                ("hysteresis1", 5, False),
                ("hysteresis2", 6, False),
                ("hysteresis3", 7, False),
                ("hysteresis4", 8, False),
                ("hysteresis5", 9, False),
                ("alarm_on_delay1", 10, False),
                ("alarm_on_delay2", 11, False),
                ("alarm_on_delay3", 12, False),
                ("alarm_on_delay4", 13, False),
                ("alarm_on_delay5", 14, False),
                ("alarm_off_delay1", 15, False),
                ("alarm_off_delay2", 16, False),
                ("alarm_off_delay3", 17, False),
                ("alarm_off_delay4", 18, False),
                ("alarm_off_delay5", 19, False),
                ("relay_mask", 20, False),
                ("relay_on_delay1", 21, False),
                ("relay_on_delay2", 22, False),
                ("relay_on_delay3", 23, False),
                ("derate1", 24, False),
                ("derate2", 25, False),
                ("derate3", 26, False),
                ("derate4", 27, False),
                ("derate5", 28, False),
                ("display_level", 29, False),
            ],
        )

    def test_read_history_log_count_uses_diag_command_86(self):
        self.service.flush_rx_backlog = lambda *args, **kwargs: 0
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1887F2A0,
                data=bytes([0xFF, 0x01, 0xC0, 0x01, 0, 0, 0, 0]),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )

        count = self.service.read_history_log_count(1)

        self.assertEqual(count, 448)
        self.assertEqual(self.driver.sent_can[-1].frame_id, 0x1886A0F2)
        self.assertEqual(self.driver.sent_can[-1].data[:3], bytes([0x00, 0x00, 0x01]))

    def test_read_history_log_entry_reassembles_chunks_and_decodes_payload(self):
        self.service.flush_rx_backlog = lambda *args, **kwargs: 0
        payload = self._history_log_payload(sequence=7)
        padded = payload.ljust(56, b"\x00")
        for chunk_index in range(8):
            self.driver.can_frames.append(
                RawFrame(
                    frame_id=0x1887F2A0,
                    data=(
                        bytes([chunk_index + 1])
                        + padded[chunk_index * 7 : (chunk_index + 1) * 7]
                    ),
                    is_fd=False,
                    extern_flag=True,
                    remote_flag=False,
                )
            )

        record = self.service.read_history_log_entry(1, 7)

        self.assertEqual(record.sequence, 7)
        self.assertEqual(record.timestamp, "2026-06-02 16:05:32")
        self.assertEqual(record.log_type, "告警日志")
        self.assertEqual(record.log_subtype, "告警产生")
        self.assertEqual(record.run_status, 2)
        self.assertEqual(record.alarm_count, 1)
        self.assertEqual(record.alarm_id, 32)
        self.assertEqual(record.alarm_level, 3)
        self.assertEqual(record.total_voltage, 315.6)
        self.assertEqual(record.soc, 83.8)
        self.assertEqual(record.max_cell_voltage, 3452)
        self.assertEqual(record.max_cell_temperature, 39.1)
        self.assertEqual(record.threshold_value, 2000)
        self.assertEqual(record.actual_value, 2100)
        self.assertEqual(self.driver.sent_can[-1].frame_id, 0x1886A0F2)
        self.assertEqual(self.driver.sent_can[-1].data[:3], bytes([0x07, 0x00, 0x01]))

    def test_write_alarm_parameter_record_encodes_signed_values(self):
        self.driver.canfd_frames.extend(
            [
                self._write_var_response(0x1883F2A0, 0x94900, success=1),
                self._write_var_response(0x1883F2A0, 0x94905, success=1),
            ]
        )
        record = AlarmParameterRecord(
            alarm_id=0,
            code="001",
            name="单体电压过高",
            values={
                "level1": -150,
                "hysteresis1": 20,
            },
        )

        self.assertTrue(self.service.write_alarm_parameter_record(1, record))

        self.assertEqual(len(self.driver.sent_can), 2)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1882A0F2)
        self.assertEqual(self.driver.sent_can[0].data, bytes.fromhex("004909006AFF0000"))
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("0549090014000000"))

    def test_write_alarm_parameter_record_uses_full_record_field_addresses(self):
        self.driver.canfd_frames.extend(
            [
                self._write_var_response(0x1883F2A0, 0x94934, success=1),
                self._write_var_response(0x1883F2A0, 0x94935, success=1),
                self._write_var_response(0x1883F2A0, 0x9493C, success=1),
                self._write_var_response(0x1883F2A0, 0x9493D, success=1),
            ]
        )
        record = AlarmParameterRecord(
            alarm_id=1,
            code="002",
            name="单体电压过低",
            values={
                "relay_mask": 0x0421,
                "relay_on_delay1": 30,
                "derate5": 0x3C28,
                "display_level": 0x0015,
            },
        )

        self.assertTrue(self.service.write_alarm_parameter_record(1, record))

        self.assertEqual(len(self.driver.sent_can), 4)
        self.assertEqual(self.driver.sent_can[0].data, bytes.fromhex("3449090021040000"))
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("354909001E000000"))
        self.assertEqual(self.driver.sent_can[2].data, bytes.fromhex("3C490900283C0000"))
        self.assertEqual(self.driver.sent_can[3].data, bytes.fromhex("3D49090015000000"))

    def test_save_alarm_parameters_to_flash_uses_control_command(self):
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x1889F2A0,
                data=bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        self.assertTrue(self.service.save_alarm_parameters_to_flash(1))

        self.assertEqual(len(self.driver.sent_can), 1)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1888A0F2)
        self.assertEqual(self.driver.sent_can[0].data, bytes.fromhex("0400000008000000"))

    def test_restore_factory_parameters_uses_factory_default_control_command(self):
        self.driver.canfd_frames.extend(
            [
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x06, 0x67, 0x11, 0x12, 0x34, 0x56, 0x78, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x02, 0x67, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1889F2A0,
                    data=bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
            ]
        )

        self.assertTrue(self.service.restore_factory_parameters(1))

        self.assertEqual(len(self.driver.sent_can), 3)
        self.assertEqual(self.driver.sent_can[-1].frame_id, 0x1888A0F2)
        self.assertEqual(self.driver.sent_can[-1].data, bytes.fromhex("0400000002000000"))

    def test_set_factory_test_mode_sends_unlock_and_control_sequence(self):
        seed = 0x12345678
        self.driver.canfd_frames.extend(
            [
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x06, 0x67, 0x11, 0x12, 0x34, 0x56, 0x78, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x02, 0x67, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1889F2A0,
                    data=bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1881F2A0,
                    data=bytes([0x0B, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
            ]
        )

        work_mode = self.service.set_factory_test_mode(1, True)

        self.assertEqual(work_mode, 1)
        self.assertEqual(len(self.driver.sent_can), 4)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:3], bytes([0x02, 0x27, 0x11]))
        self.assertEqual(self.driver.sent_can[1].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[1].data[:3], bytes([0x06, 0x27, 0x12]))
        self.assertEqual(
            self.driver.sent_can[1].data[3:7],
            security_seed_to_key(seed).to_bytes(4, byteorder="big", signed=False),
        )
        self.assertEqual(self.driver.sent_can[2].frame_id, 0x1888A0F2)
        self.assertEqual(self.driver.sent_can[2].data, bytes.fromhex("0100000001000000"))
        self.assertEqual(self.driver.sent_can[3].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[3].data, bytes.fromhex("0B00000000000000"))

    def test_set_factory_test_mode_retries_after_rejected_unlock_seed(self):
        seed = 0x12345678
        self.driver.canfd_frames.extend(
            [
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x03, 0x7F, 0x27, 0x11, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x06, 0x67, 0x11, 0x12, 0x34, 0x56, 0x78, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x02, 0x67, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1889F2A0,
                    data=bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1881F2A0,
                    data=bytes([0x0B, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
            ]
        )

        work_mode = self.service.set_factory_test_mode(1, True)

        self.assertEqual(work_mode, 1)
        self.assertEqual(len(self.driver.sent_can), 5)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:3], bytes([0x02, 0x27, 0x11]))
        self.assertEqual(self.driver.sent_can[1].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[1].data[:3], bytes([0x02, 0x27, 0x11]))
        self.assertEqual(self.driver.sent_can[2].data[:3], bytes([0x06, 0x27, 0x12]))
        self.assertEqual(
            self.driver.sent_can[2].data[3:7],
            security_seed_to_key(seed).to_bytes(4, byteorder="big", signed=False),
        )

    def test_send_next_monitor_query_cycles_monitor_signal_ids(self):
        result = self.service.send_next_monitor_query(1)

        self.assertEqual(result, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:4], bytes.fromhex("0B000000"))

    def test_monitor_query_sequence_contains_lower_controller_system_time_indexes(self):
        requested_ids = []
        for _ in range(len(self.service.index_monitor_signal_ids)):
            self.service.send_next_monitor_query(1)
            requested_ids.append(
                int.from_bytes(self.driver.sent_can[-1].data[:4], byteorder="little")
            )

        self.assertEqual(requested_ids[-6:], list(range(0x25E, 0x264)))

    def test_send_signal_query_uses_requested_active_page_index(self):
        result = self.service.send_signal_query(1, 0x315)

        self.assertEqual(result, 1)
        self.assertEqual(len(self.driver.sent_can), 1)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:4], bytes.fromhex("15030000"))

    def test_send_next_power_diagnostic_query_starts_with_run_status(self):
        result = self.service.send_next_power_diagnostic_query(1)

        self.assertEqual(result, 1)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:4], (12).to_bytes(4, "little"))

    def test_poll_caches_power_diagnostic_index_value(self):
        self.driver.canfd_frames.append(
            self._read_var_response(0x1881F2A0, 791, 1)
        )

        result = self.service.poll()
        snapshot = self.service.get_power_diagnostic_snapshot(1)

        self.assertTrue(result.had_rx_frame)
        self.assertEqual(snapshot[791], 1)

    def test_poll_decodes_monitor_query_values_into_snapshot(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 11, 1),
                self._read_var_response(0x1881F2A0, 0x90401, 4),
                self._read_var_response(0x1881F2A0, 36, 1),
                self._read_var_response(0x1881F2A0, 48, 1),
                self._read_var_response(0x1881F2A0, 112, 250),
            ]
        )

        self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["work_mode"], 1)
        self.assertEqual(snapshot["module_count"], 4)
        self.assertEqual(snapshot["di_states"][0], 1)
        self.assertTrue(snapshot["relay_states"][0])
        self.assertEqual(snapshot["rt_values"][0], 250)

    def test_poll_combines_lower_controller_system_time_protocol_indexes(self):
        values = (2026, 8, 14, 16, 27, 35)
        self.driver.canfd_frames.extend(
            self._read_var_response(0x1881F2A0, data_id, value)
            for data_id, value in zip(range(0x25E, 0x264), values)
        )

        self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["device_time"], "2026-08-14 16:27:35")

    def test_poll_decodes_atomic_bms_send_time_protocol_frame(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1CEDFFA0,
                data=bytes((26, 8, 14, 16, 27, 36, 0, 0)),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )

        result = self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["device_time"], "2026-08-14 16:27:36")
        self.assertEqual(result.legacy_updates[-1].signal_name, "下位机系统时间")
        self.assertEqual(result.legacy_updates[-1].value, "2026-08-14 16:27:36")

    def test_monitor_snapshot_advances_device_time_between_protocol_frames(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1CEDFFA0,
                data=bytes((26, 8, 14, 16, 27, 36, 0, 0)),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        self.service.poll()
        _, received_at = self.service.device_time_anchors[1]

        with patch(
            "application.can_service.time.monotonic",
            return_value=received_at + 2.2,
        ):
            snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["device_time"], "2026-08-14 16:27:38")

    def test_protocol_indexes_recalibrate_device_time_after_atomic_frame(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1CEDFFA0,
                data=bytes((26, 8, 14, 16, 27, 36, 0, 0)),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        self.service.poll()
        self.driver.canfd_frames.extend(
            self._read_var_response(0x1881F2A0, data_id, value)
            for data_id, value in zip(
                range(0x25E, 0x264),
                (2026, 8, 14, 16, 28, 4),
            )
        )

        self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["device_time"], "2026-08-14 16:28:04")

    def test_stale_device_time_sample_does_not_pin_running_clock(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1CEDFFA0,
                data=bytes((26, 8, 14, 16, 27, 36, 0, 0)),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        self.service.poll()
        device_time, received_at = self.service.device_time_anchors[1]

        with patch(
            "application.can_service.time.monotonic",
            return_value=received_at + 2.2,
        ):
            changed = self.service._set_device_time_anchor(1, device_time)
            snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertFalse(changed)
        self.assertEqual(snapshot["device_time"], "2026-08-14 16:27:38")

    def test_poll_ignores_invalid_bms_send_time_protocol_frame(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1CEDFFA0,
                data=bytes((26, 13, 14, 16, 27, 36, 0, 0)),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )

        result = self.service.poll()

        self.assertFalse(result.had_rx_frame)
        self.assertIsNone(self.service.get_index_monitor_snapshot(1)["device_time"])

    def test_monitor_snapshot_hides_incomplete_or_invalid_device_time(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x25E, 2026),
                self._read_var_response(0x1881F2A0, 0x25F, 13),
                self._read_var_response(0x1881F2A0, 0x260, 14),
                self._read_var_response(0x1881F2A0, 0x261, 16),
                self._read_var_response(0x1881F2A0, 0x262, 27),
                self._read_var_response(0x1881F2A0, 0x263, 35),
            ]
        )

        self.service.poll()

        self.assertIsNone(self.service.get_index_monitor_snapshot(1)["device_time"])

    def test_monitor_snapshot_is_independent_from_custom_request_groups(self):
        driver = FakeDriver()
        runtime_config = dict(self.runtime_config)
        runtime_config["REQUEST_GROUPS"] = [[{"index": 0x315, "name": "Hall current"}]]
        service = CanApplicationService(
            runtime_config=runtime_config,
            bus_config=self.bus_config,
            driver=driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=NullLogManager(),
        )
        service.open()
        driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x0D, 5234),
                self._read_var_response(0x1881F2A0, 0x0E, 0xFF38),
                self._read_var_response(0x1881F2A0, 16, 880),
            ]
        )

        service.poll()
        snapshot = service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["system_voltage"], 5234)
        self.assertEqual(snapshot["system_current"], -200)
        self.assertEqual(snapshot["soc"], 880)

    def test_monitor_snapshot_uses_firmware_energy_indexes(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x1FD, 586),
                self._read_var_response(0x1881F2A0, 0x1FE, 12),
                self._read_var_response(0x1881F2A0, 0x252, 25678),
                self._read_var_response(0x1881F2A0, 0x253, 16120),
                self._read_var_response(0x1881F2A0, 0x90885, 5871),
                self._read_var_response(0x1881F2A0, 0x90886, 0),
            ]
        )

        self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["single_charge_kwh"], 586)
        self.assertEqual(snapshot["single_discharge_kwh"], 12)
        self.assertEqual(snapshot["remaining_discharge_kwh"], 25678)
        self.assertEqual(snapshot["remaining_charge_kwh"], 16120)
        self.assertEqual(snapshot["total_charge_kwh"], 5871)

    def test_monitor_snapshot_uses_bcu615_60s_power_and_current_indexes(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x1AD, 1200),
                self._read_var_response(0x1881F2A0, 0x1AE, 21000),
                self._read_var_response(0x1881F2A0, 0x1AF, 900),
                self._read_var_response(0x1881F2A0, 0x1B0, 19000),
            ]
        )

        self.service.poll()
        snapshot = self.service.get_index_monitor_snapshot(1)

        self.assertEqual(snapshot["continuous_discharge_current"], 1200)
        self.assertEqual(snapshot["continuous_discharge_power"], 21000)
        self.assertEqual(snapshot["continuous_charge_current"], 900)
        self.assertEqual(snapshot["continuous_charge_power"], 19000)

    def test_control_channel_sends_unlock_and_control_sequence(self):
        seed = 0x12345678
        self.driver.canfd_frames.extend(
            [
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x06, 0x67, 0x11, 0x12, 0x34, 0x56, 0x78, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x18A1F2A0,
                    data=bytes([0x02, 0x67, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x1889F2A0,
                    data=bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
            ]
        )

        self.assertTrue(self.service.control_channel(1, 3, True))

        self.assertEqual(len(self.driver.sent_can), 3)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[1].frame_id, 0x18A0A0F2)
        self.assertEqual(self.driver.sent_can[2].frame_id, 0x1888A0F2)
        self.assertEqual(self.driver.sent_can[2].data, bytes.fromhex("0200030001000000"))

    def test_set_balance_cell_state_reads_word_sets_bit_and_writes_config_index(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x101E, 0x0005),
                self._write_var_response(0x1883F2A0, 0x101E, success=1),
            ]
        )

        word_value = self.service.set_balance_cell_state(1, 0, 1, True)

        self.assertEqual(word_value, 0x0007)
        self.assertEqual(len(self.driver.sent_can), 2)
        self.assertEqual(self.driver.sent_can[0].frame_id, 0x1880A0F2)
        self.assertEqual(self.driver.sent_can[0].data[:4], (0x101E).to_bytes(4, "little"))
        self.assertEqual(self.driver.sent_can[1].frame_id, 0x1882A0F2)
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("1E10000007000000"))

    def test_set_balance_cell_state_uses_next_balance_config_word(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x1024, 0x0001),
                self._write_var_response(0x1883F2A0, 0x1024, success=1),
            ]
        )

        word_value = self.service.set_balance_cell_state(1, 0, 96, False)

        self.assertEqual(word_value, 0x0000)
        self.assertEqual(self.driver.sent_can[0].data[:4], (0x1024).to_bytes(4, "little"))
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("2410000000000000"))

    def test_set_balance_cell_state_uses_updated_stride_for_second_module(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x14D6, 0x0000),
                self._write_var_response(0x1883F2A0, 0x14D6, success=1),
            ]
        )

        word_value = self.service.set_balance_cell_state(1, 1, 0, True)

        self.assertEqual(word_value, 0x0001)
        self.assertEqual(self.driver.sent_can[0].data[:4], bytes.fromhex("D6140000"))
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("D614000001000000"))

    def test_set_balance_cell_state_keeps_manual_bits_when_readback_is_zero(self):
        self.driver.canfd_frames.extend(
            [
                self._read_var_response(0x1881F2A0, 0x101E, 0x0000),
                self._write_var_response(0x1883F2A0, 0x101E, success=1),
                self._write_var_response(0x1883F2A0, 0x101E, success=1),
            ]
        )

        first_word = self.service.set_balance_cell_state(1, 0, 0, True)
        second_word = self.service.set_balance_cell_state(1, 0, 1, True)

        self.assertEqual(first_word, 0x0001)
        self.assertEqual(second_word, 0x0003)
        self.assertEqual(len(self.driver.sent_can), 3)
        self.assertEqual(self.driver.sent_can[0].data[:4], (0x101E).to_bytes(4, "little"))
        self.assertEqual(self.driver.sent_can[1].data, bytes.fromhex("1E10000001000000"))
        self.assertEqual(self.driver.sent_can[2].data, bytes.fromhex("1E10000003000000"))

    def test_balance_decode_uses_device_readback_for_status_display(self):
        self.service.balance_control_words["A0"][0x101E] = 0x0003
        self.driver.canfd_frames.append(
            self._read_var_response(0x1881F2A0, 0x101E, 0x0000),
        )

        poll_result = self.service.poll()
        balance_values = self.service.get_legacy_balance_state_values("A0")

        self.assertEqual(poll_result.balance_updates, ["A0"])
        self.assertEqual(balance_values[0], ("M1-001", 0))
        self.assertEqual(balance_values[1], ("M1-002", 0))
        self.assertEqual(balance_values[2], ("M1-003", 0))

    def test_poll_decodes_legacy_response(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1881F200,
                data=bytes.fromhex("7856341234120000"),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        poll_result = self.service.poll()
        self.assertEqual(len(poll_result.legacy_updates), 2)
        self.assertEqual(poll_result.legacy_updates[0].cluster_index, 0)
        self.assertEqual(poll_result.legacy_updates[0].signal_name, "SOC")
        self.assertEqual(poll_result.legacy_updates[0].value, "4660")
        self.assertEqual(poll_result.legacy_updates[1].signal_name, "SOH")
        self.assertEqual(self.service.legacy_signal_state[0]["SOC"], "4660")

    def test_poll_ignores_non_active_cluster_legacy_frames(self):
        self.service.set_active_cluster(1)
        self.driver.can_frames.extend(
            [
                RawFrame(
                    frame_id=0x1881F200,
                    data=bytes.fromhex("7856341234120000"),
                    is_fd=False,
                    extern_flag=True,
                    remote_flag=False,
                ),
                RawFrame(
                    frame_id=0x1881F2A0,
                    data=bytes.fromhex("7856341278560000"),
                    is_fd=False,
                    extern_flag=True,
                    remote_flag=False,
                ),
            ]
        )

        poll_result = self.service.poll()

        self.assertTrue(poll_result.had_rx_frame)
        self.assertEqual(len(poll_result.legacy_updates), 2)
        self.assertTrue(all(update.cluster_index == 1 for update in poll_result.legacy_updates))
        self.assertEqual(self.service.legacy_signal_state[0]["SOC"], "0")
        self.assertEqual(self.service.legacy_signal_state[1]["SOC"], "22136")

    def test_poll_decodes_balance_bitmap_response(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1881F200,
                data=bytes.fromhex("1E10000005000000"),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )

        poll_result = self.service.poll()
        balance_values = self.service.get_legacy_balance_state_values("00")

        self.assertFalse(poll_result.legacy_updates)
        self.assertEqual(poll_result.balance_updates, ["00"])
        self.assertEqual(balance_values[0], ("M1-001", 1))
        self.assertEqual(balance_values[1], ("M1-002", 0))
        self.assertEqual(balance_values[2], ("M1-003", 1))

    def test_poll_decodes_balance_bitmap_response_for_second_module(self):
        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1881F200,
                data=bytes.fromhex("D614000003000000"),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )

        self.service.poll()
        balance_values = self.service.get_legacy_balance_state_values("00")

        self.assertEqual(balance_values[104], ("M2-001", 1))
        self.assertEqual(balance_values[105], ("M2-002", 1))
        self.assertEqual(balance_values[106], ("M2-003", 0))

    def test_poll_decodes_periodic_alias_frame(self):
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x1201EF00,
                data=bytes(64),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )
        poll_result = self.service.poll()
        self.assertTrue(poll_result.periodic_updates)
        self.assertIn("00", poll_result.periodic_status)
        self.assertTrue(self.logger.rx_rows)
        self.assertTrue(self.logger.dbc_rows)
        self.assertEqual(self.logger.dbc_rows[0][2], 0x1201EFA0)

    def test_poll_decodes_periodic_a1_frame_using_a0_template(self):
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x1201EFA1,
                data=bytes(64),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        poll_result = self.service.poll()

        self.assertTrue(poll_result.periodic_updates)
        self.assertIn("A1", poll_result.periodic_status)
        self.assertEqual(poll_result.periodic_updates[0].address, "A1")
        catalog = self.service.get_dbc_catalog("A1")
        self.assertTrue(catalog)
        message_row = next(
            row for row in catalog if row["row_key"].startswith("BCU1201EFA0.")
        )
        self.assertEqual(message_row["message_name"], "BCU1201EFA1")
        self.assertEqual(poll_result.periodic_updates[0].message_name, "BCU1201EFA1")
        self.assertIn("BCU1201EFA1", poll_result.periodic_status["A1"])
        self.assertEqual(self.logger.dbc_rows[0][3], "BCU1201EFA1")
        self.assertEqual(self.logger.dbc_rows[0][2], 0x1201EFA0)

    def test_poll_caches_alarm_message_0x1204efa0_and_terminal_temperature_values(self):
        self.driver.canfd_frames.extend(
            [
                RawFrame(
                    frame_id=0x1204EFA0,
                    data=bytes([0xFF] * 64),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
                RawFrame(
                    frame_id=0x12C1EF00,
                    data=bytes(64),
                    is_fd=True,
                    extern_flag=True,
                    remote_flag=False,
                    brs=True,
                ),
            ]
        )

        self.service.poll()

        self.assertTrue(self.service.get_periodic_alarm_state_values("A0"))
        self.assertTrue(self.service.get_periodic_terminal_temperature_values("00"))
        self.assertEqual(self.service.get_periodic_alarm_state_values("A0")[0][0], "001")
        self.assertEqual(self.service.get_periodic_alarm_state_values("A0")[0][1], 15)
        self.assertEqual(self.service.get_periodic_terminal_temperature_values("00")[0][0], "01_1")
        self.assertEqual(self.logger.dbc_rows[0][2], 0x1204EFA0)

    def test_poll_decodes_balance_temperature_frame_0x12c9(self):
        payload = bytearray(64)
        for index, value in enumerate([250, -51, 0]):
            payload[index * 2 : index * 2 + 2] = int(value).to_bytes(
                2,
                "little",
                signed=True,
            )
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x12C9EFA0,
                data=bytes(payload),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        poll_result = self.service.poll()

        values = self.service.get_periodic_balance_temperature_values("A0")
        self.assertEqual(values[0], 25)
        self.assertAlmostEqual(values[1], -5.1)
        self.assertEqual(values[2], 0)
        self.assertEqual(len(values), 32)
        self.assertEqual(len(poll_result.periodic_updates), 32)
        self.assertIn("A0", poll_result.periodic_status)
        self.assertEqual(self.logger.dbc_rows[0][2], 0x12C9EFA0)
        self.assertEqual(self.logger.dbc_rows[0][3], "BCU12C9EFA0")

    def test_poll_decodes_balance_temperature_second_frame_with_offset(self):
        self.service.update_runtime_config(
            {
                "BCU_NUM": 1,
                "LECU_NUM": 2,
                "BALANCE_TEMP_PER_MODULE": 20,
                "ADDRESLIST": ["00", "A0"],
                "ADDRESLIST0x": ["0xA0"],
            }
        )
        payload = bytearray(64)
        payload[0:2] = (321).to_bytes(2, "little", signed=True)
        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x12CAEFA0,
                data=bytes(payload),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        self.service.poll()

        values = self.service.get_periodic_balance_temperature_values("A0")
        self.assertIsNone(values[31])
        self.assertAlmostEqual(values[32], 32.1)
        self.assertEqual(len(values), 40)

    def test_poll_uses_alarm_name_mapping_from_runtime_config(self):
        self.runtime_config["Alarm_name_key"] = {
            "001": "单体电压过高",
            "009": "单体压差过大",
            "047": "电池簇充电电池模块电压极差",
            "048": "电池簇放电电池模块电压极差",
            "049": "高压箱风扇故障",
        }
        self.service = CanApplicationService(
            runtime_config=self.runtime_config,
            bus_config=self.bus_config,
            driver=self.driver,
            legacy_catalog=build_legacy_catalog(),
            dbc_runtime=self.dbc_runtime,
            log_manager=self.logger,
        )
        self.service.open()

        self.driver.canfd_frames.append(
            RawFrame(
                frame_id=0x1204EFA0,
                data=bytes([0xFF] * 64),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
        )

        self.service.poll()

        alarm_values = self.service.get_periodic_alarm_state_values("A0")
        self.assertEqual(alarm_values[0][0], "001 单体电压过高")
        self.assertEqual(alarm_values[8][0], "009 单体压差过大")
        self.assertEqual(
            alarm_values[46][0],
            "047 电池簇充电电池模块电压极差",
        )
        self.assertEqual(
            alarm_values[47][0],
            "048 电池簇放电电池模块电压极差",
        )
        self.assertEqual(alarm_values[48][0], "049 高压箱风扇故障")

    def test_set_dbc_runtime_rebuilds_catalogs_and_clears_periodic_caches(self):
        self.service.periodic_voltage_values["00"][1] = 123
        self.service.periodic_temperature_values["00"][1] = 45
        self.service.periodic_alarm_values["00"]["001"] = 2

        self.service.set_dbc_runtime(None)

        self.assertEqual(self.service.get_dbc_catalog("00"), [])
        self.assertEqual(self.service.get_periodic_voltage_values("00"), [])
        self.assertEqual(self.service.get_periodic_temperature_values("00"), [])
        self.assertEqual(self.service.get_periodic_alarm_state_values("00"), [])

        self.service.set_dbc_runtime(self.dbc_runtime)
        self.assertTrue(self.service.get_dbc_catalog("00"))

    def test_write_legacy_snapshots_uses_logger(self):
        self.service.write_legacy_snapshots()
        self.assertEqual(len(self.logger.cluster_rows), 3)

    def test_write_legacy_snapshots_writes_current_state_each_interval(self):
        self.service.write_legacy_snapshots()
        self.service.write_legacy_snapshots()
        self.assertEqual(len(self.logger.cluster_rows), 6)

        self.driver.can_frames.append(
            RawFrame(
                frame_id=0x1881F2A0,
                data=bytes.fromhex("7856341234120000"),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )
        )
        self.service.poll()
        self.service.write_legacy_snapshots()
        self.assertEqual(len(self.logger.cluster_rows), 9)
        cluster_1_rows = [
            row for row in self.logger.cluster_rows[-3:] if row[0] == 1
        ]
        self.assertEqual(len(cluster_1_rows), 1)
        self.assertEqual(cluster_1_rows[0][1]["SOC"], "4660")

    def test_write_legacy_snapshots_logs_voltage_temperature_and_balance(self):
        self.service.periodic_voltage_values["00"][1] = 3301
        self.service.periodic_voltage_dirty["00"] = True
        self.service.periodic_temperature_values["00"][1] = 27.5
        self.service.periodic_temperature_dirty["00"] = True
        self.service.legacy_balance_values["00"][0] = 1
        self.service.legacy_balance_dirty["00"] = True

        self.service.write_legacy_snapshots()

        self.assertEqual(self.logger.voltage_rows[-1][0], "00")
        self.assertEqual(self.logger.voltage_rows[-1][1][0], 3301)
        self.assertEqual(self.logger.temperature_rows[-1][0], "00")
        self.assertEqual(self.logger.temperature_rows[-1][1][0], 27.5)
        self.assertEqual(self.logger.balance_rows[-1][0], "00")
        self.assertEqual(self.logger.balance_rows[-1][1][0], 1)

    def test_write_legacy_snapshots_can_limit_to_selected_cluster(self):
        self.service.legacy_signal_state[0]["SOC"] = "11"
        self.service.legacy_signal_state[1]["SOC"] = "22"
        self.service.legacy_signal_dirty[0] = True
        self.service.legacy_signal_dirty[1] = True
        self.service.periodic_voltage_values["00"][1] = 3301
        self.service.periodic_voltage_dirty["00"] = True
        self.service.periodic_voltage_values["A0"][1] = 3402
        self.service.periodic_voltage_dirty["A0"] = True

        self.service.write_legacy_snapshots(1)

        self.assertEqual(len(self.logger.cluster_rows), 1)
        self.assertEqual(self.logger.cluster_rows[0][0], 1)
        self.assertEqual(len(self.logger.voltage_rows), 1)
        self.assertEqual(self.logger.voltage_rows[0][0], "A0")
        self.assertTrue(self.service.legacy_signal_dirty[0])
        self.assertFalse(self.service.legacy_signal_dirty[1])

    def test_reopen_updates_bus_config_and_resets_runtime_state(self):
        self.service.periodic_voltage_values["00"][1] = 3300
        self.service.legacy_signal_state[0]["SOC"] = "99"
        self.service.query_cursors[0] = 1
        self.service.query_cursors[1] = 1

        updated_config = self.service.update_bus_config(device_index=2, channel_index=1)
        self.service.reopen()

        self.assertEqual(updated_config.device_index, 2)
        self.assertEqual(updated_config.channel_index, 1)
        self.assertEqual(self.driver.config.device_index, 2)
        self.assertEqual(self.driver.config.channel_index, 1)
        self.assertEqual(self.driver.open_calls, 2)
        self.assertEqual(self.driver.close_calls, 2)
        self.assertEqual(self.service.periodic_voltage_values["00"], {})
        self.assertEqual(self.service.legacy_signal_state[0]["SOC"], "0")
        self.assertEqual(self.service.query_cursors[0], 0)
        self.assertEqual(self.service.query_cursors[1], 0)


if __name__ == "__main__":
    unittest.main()
