import os
import sys
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.dashboard_service import (
    ClusterDashboardView,
    ClusterHealth,
    FleetDashboardView,
)
from data_center.models import DataQuality
from presentation.cluster_dashboard_page import (
    ClusterDashboardPage,
    DashboardColumn,
)


def build_dashboard():
    generated_at = datetime(2026, 8, 21, 10, 24, 36)
    clusters = (
        ClusterDashboardView(
            cluster_index=0,
            address="00",
            communication_quality=DataQuality.GOOD,
            health=ClusterHealth.NORMAL,
            run_status=5,
            run_status_text="放电",
            soc=88.0,
            system_voltage=798.2,
            system_current=-12.4,
            voltage_difference=65.0,
            maximum_cell_voltage=3458.0,
            minimum_cell_voltage=3393.0,
            maximum_temperature=36.8,
            temperature_difference=3.8,
            alarm_count=0,
            alarm_names=(),
            last_update=generated_at,
        ),
        ClusterDashboardView(
            cluster_index=1,
            address="A0",
            communication_quality=DataQuality.GOOD,
            health=ClusterHealth.ALARM,
            run_status=6,
            run_status_text="充电",
            soc=84.0,
            system_voltage=802.4,
            system_current=10.5,
            voltage_difference=186.0,
            maximum_cell_voltage=3512.0,
            minimum_cell_voltage=3326.0,
            maximum_temperature=52.3,
            temperature_difference=6.2,
            alarm_count=1,
            alarm_names=("单体过压",),
            last_update=generated_at,
        ),
    )
    return FleetDashboardView(
        clusters=clusters,
        total_count=2,
        online_count=2,
        normal_count=1,
        warning_count=0,
        alarm_count=1,
        offline_count=0,
        generated_at=generated_at,
    )


class ClusterDashboardPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_page_renders_abnormal_cluster_first_with_all_voltage_fields(self):
        page = ClusterDashboardPage()

        page.update_dashboard(build_dashboard())

        self.assertEqual(page.cluster_table.rowCount(), 2)
        self.assertEqual(
            page.cluster_table.item(0, DashboardColumn.ADDRESS).text(),
            "簇1",
        )
        self.assertEqual(
            page.cluster_table.item(
                0,
                DashboardColumn.VOLTAGE_DIFFERENCE,
            ).text(),
            "186",
        )
        self.assertEqual(
            page.cluster_table.item(
                0,
                DashboardColumn.MAXIMUM_CELL_VOLTAGE,
            ).text(),
            "3512",
        )
        self.assertEqual(
            page.cluster_table.item(
                0,
                DashboardColumn.MINIMUM_CELL_VOLTAGE,
            ).text(),
            "3326",
        )
        self.assertIn("2 / 2", page._summary_labels["online"].text())

    def test_cluster_address_a1_is_displayed_as_cluster_two(self):
        page = ClusterDashboardPage()
        source = build_dashboard().clusters[1]
        dashboard = replace(
            build_dashboard(),
            clusters=(replace(source, cluster_index=2, address="A1"),),
            total_count=1,
            online_count=1,
        )

        page.update_dashboard(dashboard)

        self.assertEqual(
            page.cluster_table.item(0, DashboardColumn.ADDRESS).text(),
            "簇2",
        )

    def test_run_state_column_uses_bcu_run_status_not_alarm_health(self):
        page = ClusterDashboardPage()
        page.update_dashboard(build_dashboard())

        run_state_cell = page.cluster_table.cellWidget(
            0,
            DashboardColumn.RUN_STATE,
        )
        run_state_badge = run_state_cell.findChild(
            QLabel,
            "dashboardStatusBadge",
        )
        alarm_cell = page.cluster_table.cellWidget(
            0,
            DashboardColumn.ALARM,
        )
        alarm_badge = alarm_cell.findChild(
            QLabel,
            "dashboardStatusBadge",
        )

        self.assertEqual(run_state_badge.text(), "充电")
        self.assertEqual(run_state_badge.property("status"), "none")
        self.assertIn("状态码 6", run_state_badge.toolTip())
        self.assertEqual(alarm_badge.text(), "单体过压")
        self.assertEqual(alarm_badge.property("status"), "alarm")

    def test_summary_alarm_uses_actual_alarm_count_only(self):
        page = ClusterDashboardPage()
        dashboard = replace(
            build_dashboard(),
            warning_count=4,
            alarm_count=1,
        )

        page.update_dashboard(dashboard)

        self.assertEqual(page._summary_labels["alarm"].text(), "1")

    def test_primary_action_emits_selected_cluster(self):
        page = ClusterDashboardPage()
        page.update_dashboard(build_dashboard())
        activated = []
        page.cluster_activated.connect(
            lambda cluster_index, address: activated.append(
                (cluster_index, address)
            )
        )

        page.cluster_table.cellPressed.emit(1, DashboardColumn.ADDRESS)

        self.assertEqual(activated, [(0, "00")])

    def test_clicking_embedded_status_cell_activates_cluster(self):
        page = ClusterDashboardPage()
        page.resize(1400, 760)
        page.update_dashboard(build_dashboard())
        page.show()
        self.app.processEvents()
        activated = []
        page.cluster_activated.connect(
            lambda cluster_index, address: activated.append(
                (cluster_index, address)
            )
        )

        status_cell = page.cluster_table.cellWidget(
            0,
            DashboardColumn.COMMUNICATION,
        )
        self.assertTrue(
            status_cell.testAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
        )
        click_position = status_cell.mapTo(
            page.cluster_table.viewport(),
            status_cell.rect().center(),
        )
        QTest.mouseClick(
            page.cluster_table.viewport(),
            Qt.MouseButton.LeftButton,
            pos=click_position,
        )
        self.app.processEvents()

        self.assertEqual(activated, [(1, "A0")])
        page.close()

    def test_abnormal_first_places_offline_cluster_before_alarm(self):
        dashboard = build_dashboard()
        offline_cluster = replace(
            dashboard.clusters[0],
            cluster_index=2,
            address="A4",
            communication_quality=DataQuality.OFFLINE,
            health=ClusterHealth.OFFLINE,
            soc=None,
            last_update=None,
        )
        dashboard = replace(
            dashboard,
            clusters=dashboard.clusters + (offline_cluster,),
            total_count=3,
            offline_count=1,
        )
        page = ClusterDashboardPage()

        page.update_dashboard(dashboard)

        self.assertEqual(
            page.cluster_table.item(0, DashboardColumn.ADDRESS).text(),
            "簇5",
        )

        page.abnormal_first_toggle.setChecked(False)

        self.assertEqual(
            page.cluster_table.item(0, DashboardColumn.ADDRESS).text(),
            "未编制簇",
        )

    def test_fullscreen_button_emits_requested_state(self):
        page = ClusterDashboardPage()
        requested_states = []
        page.fullscreen_requested.connect(requested_states.append)

        page.fullscreen_button.click()

        self.assertEqual(requested_states, [True])
        self.assertEqual(page.fullscreen_button.text(), "退出全屏")

        page.set_fullscreen_state(False)

        self.assertFalse(page.fullscreen_button.isChecked())
        self.assertEqual(page.fullscreen_button.text(), "全屏")


if __name__ == "__main__":
    unittest.main()
