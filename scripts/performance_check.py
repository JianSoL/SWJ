import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def benchmark_trend_store():
    from application.trend_store import TrendDataStore

    store = TrendDataStore(max_bars_per_period=480)
    start = time.perf_counter()
    for index in range(100000):
        store.add_sample(1, "voltage", 600.0 + (index % 31) * 0.1, 1_700_000_000 + index * 0.1)
    ingest_seconds = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(5000):
        store.bars_for(1, "voltage", 5, 240)
    read_seconds = time.perf_counter() - start
    stats = store.memory_stats()
    _require(stats["sample_count"] == 100000, "trend sample count mismatch")
    _require(
        stats["bar_count"] <= len(store.periods) * store.max_bars_per_period,
        "trend store exceeded bounded capacity",
    )
    return {
        "trend_ingest_s": ingest_seconds,
        "trend_5000_reads_s": read_seconds,
        "trend_bar_count": stats["bar_count"],
    }


def benchmark_dbc_batch(app):
    from UI.T36 import DbcParsePage

    page = DbcParsePage()
    page.hide()
    payload = bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F])
    start = time.perf_counter()
    for timestamp in range(5000):
        page.handle_can_frame(0x1204EFA0, payload, timestamp=timestamp + 1)
    decode_seconds = time.perf_counter() - start
    _require(page.live_table.rowCount() == 0, "hidden DBC page performed table writes")
    _require(0 < len(page.live_pending_updates) < 20, "DBC pending cache is not bounded by signal")
    pending_count = len(page.live_pending_updates)
    page.flush_live_updates()
    _require(page.live_table.rowCount() == pending_count, "DBC batch flush row mismatch")
    page.close()
    app.processEvents()
    return {
        "dbc_5000_decode_s": decode_seconds,
        "dbc_pending_signals": pending_count,
    }


def benchmark_session_logger():
    from session_logger import SessionLogManager

    frame = SimpleNamespace(
        frame_id=0x1880A0F2,
        data=bytes([1, 2, 3, 4, 5, 6, 7, 8]),
        data_len=8,
        extern_flag=True,
        remote_flag=False,
    )
    with tempfile.TemporaryDirectory(prefix="aidc_perf_log_") as temp_dir:
        logger = SessionLogManager(
            temp_dir,
            cluster_indices=[1],
            cluster_addresses=["A0"],
            runtime_signal_names=["SOC"],
            enabled=True,
        )
        start = time.perf_counter()
        for _ in range(10000):
            logger.log_rx("rx_can", frame)
        write_seconds = time.perf_counter() - start
        row_count = logger.rx_writer.row_count
        logger.close()
    _require(row_count == 10000, "session logger row count mismatch")
    return {"log_10000_rows_s": write_seconds}


def benchmark_request_scheduler(app):
    import main as main_module

    main_module.Edit._connect_can = lambda self, show_dialog=False: False
    window = main_module.Edit()
    query_count = 0

    def record_query(_cluster_index, _data):
        nonlocal query_count
        query_count += 1

    window.c = SimpleNamespace(close=lambda: None, log_manager=None)
    window.can_ready = True
    window.QueryData = record_query
    window.table_index = window._realtime_monitor_tab_index()
    simulated_clock = [100.0]
    ticks = int(12.0 / (main_module.CAN_REQUEST_NORMAL_INTERVAL_MS / 1000.0))
    with patch.object(main_module.time, "monotonic", lambda: simulated_clock[0]):
        for tick in range(ticks):
            simulated_clock[0] = 100.0 + tick * (main_module.CAN_REQUEST_NORMAL_INTERVAL_MS / 1000.0)
            window.last_can_rx_monotonic = simulated_clock[0]
            window.can_connected_monotonic = simulated_clock[0]
            window.RequestBCUVAR()

    page_request_limit = ticks * main_module.CAN_REQUEST_BURST_PER_TICK
    shared_request_limit = int(12.0 / main_module.SYSTEM_KLINE_BACKGROUND_INTERVAL_S) + 2
    _require(
        query_count <= page_request_limit + shared_request_limit,
        "request scheduler exceeded page and shared-signal load budget",
    )
    window.close()
    app.processEvents()
    return {
        "request_ticks": ticks,
        "request_count": query_count,
        "request_budget": page_request_limit + shared_request_limit,
    }


def main():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    metrics = {}
    metrics.update(benchmark_trend_store())
    metrics.update(benchmark_dbc_batch(app))
    metrics.update(benchmark_session_logger())
    metrics.update(benchmark_request_scheduler(app))
    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}={value:.4f}")
        else:
            print(f"{name}={value}")
    print("PERFORMANCE_CHECK_OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"PERFORMANCE_CHECK_FAILED: {exc}")
        sys.exit(1)
