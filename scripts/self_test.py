import csv
import os
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.reader(csv_file))


def _set_snapshot_value(record, key_prefix, value):
    for key in record:
        if key.startswith(key_prefix):
            record[key] = value
            return key
    raise AssertionError(f"{key_prefix} snapshot field not found")


def test_configuration_round_trip():
    from application.configuration import (
        DEFAULT_CAN_BOARD_CONFIG,
        build_cluster_addresses,
        build_cluster_indices,
        load_can_board_config,
        save_can_board_config,
    )

    with tempfile.TemporaryDirectory(prefix="aidc_config_test_") as temp_dir:
        config_path = Path(temp_dir) / "config.json"
        saved = save_can_board_config(
            {
                "can_type": "usb_can_4eu",
                "can_idx": "2",
                "chn": "1",
                "baud_rate": "500",
            },
            config_path,
        )
        loaded = load_can_board_config(config_path)

    _assert(saved == loaded, "CAN board config round trip mismatch")
    _assert(loaded["can_idx"] == 2, "CAN index should be normalized to int")
    _assert(load_can_board_config("__missing_config__.json") == DEFAULT_CAN_BOARD_CONFIG, "missing config should use defaults")

    runtime_config = {"BCU_NUM": 2, "ADDRESLIST": ["00", "A0", "A1", "A2"]}
    _assert(build_cluster_indices(runtime_config) == [1, 2], "cluster indices mismatch")
    _assert(build_cluster_addresses(runtime_config) == ["A0", "A1"], "cluster addresses mismatch")


def test_session_logger_files():
    from session_logger import SessionLogManager

    with tempfile.TemporaryDirectory(prefix="aidc_logger_test_") as temp_dir:
        logger = SessionLogManager(
            temp_dir,
            cluster_indices=[1],
            cluster_addresses=["A0"],
            runtime_signal_names=["SOC", "RUN_STATE"],
            voltage_count=2,
            temperature_count=2,
            balance_module_count=1,
            balance_cells_per_module=2,
            abnormal_count=2,
            enabled=True,
        )
        frame = SimpleNamespace(
            frame_id=0x1880A0F2,
            data=bytes([1, 2, 3, 4, 5, 6, 7, 8]),
            data_len=8,
            extern_flag=True,
            remote_flag=False,
        )
        logger.log_tx("tx_can", "dev0/ch1", frame, 1)
        logger.log_rx("rx_can", frame, ["self_test"])
        logger.write_cluster_snapshot(1, {"SOC": 88, "RUN_STATE": 5})
        logger.write_voltage_snapshot("A0", [3301, 3302])
        logger.write_temperature_snapshot("A0", [251, 252])
        logger.write_balance_snapshot("A0", [1, 0])
        logger.write_abnormal_snapshot("A0", [0, 2])
        logger.close()

        tx_rows = _read_csv(logger.tx_path)
        rx_rows = _read_csv(logger.rx_path)
        runtime_rows = _read_csv(logger.runtime_path_by_index[1])
        voltage_rows = _read_csv(logger.voltage_path_by_address["A0"])

    _assert(len(tx_rows) == 2, "TX log row count mismatch")
    _assert(len(rx_rows) == 2, "RX log row count mismatch")
    _assert(runtime_rows[1][1:] == ["88", "5"], "runtime snapshot mismatch")
    _assert(voltage_rows[1][1:] == ["3301", "3302"], "voltage snapshot mismatch")


def test_main_window_offscreen_logging():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    import main as main_module

    main_module.Edit._connect_can = lambda self, show_dialog=False: False
    app = QApplication.instance() or QApplication([])
    window = main_module.Edit()
    try:
        _assert(
            all(window.cluster_selector.itemData(index) > 0 for index in range(window.cluster_selector.count())),
            "top cluster selector should not expose 00 cluster index",
        )

        original_bcu_num = main_module.config["BCU_NUM"]
        original_address_list = list(main_module.config["ADDRESLIST"])
        try:
            main_module.config["BCU_NUM"] = 5
            main_module.config["ADDRESLIST"] = ["00", "A0", "00", "0x00", "A3", ""]
            _assert(
                window._build_cluster_options() == [(1, "A0"), (4, "A3")],
                "uncompiled 00 addresses should be filtered from cluster options",
            )
        finally:
            main_module.config["BCU_NUM"] = original_bcu_num
            main_module.config["ADDRESLIST"] = original_address_list

        with tempfile.TemporaryDirectory(prefix="aidc_ui_log_test_") as temp_dir:
            window._runtime_log_dir = lambda: temp_dir
            window._set_active_cluster(1, refresh=False, source="self_test")
            window.log_scope_selector.setCurrentIndex(window.log_scope_selector.findData("current"))
            window.save_log_checkbox.setChecked(True)

            _set_snapshot_value(window.ResDataRec[1], "SOC", "88")
            _set_snapshot_value(window.ResDataRec[2], "SOC", "99")

            cell_count = int(main_module.config["LECU_NUM"]) * int(main_module.config["CELL_NUM"])
            temp_count = int(main_module.config["LECU_NUM"]) * int(main_module.config["CELL_Tem_NUM"])
            main_module.Vres = [3300 + index for index in range(cell_count)]
            main_module.VresTem = [250 + index for index in range(temp_count)]
            main_module.VresBAL = [index % 2 for index in range(cell_count)]
            main_module.VresDXYC = [0 for _ in range(cell_count)]

            window.voltage_snapshot_dirty = True
            window.temperature_snapshot_dirty = True
            window.balance_snapshot_dirty = True
            window.abnormal_snapshot_dirty = True
            window.SaveRunData()

            window.log_scope_selector.setCurrentIndex(window.log_scope_selector.findData("all"))
            window.SaveRunData()

            tab_names = [
                window.tabWidget.tabText(index)
                for index in range(window.tabWidget.count())
            ]
            _assert("实时监控" in tab_names, "realtime monitor tab is missing")
            window.tabWidget.setCurrentIndex(window._realtime_monitor_tab_index())
            window._refresh_realtime_monitor_page()
            _assert(window.S27.value_fields["soc"].text() == "8.8 %", "realtime SOC value mismatch")
            _assert(window.S27.value_fields["max_cell_voltage"].text().endswith("mV"), "realtime voltage extrema missing")

            window._close_session_log()

            log_dir = Path(temp_dir)
            runtime_files = list(log_dir.rglob("*runtime_cluster_1.csv"))
            all_scope_runtime_files = list(log_dir.rglob("*runtime_cluster_2.csv"))
            voltage_files = list(log_dir.rglob("*voltage_A0.csv"))
            temperature_files = list(log_dir.rglob("*temperature_A0.csv"))
            balance_files = list(log_dir.rglob("*balance_A0.csv"))
            abnormal_files = list(log_dir.rglob("*abnormal_A0.csv"))

            _assert(runtime_files, "runtime CSV was not created")
            _assert(all_scope_runtime_files, "all-scope runtime CSV was not created")
            _assert(voltage_files, "voltage CSV was not created")
            _assert(temperature_files, "temperature CSV was not created")
            _assert(balance_files, "balance CSV was not created")
            _assert(abnormal_files, "abnormal CSV was not created")

            runtime_rows = _read_csv(runtime_files[0])
            soc_index = next(index for index, header in enumerate(runtime_rows[0]) if header.startswith("SOC"))
            _assert(runtime_rows[1][soc_index] == "88", "UI runtime SOC snapshot mismatch")
            all_scope_runtime_rows = _read_csv(all_scope_runtime_files[0])
            all_scope_soc_index = next(
                index for index, header in enumerate(all_scope_runtime_rows[0]) if header.startswith("SOC")
            )
            _assert(len(all_scope_runtime_rows) == 2, "current-scope logging should not append cluster 2")
            _assert(
                all_scope_runtime_rows[1][all_scope_soc_index] == "99",
                "all-scope runtime SOC snapshot mismatch",
            )
    finally:
        window.close()
        if QApplication.instance() is app:
            app.quit()


def main():
    tests = [
        test_configuration_round_trip,
        test_session_logger_files,
        test_main_window_offscreen_logging,
    ]
    failures = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failures.append((test.__name__, exc, traceback.format_exc()))
            print(f"FAIL {test.__name__}: {exc}")

    if failures:
        print("\nSelf test failures:")
        for name, _exc, detail in failures:
            print(f"\n{name}\n{detail}")
        return 1

    print(f"\nSELF_TEST_OK tests={len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
