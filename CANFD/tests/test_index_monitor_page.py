import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from presentation.index_monitor_page import IndexMonitorPage


class IndexMonitorPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_60s_power_and_current_values_use_protocol_scaling(self):
        page = IndexMonitorPage()

        page.update_snapshot(
            {
                "continuous_discharge_power": 21000,
                "continuous_charge_power": 19000,
                "continuous_discharge_current": 1200,
                "continuous_charge_current": 900,
            }
        )

        self.assertEqual(
            page.metric_labels["continuous_discharge_power"].text(),
            "60S最大放电功率",
        )
        self.assertEqual(
            page.metric_labels["continuous_charge_current"].text(),
            "60S最大充电电流",
        )
        self.assertEqual(
            page.value_fields["continuous_discharge_power"].text(),
            "210000 W",
        )
        self.assertEqual(
            page.value_fields["continuous_charge_power"].text(),
            "190000 W",
        )
        self.assertEqual(
            page.value_fields["continuous_discharge_current"].text(),
            "120 A",
        )
        self.assertEqual(
            page.value_fields["continuous_charge_current"].text(),
            "90 A",
        )
        page.close()

    def test_single_energy_values_use_0_1_kwh_scaling(self):
        page = IndexMonitorPage()

        page.update_snapshot(
            {
                "single_charge_kwh": 586,
                "single_discharge_kwh": 12,
                "remaining_charge_kwh": 16120,
                "total_charge_kwh": 5871,
            }
        )

        self.assertEqual(
            page.value_fields["single_charge_kwh"].text(),
            "58.6 kWh",
        )
        self.assertEqual(
            page.value_fields["single_discharge_kwh"].text(),
            "1.2 kWh",
        )
        self.assertEqual(
            page.value_fields["remaining_charge_kwh"].text(),
            "161.2 kWh",
        )
        self.assertEqual(
            page.value_fields["total_charge_kwh"].text(),
            "58.71 kWh",
        )
        page.close()

    def test_layout_reflows_and_scrolls_at_lower_resolutions(self):
        page = IndexMonitorPage()
        page.show()

        page.resize(1900, 900)
        self.app.processEvents()
        self.assertEqual(page.responsive_layout_mode, "wide")
        temperature_position = page.monitor_grid.getItemPosition(
            page.monitor_grid.indexOf(page.temperature_group)
        )
        self.assertEqual(temperature_position[:2], (1, 2))

        page.resize(1300, 720)
        self.app.processEvents()
        self.assertEqual(page.responsive_layout_mode, "medium")
        statistics_position = page.monitor_grid.getItemPosition(
            page.monitor_grid.indexOf(page.statistics_group)
        )
        self.assertEqual(statistics_position[:2], (2, 0))

        page.resize(900, 520)
        self.app.processEvents()
        self.assertEqual(page.responsive_layout_mode, "narrow")
        temperature_position = page.monitor_grid.getItemPosition(
            page.monitor_grid.indexOf(page.temperature_group)
        )
        self.assertEqual(temperature_position[:2], (5, 0))
        self.assertGreater(
            page.scroll_area.verticalScrollBar().maximum(),
            0,
        )

        input_columns = {
            page.input_state_layout.getItemPosition(
                page.input_state_layout.indexOf(dot)
            )[1]
            for dot in page.input_dots
        }
        output_columns = {
            page.output_state_layout.getItemPosition(
                page.output_state_layout.indexOf(dot)
            )[1]
            for dot in page.output_dots
        }
        self.assertLessEqual(max(input_columns), 3)
        self.assertLessEqual(max(output_columns), 3)
        page.close()


if __name__ == "__main__":
    unittest.main()
