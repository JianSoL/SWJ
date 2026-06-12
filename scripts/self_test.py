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
                "Has_N": "1",
            },
            config_path,
        )
        loaded = load_can_board_config(config_path)

    _assert(saved == loaded, "CAN board config round trip mismatch")
    _assert(loaded["can_idx"] == 2, "CAN index should be normalized to int")
    _assert(loaded["Has_N"] == 1, "Has_N should be normalized to int flag")
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
            window.cluster_selector.itemData(0) == 0,
            "top cluster selector should expose 00 uncompiled cluster index",
        )
        _assert(
            "未编制" in window.cluster_selector.itemText(0),
            "00 cluster selector option should be marked as uncompiled",
        )
        _assert(
            window.cluster_selector.currentData() > 0,
            "default cluster selector should still choose the first compiled cluster",
        )
        original_has_n = main_module.config.get("Has_N", 0)
        try:
            window._set_has_neutral(1, persist=False, refresh=True)
            _assert(main_module.config["Has_N"] == 1, "Has_N runtime config should switch to neutral mode")
            _assert(window.has_neutral_checkbox.isChecked(), "neutral checkbox should mirror Has_N=1")
            _assert(window.label[window.CLUSTER_TAB_INDEX][0].text() == "上半簇信息", "neutral label should show upper half")
            window._set_has_neutral(0, persist=False, refresh=True)
            _assert(main_module.config["Has_N"] == 0, "Has_N runtime config should switch to no-neutral mode")
            _assert(not window.has_neutral_checkbox.isChecked(), "neutral checkbox should mirror Has_N=0")
            _assert(
                window.label[window.CLUSTER_TAB_INDEX][1].text() == "未使用（无中线）",
                "no-neutral label should mark lower half table unused",
            )
        finally:
            window._set_has_neutral(original_has_n, persist=False, refresh=True)

        original_bcu_num = main_module.config["BCU_NUM"]
        original_address_list = list(main_module.config["ADDRESLIST"])
        try:
            main_module.config["BCU_NUM"] = 5
            main_module.config["ADDRESLIST"] = ["00", "A0", "00", "0x00", "A3", ""]
            _assert(
                window._build_cluster_options() == [(0, "00"), (1, "A0"), (4, "A3")],
                "cluster options should include 00 placeholder and filter uncompiled cluster slots",
            )
        finally:
            main_module.config["BCU_NUM"] = original_bcu_num
            main_module.config["ADDRESLIST"] = original_address_list

        window._set_active_cluster(0, refresh=True, source="self_test")
        _assert(window._active_cluster_index() == 0, "00 uncompiled cluster should be selectable")
        _assert(window.cluster_selector.currentData() == 0, "cluster selector should sync to 00 uncompiled option")

        window._cache_host_control_snapshot(1, {"work_mode": main_module.WORK_MODE_GZ_TEST}, merge=False)
        window._cache_host_control_snapshot(2, {"work_mode": main_module.WORK_MODE_NORMAL}, merge=False)
        window._set_active_cluster(1, refresh=False, source="self_test")
        _assert("开" in window.S17.work_mode_label.text(), "cluster 1 should show cached factory mode on")
        _assert("开" in window.factory_status_label.text(), "top factory status should show cluster 1 factory mode")
        window._set_active_cluster(2, refresh=False, source="self_test")
        _assert("关" in window.S17.work_mode_label.text(), "cluster 2 should show its own cached factory mode off")
        _assert("关" in window.factory_status_label.text(), "top factory status should show cluster 2 factory mode")
        window.host_control_snapshots.pop(2, None)
        window._set_active_cluster(1, refresh=False, source="self_test")
        window._set_active_cluster(2, refresh=False, source="self_test")
        _assert("--" in window.S17.work_mode_label.text(), "cluster without cache should not reuse another cluster factory mode")
        _assert("未知" in window.factory_status_label.text(), "top factory status should be unknown without cluster cache")

        original_frozen = getattr(main_module.sys, "frozen", None)
        original_executable = main_module.sys.executable
        with tempfile.TemporaryDirectory(prefix="aidc_exe_log_dir_test_") as temp_dir:
            main_module.sys.frozen = True
            main_module.sys.executable = str(Path(temp_dir) / "main.exe")
            try:
                expected_log_dir = str(Path(temp_dir) / "hisData")
                _assert(window._runtime_log_dir() == expected_log_dir, "exe runtime log dir should be beside main.exe")
                _assert(window._history_log_dir() == expected_log_dir, "exe history log dir should be beside main.exe")
            finally:
                main_module.sys.executable = original_executable
                if original_frozen is None:
                    delattr(main_module.sys, "frozen")
                else:
                    main_module.sys.frozen = original_frozen

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
            _assert("实时告警" in tab_names, "active alarm tab is missing")
            _assert("实时监控" in tab_names, "realtime monitor tab is missing")
            _assert(window.S28.auto_refresh_checkbox.isChecked(), "active alarm auto refresh should be enabled by default")
            window.tabWidget.setCurrentIndex(window._realtime_monitor_tab_index())
            _assert(36 in window.realtime_monitor_signal_ids, "realtime monitor should poll DI indexes")
            _assert(112 in window.realtime_monitor_signal_ids, "realtime monitor should poll RT indexes")
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_WORK_MODE, 1)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_RUN_STATUS, 5)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_CURR, main_module.to_unsigned_16bit(-123))
            window._cache_realtime_monitor_index_value(1, main_module.VAR_HALL_CURR, 456)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SHUNT_CURR, main_module.to_unsigned_16bit(-78))
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_ANALOG_BAT_VOLT, 6123)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_VOLT, 6110)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_ANALOG_PACK_VOLT, 5987)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_SOC, 888)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_DIS_SOC, 887)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_SOH, 990)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_DIFF_VOLT, 12)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_AVG_VOLT, 3321)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_AVG_TEMP, 251)
            window._cache_realtime_monitor_index_value(1, main_module.PAR_SYS_MODULE_COUNT, 4)
            window._cache_realtime_monitor_index_value(1, main_module.PAR_SYS_AFE_COUNT, 2)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_ONLINE_LECU_NUM, 3)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_CELL_VOLT_MAX, 3456)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_MAXV_POSI, 0x0203)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_CELL_VOLT_MIN, 3210)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_MINV_POSI, 0x0104)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_CELL_TEMP_MAX, 403)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_MAXT_POSI, 0x0302)
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_CELL_TEMP_MIN, main_module.to_unsigned_16bit(-52))
            window._cache_realtime_monitor_index_value(1, main_module.VAR_SYS_MINT_POSI, 0x0401)
            window._cache_realtime_monitor_index_value(1, 36, 0xFFFF)
            window._cache_realtime_monitor_index_value(1, 37, 0)
            window._cache_realtime_monitor_index_value(1, 48, 1)
            window._cache_realtime_monitor_index_value(1, 49, 0)
            window._cache_realtime_monitor_index_value(1, 112, 251)
            window._cache_realtime_monitor_index_value(1, 113, main_module.to_unsigned_16bit(-52))
            window._cache_realtime_monitor_index_value(1, 122, 305)
            window._cache_realtime_monitor_index_value(1, main_module.PAR_SYS_OUTPUT_HVIL_FREQ, 500)
            window._cache_realtime_monitor_index_value(1, main_module.PAR_SYS_OUTPUT_HVIL_DUTY_RATIO, 625)
            window._refresh_realtime_monitor_page()
            _assert(window.S27.value_fields["soc"].text() == "88.8 %", "realtime SOC value mismatch")
            _assert(window.S27.value_fields["system_current"].text() == "-12.3 A", "realtime system current mismatch")
            _assert(window.S27.value_fields["battery_voltage"].text() == "612.3 V", "realtime battery voltage mismatch")
            _assert(window.S27.value_fields["max_cell_voltage"].text() == "3456 mV", "realtime voltage extrema missing")
            _assert(window.S27.value_fields["max_cell_voltage_module"].text() == "2", "realtime voltage module mismatch")
            _assert(window.S27.value_fields["max_cell_voltage_index"].text() == "3", "realtime voltage position mismatch")
            _assert(window.S27.input_dots[0]._active is True, "realtime DI1 state mismatch")
            _assert(window.S27.input_dots[1]._active is False, "realtime DI2 state mismatch")
            _assert(window.S27.output_dots[0]._active is True, "realtime HSD1 state mismatch")
            _assert(window.S27.output_dots[1]._active is False, "realtime HSD2 state mismatch")
            _assert(window.S27.rt_fields[0].text() == "25.1 ℃", "realtime RT1 temperature mismatch")
            _assert(window.S27.value_fields["hvil_pwm_freq"].text() == "50 Hz", "realtime HVIL frequency mismatch")

            active_alarm = window.decode_active_alarm_frames(
                SimpleNamespace(data=bytes([0xFE, 1, 3, 2, 1, 4, 0, 1])),
                SimpleNamespace(data=bytes([0xFF, 1, 24, 5, 6, 7, 8, 9])),
            )
            _assert(active_alarm["index"] == 1, "active alarm index mismatch")
            _assert(active_alarm["alarm_id"] == 1, "active alarm display id mismatch")
            _assert(active_alarm["alarm_level_text"] == "4 四级", "active alarm level mismatch")
            _assert(active_alarm["bat_text"] == "1 下半簇", "active alarm half-cluster mismatch")
            _assert(active_alarm["start_time"] == "2024-05-06 07:08:09", "active alarm time mismatch")
            window.S28.set_active_alarm_records([active_alarm], total_count=1)
            _assert(window.S28.active_alarm_table.rowCount() == 1, "active alarm table row count mismatch")
            _assert(window.S28.active_alarm_table.item(0, 1).text() == "1", "active alarm table id mismatch")
            _assert(window.S28.active_alarm_table.item(0, 7).text() == "2024-05-06 07:08:09", "active alarm table time mismatch")

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
