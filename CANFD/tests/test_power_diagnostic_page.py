import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from presentation.power_diagnostic_page import PowerDiagnosticPage


class PowerDiagnosticPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_page_renders_report_and_event(self):
        page = PowerDiagnosticPage()
        page.set_cluster_context(1, "A0")
        page.update_report(
            {
                "summary_status": "blocked",
                "summary_title": "上电受阻：绝缘检测完成",
                "primary_reason": "绝缘检测未完成",
                "run_status_name": "自检",
                "blocked_count": 1,
                "warning_count": 0,
                "shutdown_status": "abnormal",
                "generated_at": "2026-07-08 12:00:00",
                "firmware_source": "BCU615/06.bcu_app_02v01",
                "conditions": [
                    {
                        "category": "自检",
                        "name": "绝缘检测完成",
                        "value": "未完成",
                        "status": "blocked",
                        "status_text": "阻断",
                        "evidence": "VAR_SYS_INSU_FINISH_FLAG == 0",
                        "advice": "检查绝缘模块",
                        "source": "Task_Batt_Manage.c",
                    }
                ],
            },
            [
                {
                    "time": "2026-07-08 12:00:01",
                    "transition": "高压待机 -> 切断",
                    "type": "异常下电",
                    "cause": "绝缘故障",
                    "evidence": "绝缘检测未完成",
                }
            ],
        )

        self.assertIn("上电受阻", page.summary_banner.text())
        self.assertEqual(page.conditions_table.rowCount(), 1)
        self.assertEqual(page.events_table.rowCount(), 1)
        self.assertIn("簇1", page.cluster_label.text())
        page.close()


if __name__ == "__main__":
    unittest.main()
