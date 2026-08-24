import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from application.can_service import CanApplicationService
from application.config_loader import (
    load_runtime_config,
    resolve_active_cluster_addresses,
)
from application.runtime import build_runtime_paths
from application.session_logger import SessionLogManager
from domain.dbc_runtime import DbcRuntime
from domain.legacy_catalog import LegacySignalCatalog
from domain.models import BusConfig
from infrastructure.cxcanfd_driver import CxCanFdDriver, VCI_USBCAN2


def build_service():
    runtime_paths = build_runtime_paths()
    runtime_config = load_runtime_config(
        runtime_paths.config_path,
        profile=runtime_paths.profile,
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
    legacy_catalog = LegacySignalCatalog.from_yaml(runtime_paths.legacy_catalog_path)
    dbc_runtime = DbcRuntime(runtime_paths.dbc_path)
    balance_module_count = int(
        runtime_config.get(
            "BALANCE_MODULE_COUNT",
            runtime_config.get("LECU_NUM", 4),
        )
    )
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
    )
    driver = CxCanFdDriver()
    return CanApplicationService(
        runtime_config=runtime_config,
        bus_config=bus_config,
        driver=driver,
        legacy_catalog=legacy_catalog,
        dbc_runtime=dbc_runtime,
        log_manager=log_manager,
    )


def main():
    service = build_service()
    started_at = time.time()
    deadline = started_at + 5.0
    total_legacy_updates = 0
    total_periodic_updates = 0
    seen_reply_ids = set()
    seen_periodic_ids = set()

    try:
        service.open()
        print("hardware_smoke,open=ok", flush=True)
        query_result = service.send_next_query(1)
        print(f"hardware_smoke,query_result={query_result}", flush=True)

        while time.time() < deadline:
            poll_result = service.poll()
            total_legacy_updates += len(poll_result.legacy_updates)
            total_periodic_updates += len(poll_result.periodic_updates)

            for update in poll_result.legacy_updates:
                seen_reply_ids.add(f"cluster_{update.cluster_index}:{update.signal_name}")
            for update in poll_result.periodic_updates:
                seen_periodic_ids.add(f"{update.address}:{update.message_name}")
            time.sleep(0.05)

        print(
            "hardware_smoke,"
            f"legacy_updates={total_legacy_updates},"
            f"periodic_updates={total_periodic_updates},"
            f"legacy_samples={len(seen_reply_ids)},"
            f"periodic_samples={len(seen_periodic_ids)}",
            flush=True,
        )
        for sample in sorted(seen_reply_ids)[:10]:
            print(f"hardware_smoke,legacy_sample={sample}", flush=True)
        for sample in sorted(seen_periodic_ids)[:10]:
            print(f"hardware_smoke,periodic_sample={sample}", flush=True)
    finally:
        service.close()
        print("hardware_smoke,close=ok", flush=True)


if __name__ == "__main__":
    main()
