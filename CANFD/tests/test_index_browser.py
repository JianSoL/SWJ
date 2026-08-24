import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from domain.index_catalog import IndexCatalog
from presentation.index_control_page import IndexControlPage


class IndexBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])
        cls.catalog = IndexCatalog.from_json(
            PROJECT_DIR / "resources" / "index_catalog.json"
        )
        cls.config = {
            "BCU_NUM": 2,
            "LECU_NUM": 4,
            "CELL_NUM": 104,
            "Alarm_name_key": {"001": "单体电压过高"},
        }

    def setUp(self):
        self.page = IndexControlPage(self.catalog, self.config)
        self.page.show()
        self.app.processEvents()

    def tearDown(self):
        self.page.close()
        self.app.processEvents()

    def test_direct_index_input_updates_name_and_detail(self):
        self.page.index_edits[0].setText("0x315")
        self.page.index_edits[0].setFocus()
        self.app.processEvents()

        self.assertIn("霍尔", self.page.index_name_labels[0].toolTip())
        self.assertEqual(self.page.index_hex_labels[0].text(), "0x315")
        self.assertIn("VAR_HALL_CURR", self.page.index_detail_meta.text())

    def test_browser_search_selects_and_fills_active_row(self):
        self.page.active_index_row = 2
        dialog = self.page.create_index_browser_dialog()
        selected = []
        dialog.indexSelected.connect(selected.append)

        dialog.search_edit.setText("霍尔电流")
        self.app.processEvents()
        self.assertGreater(dialog.proxy_model.rowCount(), 0)

        first = dialog.proxy_model.index(0, 0)
        dialog.table.selectionModel().select(
            first,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.app.processEvents()
        dialog._accept_current()

        self.assertEqual(selected, [0x315])
        self.assertEqual(self.page.index_edits[2].text(), str(0x315))
        self.assertEqual(self.page.get_index_resolution(2).symbol, "VAR_HALL_CURR")
        dialog.close()

    def test_browser_search_finds_decimal_lecu_count_index(self):
        dialog = self.page.create_index_browser_dialog()

        dialog.search_edit.setText("590849")
        self.app.processEvents()

        self.assertEqual(dialog.proxy_model.rowCount(), 1)
        proxy_index = dialog.proxy_model.index(0, 0)
        source_index = dialog.proxy_model.mapToSource(proxy_index)
        entry = dialog.source_model.entry_at(source_index.row())
        self.assertEqual(entry.data_id, 590849)
        self.assertEqual(entry.symbol, "PAR_SYS_LECU_NUM")
        dialog.close()

if __name__ == "__main__":
    unittest.main()
