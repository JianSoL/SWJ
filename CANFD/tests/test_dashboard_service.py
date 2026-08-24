import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.dashboard_service import ClusterHealth, DashboardService
from data_center.models import DataQuality
from data_center.runtime_cache import RuntimeDataCenter
from domain.models import LegacySignalUpdate, PollResult
from protocol.bms_signal_ids import DASHBOARD_POLL_SEQUENCE


class FakeProtocolService:
    def __init__(self):
        self.cluster_indices = [0, 1]
        self.cluster_index_to_address = {0: "00", 1: "A0"}
        self.cluster_address_to_index = {"00": 0, "A0": 1}
        self.query_calls = []
        self.snapshots = {
            0: {
                "run_status": 5,
                "soc": 880,
                "system_voltage": 7982,
                "system_current": -124,
                "diff_voltage": 86,
                "max_cell_voltage": 3458,
                "min_cell_voltage": 3372,
                "max_cell_temp": 368,
                "diff_temp": 56,
            },
            1: {
                "run_status": 6,
                "soc": 720,
                "system_voltage": 7654,
                "system_current": -148,
                "diff_voltage": 76,
                "max_cell_voltage": 3461,
                "min_cell_voltage": 3385,
                "max_cell_temp": 523,
                "diff_temp": 46,
            },
        }
        self.activities = {
            0: {"is_open": True, "last_rx_age_s": 0.2},
            1: {"is_open": True, "last_rx_age_s": 0.3},
        }
        self.alarms = {"00": [("单体过压", 2)], "A0": []}

    def send_signal_query(self, cluster_index, signal_id):
        self.query_calls.append((cluster_index, signal_id))
        return 1

    def get_index_monitor_snapshot(self, cluster_index):
        return dict(self.snapshots[cluster_index])

    def get_bus_activity_snapshot(self, cluster_index):
        return dict(self.activities[cluster_index])

    def get_periodic_alarm_state_values(self, address):
        return list(self.alarms[address])


class DashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.protocol_service = FakeProtocolService()
        self.data_center = RuntimeDataCenter(
            self.protocol_service.cluster_index_to_address
        )
        self.service = DashboardService(
            self.protocol_service,
            self.data_center,
            communication_timeout_s=2.0,
        )

    def test_ingest_builds_scaled_all_cluster_dashboard(self):
        poll_result = PollResult(
            legacy_updates=[
                LegacySignalUpdate(
                    cluster_index=0,
                    signal_id=16,
                    signal_name="SOC",
                    value="880",
                    unit="0.1%",
                    table_index=-1,
                    row_index=-1,
                    source_kind="can",
                ),
                LegacySignalUpdate(
                    cluster_index=1,
                    signal_id=16,
                    signal_name="SOC",
                    value="720",
                    unit="0.1%",
                    table_index=-1,
                    row_index=-1,
                    source_kind="can",
                ),
            ]
        )

        self.service.ingest_poll_result(poll_result)
        dashboard = self.service.get_dashboard()

        self.assertEqual(dashboard.total_count, 2)
        self.assertEqual(dashboard.online_count, 2)
        self.assertEqual(dashboard.alarm_count, 1)
        self.assertEqual(dashboard.clusters[0].health, ClusterHealth.ALARM)
        self.assertEqual(dashboard.clusters[0].soc, 88.0)
        self.assertEqual(dashboard.clusters[0].system_voltage, 798.2)
        self.assertEqual(dashboard.clusters[0].system_current, -12.4)
        self.assertEqual(dashboard.clusters[0].maximum_cell_voltage, 3458.0)
        self.assertEqual(dashboard.clusters[0].minimum_cell_voltage, 3372.0)
        self.assertEqual(dashboard.clusters[1].maximum_temperature, 52.3)
        self.assertEqual(dashboard.clusters[1].health, ClusterHealth.NORMAL)
        self.assertEqual(dashboard.warning_count, 0)

    def test_dashboard_query_cycles_named_protocol_sequence_across_clusters(self):
        call_count = len(DASHBOARD_POLL_SEQUENCE) + 1

        for _ in range(call_count):
            self.service.send_next_query()

        self.assertEqual(
            self.protocol_service.query_calls[0],
            (0, int(DASHBOARD_POLL_SEQUENCE[0])),
        )
        self.assertEqual(
            self.protocol_service.query_calls[-1],
            (1, int(DASHBOARD_POLL_SEQUENCE[0])),
        )
        self.assertIn(0x148, tuple(map(int, DASHBOARD_POLL_SEQUENCE)))
        self.assertIn(0x14B, tuple(map(int, DASHBOARD_POLL_SEQUENCE)))

    def test_stale_cluster_is_marked_offline(self):
        self.protocol_service.activities[1]["last_rx_age_s"] = 3.0
        self.service.refresh_all_clusters()

        dashboard = self.service.get_dashboard()

        self.assertEqual(dashboard.clusters[1].communication_quality, DataQuality.STALE)
        self.assertEqual(dashboard.clusters[1].health, ClusterHealth.OFFLINE)

    def test_severe_measurement_does_not_create_an_alarm_without_alarm_frame(self):
        self.protocol_service.snapshots[1]["diff_voltage"] = 151
        self.service.refresh_all_clusters()

        dashboard = self.service.get_dashboard()

        self.assertEqual(dashboard.clusters[1].health, ClusterHealth.NORMAL)
        self.assertEqual(dashboard.clusters[1].alarm_count, 0)

    def test_dashboard_alarm_count_sums_actual_lower_controller_alarms(self):
        self.protocol_service.alarms["00"] = [
            ("ALARM_A", 2),
            ("ALARM_B", 1),
        ]
        self.service.refresh_all_clusters()

        dashboard = self.service.get_dashboard()

        self.assertEqual(dashboard.alarm_count, 2)


if __name__ == "__main__":
    unittest.main()
