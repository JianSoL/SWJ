import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.session_logger import SessionLogManager
from domain.models import RawFrame


class SessionLogManagerTests(unittest.TestCase):
    def test_disabled_logger_skips_file_creation_and_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(
                temp_dir,
                cluster_indices=[0, 1],
                legacy_signal_names=["SOC"],
                enabled=False,
            )
            frame = RawFrame(
                frame_id=0x1204EF00,
                data=bytes([0xFF] * 8),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )

            logger.log_tx("query", 0, frame, 1)
            logger.log_rx("rx_can", frame, ["addr=00"])
            logger.log_dbc(
                "rx_canfd",
                frame,
                {
                    "frame_id": 0x1204EFA0,
                    "address": "00",
                    "message_name": "BCU1204EFA0",
                    "signals": [],
                },
            )
            logger.write_cluster_snapshot(0, {"SOC": "1"})
            logger.close()

            self.assertFalse(logger.tx_path.exists())
            self.assertFalse(logger.rx_path.exists())
            self.assertFalse(logger.dbc_path.exists())
            self.assertFalse(logger.cluster_path_by_index[0].exists())

    def test_cluster_zero_snapshot_uses_explicit_indices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(
                temp_dir,
                cluster_indices=[0, 1],
                legacy_signal_names=["SOC"],
            )

            logger.write_cluster_snapshot(0, {"SOC": "88"})
            logger.close()

            cluster_zero_path = logger.cluster_path_by_index[0]
            self.assertTrue(cluster_zero_path.exists())
            with open(cluster_zero_path, "r", newline="", encoding="utf-8") as cluster_file:
                rows = list(csv.reader(cluster_file))

        self.assertEqual(rows[0], ["timestamp", "SOC"])
        self.assertEqual(rows[1][1], "88")

    def test_logger_can_be_enabled_after_startup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(
                temp_dir,
                cluster_indices=[0, 1],
                legacy_signal_names=["SOC"],
                enabled=False,
            )
            frame = RawFrame(
                frame_id=0x1204EF00,
                data=bytes([0xAA] * 8),
                is_fd=False,
                extern_flag=True,
                remote_flag=False,
            )

            logger.set_enabled(True)
            logger.log_tx("query", 0, frame, 1)
            logger.write_cluster_snapshot(0, {"SOC": "7"})
            logger.close()

            self.assertTrue(logger.tx_path.exists())
            self.assertTrue(logger.cluster_path_by_index[0].exists())

    def test_periodic_snapshot_logs_create_separate_csv_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(
                temp_dir,
                cluster_indices=[0, 1],
                cluster_addresses=["00", "A0"],
                legacy_signal_names=["SOC"],
                voltage_count=3,
                temperature_count=2,
                balance_module_count=1,
                balance_cells_per_module=4,
            )

            logger.write_voltage_snapshot("00", [3301, 3302, None])
            logger.write_temperature_snapshot("00", [25.5, 26.0])
            logger.write_balance_snapshot("00", [1, 0, None, 1])
            logger.close()

            with open(
                logger.voltage_path_by_address["00"],
                "r",
                newline="",
                encoding="utf-8",
            ) as voltage_file:
                voltage_rows = list(csv.reader(voltage_file))
            with open(
                logger.temperature_path_by_address["00"],
                "r",
                newline="",
                encoding="utf-8",
            ) as temperature_file:
                temperature_rows = list(csv.reader(temperature_file))
            with open(
                logger.balance_path_by_address["00"],
                "r",
                newline="",
                encoding="utf-8",
            ) as balance_file:
                balance_rows = list(csv.reader(balance_file))

        self.assertEqual(voltage_rows[0], ["timestamp", "CELL_001", "CELL_002", "CELL_003"])
        self.assertEqual(voltage_rows[1][1:], ["3301", "3302", ""])
        self.assertEqual(temperature_rows[0], ["timestamp", "TEMP_001", "TEMP_002"])
        self.assertEqual(temperature_rows[1][1:], ["25.5", "26"])
        self.assertEqual(balance_rows[0], ["timestamp", "M1-001", "M1-002", "M1-003", "M1-004"])
        self.assertEqual(balance_rows[1][1:], ["1", "0", "", "1"])

    def test_log_dbc_writes_separate_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(temp_dir, cluster_count=2, legacy_signal_names=["SOC"])
            frame = RawFrame(
                frame_id=0x1204EF00,
                data=bytes([0xFF] * 64),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
            decoded = {
                "frame_id": 0x1204EFA0,
                "address": "A0",
                "message_name": "BCU1204EFA0",
                "signals": [
                    {"signal_name": "ALARM_STATE_ID_001", "value": 15, "unit": "NAN"},
                    {"signal_name": "ALARM_STATE_ID_002", "value": 0, "unit": "NAN"},
                ],
            }

            logger.log_dbc("rx_canfd", frame, decoded)
            logger.close()

            with open(logger.dbc_path, "r", newline="", encoding="utf-8") as dbc_file:
                rows = list(csv.reader(dbc_file))

        self.assertEqual(
            rows[0],
            [
                "timestamp",
                "frame_kind",
                "raw_can_id",
                "dbc_can_id",
                "address",
                "message_name",
                "signal_count",
                "signals_json",
            ],
        )
        self.assertEqual(rows[1][1], "rx_canfd")
        self.assertEqual(rows[1][2], "0x1204EF00")
        self.assertEqual(rows[1][3], "0x1204EFA0")
        self.assertEqual(rows[1][4], "A0")
        self.assertEqual(rows[1][5], "BCU1204EFA0")
        self.assertEqual(rows[1][6], "2")
        self.assertEqual(
            json.loads(rows[1][7]),
            [
                {"signal_name": "ALARM_STATE_ID_001", "value": 15, "unit": "NAN"},
                {"signal_name": "ALARM_STATE_ID_002", "value": 0, "unit": "NAN"},
            ],
        )

    def test_all_log_files_roll_over_after_max_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = SessionLogManager(
                temp_dir,
                cluster_count=1,
                legacy_signal_names=["SOC"],
                max_rows_per_file=2,
            )
            frame = RawFrame(
                frame_id=0x1204EF00,
                data=bytes([0xFF] * 64),
                is_fd=True,
                extern_flag=True,
                remote_flag=False,
                brs=True,
            )
            decoded = {
                "frame_id": 0x1204EFA0,
                "address": "A0",
                "message_name": "BCU1204EFA0",
                "signals": [
                    {"signal_name": "ALARM_STATE_ID_001", "value": 15, "unit": "NAN"},
                ],
            }

            for index in range(3):
                logger.log_tx("query", 1, frame, index)
                logger.log_rx("rx_canfd", frame, ["message=BCU1204EFA0"])
                logger.log_dbc("rx_canfd", frame, decoded)
                logger.write_cluster_snapshot(1, {"SOC": str(index)})
            logger.close()

            expected_paths = [
                logger.tx_path,
                logger.tx_path.with_name(f"{logger.tx_path.stem}_part2{logger.tx_path.suffix}"),
                logger.rx_path,
                logger.rx_path.with_name(f"{logger.rx_path.stem}_part2{logger.rx_path.suffix}"),
                logger.dbc_path,
                logger.dbc_path.with_name(f"{logger.dbc_path.stem}_part2{logger.dbc_path.suffix}"),
                logger.cluster_paths[0],
                logger.cluster_paths[0].with_name(
                    f"{logger.cluster_paths[0].stem}_part2{logger.cluster_paths[0].suffix}"
                ),
            ]

            for path in expected_paths:
                self.assertTrue(path.exists(), str(path))

            with open(logger.tx_path, "r", newline="", encoding="utf-8") as tx_file:
                self.assertEqual(len(list(csv.reader(tx_file))), 3)
            with open(
                logger.tx_path.with_name(f"{logger.tx_path.stem}_part2{logger.tx_path.suffix}"),
                "r",
                newline="",
                encoding="utf-8",
            ) as tx_part2_file:
                self.assertEqual(len(list(csv.reader(tx_part2_file))), 2)


if __name__ == "__main__":
    unittest.main()
