import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import main as main_module


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    @patch("main.MainWindow")
    @patch("main.CanApplicationService")
    @patch("main.CxCanFdDriver")
    @patch("main.SessionLogManager")
    @patch("main.DbcRuntime")
    @patch("main.LegacySignalCatalog")
    @patch("main.load_runtime_config")
    def test_build_main_window_wires_new_stack(
        self,
        load_runtime_config_mock,
        legacy_catalog_class_mock,
        dbc_runtime_class_mock,
        session_logger_class_mock,
        driver_class_mock,
        service_class_mock,
        main_window_class_mock,
    ):
        runtime_config = {
            "BCU_NUM": 2,
            "ADDRESLIST": ["00", "A0", "A1"],
            "DEVICE_INDEX": 3,
            "CHANNEL_INDEX": 1,
        }
        load_runtime_config_mock.return_value = runtime_config

        legacy_catalog = MagicMock()
        legacy_catalog.logged_signal_names = ["SOC"]
        legacy_catalog_class_mock.from_excel.return_value = legacy_catalog

        dbc_runtime = MagicMock()
        dbc_runtime_class_mock.return_value = dbc_runtime

        log_manager = MagicMock()
        session_logger_class_mock.return_value = log_manager

        driver = MagicMock()
        driver_class_mock.return_value = driver

        service = MagicMock()
        service_class_mock.return_value = service

        window = MagicMock()
        main_window_class_mock.return_value = window

        result = main_module.build_main_window()

        self.assertIs(result, window)
        load_runtime_config_mock.assert_called_once()
        legacy_catalog_class_mock.from_excel.assert_called_once()
        dbc_runtime_class_mock.assert_called_once()
        session_logger_class_mock.assert_called_once()
        driver_class_mock.assert_called_once()
        service_class_mock.assert_called_once()
        main_window_class_mock.assert_called_once_with(service, runtime_config)
        service_kwargs = service_class_mock.call_args.kwargs
        self.assertEqual(service_kwargs["bus_config"].device_index, 3)
        self.assertEqual(service_kwargs["bus_config"].channel_index, 1)


if __name__ == "__main__":
    unittest.main()
