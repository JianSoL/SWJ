import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
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
    @patch("main.DeviceService")
    @patch("main.DashboardService")
    @patch("main.RuntimeDataCenter")
    @patch("main.CanApplicationService")
    @patch("main.CxCanFdDriver")
    @patch("main.SessionLogManager")
    @patch("main.DbcRuntime")
    @patch("main.LegacySignalCatalog")
    @patch("main.IndexCatalog")
    @patch("main.load_runtime_config")
    @patch("main.build_runtime_paths")
    def test_build_main_window_wires_new_stack(
        self,
        build_runtime_paths_mock,
        load_runtime_config_mock,
        index_catalog_class_mock,
        legacy_catalog_class_mock,
        dbc_runtime_class_mock,
        session_logger_class_mock,
        driver_class_mock,
        protocol_service_class_mock,
        data_center_class_mock,
        dashboard_service_class_mock,
        device_service_class_mock,
        main_window_class_mock,
    ):
        runtime_config = {
            "BCU_NUM": 2,
            "ADDRESLIST": ["A0", "A1"],
            "DEVICE_INDEX": 3,
            "CHANNEL_INDEX": 1,
        }
        load_runtime_config_mock.return_value = runtime_config
        runtime_paths = SimpleNamespace(
            config_path=Path("conf.yaml"),
            profile="Release",
            legacy_catalog_path=Path("SINGLE") / "BCU.yaml",
            index_catalog_path=Path("resources") / "index_catalog.json",
            dbc_path=Path("DCFDV1.3.dbc"),
            log_dir=Path("log"),
        )
        build_runtime_paths_mock.return_value = runtime_paths

        legacy_catalog = MagicMock()
        legacy_catalog.logged_signal_names = ["SOC"]
        legacy_catalog_class_mock.from_yaml.return_value = legacy_catalog

        index_catalog = MagicMock()
        index_catalog_class_mock.from_json.return_value = index_catalog

        dbc_runtime = MagicMock()
        dbc_runtime_class_mock.return_value = dbc_runtime

        log_manager = MagicMock()
        session_logger_class_mock.return_value = log_manager

        driver = MagicMock()
        driver_class_mock.return_value = driver

        protocol_service = MagicMock()
        protocol_service.cluster_index_to_address = {0: "A0", 1: "A1"}
        protocol_service_class_mock.return_value = protocol_service

        data_center = MagicMock()
        data_center_class_mock.return_value = data_center

        dashboard_service = MagicMock()
        dashboard_service_class_mock.return_value = dashboard_service

        device_service = MagicMock()
        device_service_class_mock.return_value = device_service

        window = MagicMock()
        main_window_class_mock.return_value = window

        progress_events = []

        result = main_module.build_main_window(
            progress_callback=lambda message, progress: progress_events.append(
                (message, progress)
            )
        )

        self.assertIs(result, window)
        self.assertIn(("\u51c6\u5907\u8fd0\u884c\u76ee\u5f55", 8), progress_events)
        self.assertIn(("\u6784\u5efa\u4e3b\u754c\u9762", 90), progress_events)
        build_runtime_paths_mock.assert_called_once_with()
        load_runtime_config_mock.assert_called_once_with(
            runtime_paths.config_path,
            profile=runtime_paths.profile,
        )
        legacy_catalog_class_mock.from_yaml.assert_called_once_with(
            runtime_paths.legacy_catalog_path
        )
        index_catalog_class_mock.from_json.assert_called_once_with(
            runtime_paths.index_catalog_path
        )
        dbc_runtime_class_mock.assert_called_once()
        session_logger_class_mock.assert_called_once()
        driver_class_mock.assert_called_once()
        protocol_service_class_mock.assert_called_once()
        main_window_class_mock.assert_called_once_with(
            device_service,
            runtime_config,
            runtime_paths=runtime_paths,
            product_info=main_module.PRODUCT_INFO,
            index_catalog=index_catalog,
            connect_on_init=True,
        )
        service_kwargs = protocol_service_class_mock.call_args.kwargs
        self.assertEqual(service_kwargs["bus_config"].device_index, 3)
        self.assertEqual(service_kwargs["bus_config"].channel_index, 1)
        data_center_class_mock.assert_called_once_with(
            protocol_service.cluster_index_to_address
        )
        dashboard_service_class_mock.assert_called_once_with(
            protocol_service,
            data_center,
            communication_timeout_s=2.0,
        )
        device_service_class_mock.assert_called_once_with(
            protocol_service,
            dashboard_service,
        )


if __name__ == "__main__":
    unittest.main()
