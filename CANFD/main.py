from PyQt6.QtWidgets import QApplication, QMessageBox

from application.can_service import CanApplicationService
from application.config_loader import (
    load_runtime_config,
    resolve_active_cluster_addresses,
)
from application.dashboard_service import DashboardService
from application.device_service import DeviceService
from application.runtime import build_runtime_paths
from application.session_logger import SessionLogManager
from data_center.runtime_cache import RuntimeDataCenter
from domain.dbc_runtime import DbcRuntime
from domain.index_catalog import IndexCatalog
from domain.legacy_catalog import LegacySignalCatalog
from domain.models import BusConfig
from infrastructure.cxcanfd_driver import CxCanFdDriver, VCI_USBCAN2
from presentation.main_window import MainWindow
from presentation.startup_splash import StartupSplash
from product import PRODUCT_INFO


def _report_startup(progress_callback, message, progress):
    if callable(progress_callback):
        progress_callback(message, progress)


def build_main_window(
    runtime_paths=None,
    progress_callback=None,
    connect_on_init=True,
):
    _report_startup(progress_callback, "\u51c6\u5907\u8fd0\u884c\u76ee\u5f55", 8)
    runtime_paths = runtime_paths or build_runtime_paths()
    _report_startup(progress_callback, "\u52a0\u8f7d\u8fd0\u884c\u914d\u7f6e", 18)
    runtime_config = load_runtime_config(
        runtime_paths.config_path,
        profile=runtime_paths.profile,
    )
    balance_module_count = int(
        runtime_config.get(
            "BALANCE_MODULE_COUNT",
            runtime_config.get("LECU_NUM", 4),
        )
    )
    bus_config = BusConfig(
        can_type=VCI_USBCAN2,
        device_index=int(runtime_config.get("DEVICE_INDEX", 0)),
        channel_index=int(runtime_config.get("CHANNEL_INDEX", 0)),
        arbitration_baud=500000,
        data_baud=2000000,
        fd_standard=0,
        mode=0,
        receive_timeout_ms=0,
    )
    _report_startup(progress_callback, "\u8bfb\u53d6\u4fe1\u53f7\u8868", 34)
    legacy_catalog = LegacySignalCatalog.from_yaml(runtime_paths.legacy_catalog_path)
    _report_startup(progress_callback, "\u8bfb\u53d6\u7d22\u5f15\u76ee\u5f55", 48)
    index_catalog = IndexCatalog.from_json(runtime_paths.index_catalog_path)
    _report_startup(progress_callback, "\u521d\u59cb\u5316 DBC \u6570\u636e", 60)
    dbc_runtime = DbcRuntime(runtime_paths.dbc_path)
    _report_startup(progress_callback, "\u51c6\u5907\u65e5\u5fd7\u7cfb\u7edf", 70)
    logging_enabled = bool(runtime_config.get("SAVE_LOG", 0))
    active_cluster_addresses = resolve_active_cluster_addresses(runtime_config)
    log_manager = SessionLogManager(
        log_dir=runtime_paths.log_dir,
        cluster_indices=range(len(active_cluster_addresses)),
        cluster_addresses=active_cluster_addresses,
        legacy_signal_names=legacy_catalog.logged_signal_names,
        voltage_count=int(runtime_config.get("CELL_NUM", 0)),
        temperature_count=int(runtime_config.get("CELL_Tem_NUM", 0)),
        balance_module_count=balance_module_count,
        balance_cells_per_module=int(
            runtime_config.get("BALANCE_CELLS_PER_MODULE", runtime_config.get("CELL_NUM", 0))
        ),
        balance_temperature_per_module=int(
            runtime_config.get("BALANCE_TEMP_PER_MODULE", 8)
        ),
        enabled=False,
        flush_interval_ms=int(runtime_config.get("LOG_FLUSH_INTERVAL_MS", 250)),
        flush_row_count=int(runtime_config.get("LOG_FLUSH_ROW_COUNT", 128)),
    )
    _report_startup(progress_callback, "\u5efa\u7acb CANFD \u670d\u52a1", 80)
    driver = CxCanFdDriver()
    protocol_service = CanApplicationService(
        runtime_config=runtime_config,
        bus_config=bus_config,
        driver=driver,
        legacy_catalog=legacy_catalog,
        dbc_runtime=dbc_runtime,
        log_manager=log_manager,
    )
    data_center = RuntimeDataCenter(protocol_service.cluster_index_to_address)
    dashboard_service = DashboardService(
        protocol_service,
        data_center,
        communication_timeout_s=(
            int(runtime_config.get("COMMUNICATION_ACTIVE_TIMEOUT_MS", 2000))
            / 1000.0
        ),
    )
    service = DeviceService(protocol_service, dashboard_service)
    service.set_snapshot_logging_enabled(logging_enabled)
    _report_startup(progress_callback, "\u6784\u5efa\u4e3b\u754c\u9762", 90)
    return MainWindow(
        service,
        runtime_config,
        runtime_paths=runtime_paths,
        product_info=PRODUCT_INFO,
        index_catalog=index_catalog,
        connect_on_init=connect_on_init,
    )


def main():
    app = QApplication([])
    app.setApplicationName(PRODUCT_INFO.display_name)
    app.setApplicationVersion(PRODUCT_INFO.version)
    app.setOrganizationName(PRODUCT_INFO.organization)

    splash = StartupSplash(PRODUCT_INFO)
    splash.show()
    splash.set_status("\u542f\u52a8\u5e94\u7528\u6846\u67b6", 4)
    app.processEvents()

    def update_splash(message, progress):
        splash.set_status(message, progress)
        app.processEvents()

    try:
        window = build_main_window(
            progress_callback=update_splash,
            connect_on_init=False,
        )
    except Exception as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "\u4e0a\u4f4d\u673a\u542f\u52a8\u5931\u8d25",
            str(exc),
        )
        raise

    update_splash("\u542f\u52a8\u5b8c\u6210\uff0c\u6253\u5f00\u4e3b\u754c\u9762", 98)
    window.show()
    splash.finish(window)
    window.schedule_startup_bus_open()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
