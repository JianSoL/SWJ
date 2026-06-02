from pathlib import Path

from PyQt6.QtWidgets import QApplication

from application.can_service import CanApplicationService
from application.config_loader import load_runtime_config
from application.session_logger import SessionLogManager
from domain.dbc_runtime import DbcRuntime
from domain.legacy_catalog import LegacySignalCatalog
from domain.models import BusConfig
from infrastructure.cxcanfd_driver import CxCanFdDriver, VCI_USBCAN2
from presentation.main_window import MainWindow


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _find_dbc_path():
    candidates = [
        PROJECT_DIR / "DCFDV1.3.dbc",
        BASE_DIR / "DCFDV1.3.dbc",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("DCFDV1.3.dbc not found")


def build_main_window():
    runtime_config = load_runtime_config(BASE_DIR / "conf.yaml")
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
    legacy_catalog = LegacySignalCatalog.from_excel(BASE_DIR / "SINGLE" / "BCU.xlsx")
    dbc_runtime = DbcRuntime(_find_dbc_path())
    log_manager = SessionLogManager(
        log_dir=BASE_DIR / "log",
        cluster_indices=range(0, runtime_config["BCU_NUM"] + 1),
        cluster_addresses=runtime_config["ADDRESLIST"][: runtime_config["BCU_NUM"] + 1],
        legacy_signal_names=legacy_catalog.logged_signal_names,
        voltage_count=int(runtime_config.get("CELL_NUM", 0)),
        temperature_count=int(runtime_config.get("CELL_Tem_NUM", 0)),
        balance_module_count=balance_module_count,
        balance_cells_per_module=int(
            runtime_config.get("BALANCE_CELLS_PER_MODULE", runtime_config.get("CELL_NUM", 0))
        ),
        enabled=bool(runtime_config.get("SAVE_LOG", 0)),
    )
    driver = CxCanFdDriver()
    service = CanApplicationService(
        runtime_config=runtime_config,
        bus_config=bus_config,
        driver=driver,
        legacy_catalog=legacy_catalog,
        dbc_runtime=dbc_runtime,
        log_manager=log_manager,
    )
    return MainWindow(service, runtime_config)


def main():
    app = QApplication([])
    window = build_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
