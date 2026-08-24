import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.power_diagnostics import (
    POWER_DIAGNOSTIC_SIGNAL_IDS,
    PowerDiagnosticAnalyzer,
)


class PowerDiagnosticAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = PowerDiagnosticAnalyzer()
        self.values = {data_id: 0 for data_id in POWER_DIAGNOSTIC_SIGNAL_IDS}
        self.values.update(
            {
                12: 2,
                14: 0,
                23: 4,
                37: 0xFFFF,
                91: 5000,
                92: 4900,
                791: 1,
                0x83002: 0x0100,
                0x90479: 100,
                0x9047A: 90,
                0x9047C: 10,
                0x9047D: 500,
            }
        )

    def _condition(self, report, name):
        return next(item for item in report["conditions"] if item["name"] == name)

    def test_insulation_not_finished_blocks_power_on(self):
        self.values[791] = 0

        report = self.analyzer.analyze(self.values)

        condition = self._condition(report, "绝缘检测完成")
        self.assertEqual(condition["status"], "blocked")
        self.assertEqual(report["summary_status"], "blocked")

    def test_precharge_failure_is_reported_as_blocking(self):
        self.values[12] = 3
        self.values[279] = 1

        report = self.analyzer.analyze(self.values)

        condition = self._condition(report, "预充完成条件")
        self.assertEqual(condition["status"], "blocked")
        self.assertIn("预充", report["summary_title"])

    def test_vms_shutdown_request_builds_normal_transition_event(self):
        self.values[0x83002] = 0x0200

        event = self.analyzer.build_transition_event(4, 10, self.values)

        self.assertEqual(event["type"], "正常请求下电")
        self.assertEqual(event["severity"], "normal")

    def test_severe_alarm_builds_abnormal_transition_event(self):
        self.values[0x83002] = 0
        self.values[276] = 0x0100

        event = self.analyzer.build_transition_event(4, 10, self.values)

        self.assertEqual(event["type"], "异常下电")
        self.assertEqual(event["severity"], "danger")
        self.assertIn("严重告警", event["cause"])


if __name__ == "__main__":
    unittest.main()
