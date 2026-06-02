import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from UI.module_value_page import ModuleValuePage


class ModuleValuePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_extrema_highlight_is_calculated_per_group(self):
        page = ModuleValuePage(
            title="test",
            group_title="group",
            group_count=2,
            values_per_group=3,
            items_per_row=3,
            highlight_mode="extrema",
        )

        page.setValues([100, 200, 300, 1000, 900, 800])

        self.assertIn("#fff59d", page.lineEdits[0].styleSheet())
        self.assertEqual(page.lineEdits[1].styleSheet(), "")
        self.assertIn("#ef5350", page.lineEdits[2].styleSheet())
        self.assertIn("#ef5350", page.lineEdits[3].styleSheet())
        self.assertEqual(page.lineEdits[4].styleSheet(), "")
        self.assertIn("#fff59d", page.lineEdits[5].styleSheet())

        page.close()

    def test_extrema_highlight_ignores_empty_values_inside_group(self):
        page = ModuleValuePage(
            title="test",
            group_title="group",
            group_count=2,
            values_per_group=3,
            items_per_row=3,
            highlight_mode="extrema",
        )

        page.setValues([None, 200, 300, "", 900, 800])

        self.assertEqual(page.lineEdits[0].styleSheet(), "")
        self.assertIn("#fff59d", page.lineEdits[1].styleSheet())
        self.assertIn("#ef5350", page.lineEdits[2].styleSheet())
        self.assertEqual(page.lineEdits[3].styleSheet(), "")
        self.assertIn("#ef5350", page.lineEdits[4].styleSheet())
        self.assertIn("#fff59d", page.lineEdits[5].styleSheet())

        page.close()

    def test_page_does_not_expand_beyond_configured_group_capacity(self):
        page = ModuleValuePage(
            title="test",
            group_title="group",
            group_count=1,
            values_per_group=2,
            items_per_row=2,
            highlight_mode="extrema",
        )

        page.setValues([100, 200, 300, 400])

        self.assertEqual(len(page.groups), 1)
        self.assertEqual(len(page.lineEdits), 2)
        self.assertEqual(page.lineEdits[0].text(), "100")
        self.assertEqual(page.lineEdits[1].text(), "200")

        page.close()


if __name__ == "__main__":
    unittest.main()
