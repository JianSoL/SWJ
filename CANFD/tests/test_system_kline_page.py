import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.trend_store import TrendDataStore
from presentation.system_kline_page import SystemKLinePage


class SystemKLinePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_page_switches_period_and_clears_current_cluster(self):
        store = TrendDataStore()
        store.add_sample(1, "voltage", 650.1, 100.0)
        store.add_sample(1, "voltage", 651.2, 101.0)
        page = SystemKLinePage(store)
        page.set_cluster_context(1, "A0")

        page.period_selector.setCurrentIndex(page.period_selector.findData(1))
        page.refresh_active_chart(force=True)

        self.assertEqual(page.cluster_label.text(), "当前簇: 簇1 / 地址 A0")
        self.assertEqual(page.chart_tabs.count(), 3)
        self.assertEqual(page.chart_tabs.tabText(1), "霍尔电流 K线")
        self.assertEqual(page.chart_tabs.tabText(2), "分流器电流 K线")
        self.assertEqual(page.panels["voltage"].summary["count"], 2)
        self.assertIn("已采样 2 次", page.status_label.text())

        page.clear_current_cluster()
        self.assertEqual(store.sample_count(1, "voltage"), 0)
        self.assertEqual(page.panels["voltage"].summary["count"], 0)
        page.close()

    def test_pause_stops_redraw_without_stopping_collection(self):
        store = TrendDataStore()
        page = SystemKLinePage(store)
        page.set_cluster_context(1, "A0")
        page.pause_checkbox.setChecked(True)
        store.add_sample(1, "hall_current", -10.0, 100.0)
        page.notify_sample_added(1, "hall_current")

        self.assertFalse(page.redraw_timer.isActive())
        self.assertIn("后台仍在采集", page.status_label.text())
        self.assertEqual(store.sample_count(1, "hall_current"), 1)
        page.close()


if __name__ == "__main__":
    unittest.main()
