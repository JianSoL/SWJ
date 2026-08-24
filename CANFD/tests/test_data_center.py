import sys
import unittest
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from data_center.models import ActiveAlarm, DataQuality
from data_center.runtime_cache import RuntimeDataCenter


class RuntimeDataCenterTests(unittest.TestCase):
    def test_runtime_cache_preserves_hierarchy_quality_and_statistics(self):
        data_center = RuntimeDataCenter({0: "00", 1: "A0"})
        timestamp = datetime(2026, 8, 21, 10, 24, 30)

        data_center.update_cluster_values(
            1,
            {"soc": 80.0, "system_voltage": 790.0},
            units={"soc": "%", "system_voltage": "V"},
            quality=DataQuality.GOOD,
            timestamp=timestamp,
        )
        data_center.update_cluster_values(
            1,
            {"soc": 84.0},
            units={"soc": "%"},
            quality=DataQuality.GOOD,
            timestamp=timestamp,
        )
        data_center.update_cluster_communication(1, DataQuality.GOOD, timestamp)
        data_center.replace_cluster_alarms(
            1,
            [ActiveAlarm(code="007", name="单体过压", level=2)],
        )

        system = data_center.snapshot()
        cluster = system.stacks["stack_1"].clusters[1]

        self.assertEqual(cluster.address, "A0")
        self.assertEqual(cluster.communication_quality, DataQuality.GOOD)
        self.assertEqual(cluster.latest_values["soc"].value, 84.0)
        self.assertEqual(cluster.latest_values["soc"].unit, "%")
        self.assertEqual(cluster.latest_values["soc"].statistics.minimum, 80.0)
        self.assertEqual(cluster.latest_values["soc"].statistics.maximum, 84.0)
        self.assertEqual(cluster.latest_values["soc"].statistics.average, 82.0)
        self.assertEqual(cluster.active_alarms[0].name, "单体过压")

    def test_reconfigure_reuses_matching_cluster_and_drops_removed_cluster(self):
        data_center = RuntimeDataCenter({0: "00", 1: "A0"})
        data_center.update_cluster_values(1, {"soc": 75.0})

        data_center.configure_clusters({0: "00", 1: "A0", 2: "A1"})

        clusters = list(data_center.list_clusters())
        self.assertEqual([cluster.address for cluster in clusters], ["00", "A0", "A1"])
        self.assertEqual(clusters[1].latest_values["soc"].value, 75.0)


if __name__ == "__main__":
    unittest.main()
