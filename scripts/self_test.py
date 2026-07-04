import csv
import json
import os
import sys
import tempfile
import time
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
        LOG_INTERVAL_CONFIG_KEY,
        build_cluster_addresses,
        build_cluster_indices,
        load_can_board_config,
        load_runtime_config_overrides,
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
                "BCU_NUM": "4",
                "LECU_NUM": "8",
                "CELL_NUM": "20",
                "CELL_Tem_NUM": "12",
                LOG_INTERVAL_CONFIG_KEY: "2500",
            },
            config_path,
        )
        loaded = load_can_board_config(config_path)
        overrides = load_runtime_config_overrides(config_path)

    _assert(saved == loaded, "CAN board config round trip mismatch")
    _assert(loaded["can_idx"] == 2, "CAN index should be normalized to int")
    _assert(loaded["Has_N"] == 1, "Has_N should be normalized to int flag")
    _assert(loaded["BCU_NUM"] == 4, "cluster count should be normalized to int")
    _assert(loaded["LECU_NUM"] == 8, "module count should be normalized to int")
    _assert(loaded["CELL_NUM"] == 20, "cell count should be normalized to int")
    _assert(loaded["CELL_Tem_NUM"] == 12, "temperature count should be normalized to int")
    _assert(loaded[LOG_INTERVAL_CONFIG_KEY] == 2500, "log interval should be normalized to int milliseconds")
    _assert(overrides["BCU_NUM"] == 4, "runtime override should include cluster count")
    _assert(overrides["CELL_Tem_NUM"] == 12, "runtime override should include temperature count")
    _assert(overrides[LOG_INTERVAL_CONFIG_KEY] == 2500, "runtime override should include log interval")
    _assert(load_can_board_config("__missing_config__.json") == DEFAULT_CAN_BOARD_CONFIG, "missing config should use defaults")

    runtime_config = {"BCU_NUM": 2, "ADDRESLIST": ["00", "A0", "A1", "A2"]}
    _assert(build_cluster_indices(runtime_config) == [1, 2], "cluster indices mismatch")
    _assert(build_cluster_addresses(runtime_config) == ["A0", "A1"], "cluster addresses mismatch")


def test_trend_data_store():
    from application.trend_store import TrendDataStore, aggregate_period_statistics

    store = TrendDataStore(max_bars_per_period=24)
    base = 1_700_000_000
    samples = []
    for index in range(5000):
        timestamp = base + index
        value = 600.0 + (index % 17) * 0.1
        samples.append((timestamp, value))
        _assert(store.add_sample(1, "voltage", value, timestamp), "trend sample should be accepted")

    _assert(store.sample_count(1, "voltage") == 5000, "trend sample count mismatch")
    _assert(len(store.bars_for(1, "voltage", 1, 240)) == 24, "trend store should enforce bar capacity")
    _assert(len(store.bars_for(1, "voltage", 60, 10)) == 10, "trend window limit mismatch")
    _assert(store.latest_value(1, "voltage") == samples[-1][1], "trend latest value mismatch")
    stats = store.memory_stats()
    _assert(stats["bar_count"] <= len(store.periods) * 24, "trend memory should remain bounded")

    comparison_samples = samples[:25]
    reference = aggregate_period_statistics(comparison_samples, 5, 24)
    comparison_store = TrendDataStore(max_bars_per_period=24)
    for timestamp, value in comparison_samples:
        comparison_store.add_sample(1, "voltage", value, timestamp)
    _assert(
        comparison_store.bars_for(1, "voltage", 5, 24) == reference,
        "incremental aggregation should match reference aggregation",
    )
    comparison_store.add_sample(2, "voltage", 700.0, base)
    _assert(comparison_store.latest_value(1, "voltage") != 700.0, "trend clusters should be isolated")
    comparison_store.clear_cluster(1)
    _assert(comparison_store.sample_count(1, "voltage") == 0, "trend cluster clear mismatch")


def test_session_logger_files():
    from session_logger import SessionLogManager, _RollingCsvWriter

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
        logger.flush()
        _assert(logger.rx_writer.pending_row_count == 0, "explicit log flush should drain buffered rows")
        logger.close()

        buffered_writer = _RollingCsvWriter(
            Path(temp_dir) / "buffered.csv",
            ["value"],
            max_rows=100,
            flush_row_interval=3,
            flush_interval_s=3600,
        )
        buffered_writer.write_row([1])
        buffered_writer.write_row([2])
        _assert(buffered_writer.pending_row_count == 2, "log writer should buffer rows")
        buffered_writer.write_row([3])
        _assert(buffered_writer.pending_row_count == 0, "log writer should flush at row threshold")
        buffered_writer.close()

        tx_rows = _read_csv(logger.tx_path)
        rx_rows = _read_csv(logger.rx_path)
        runtime_rows = _read_csv(logger.runtime_path_by_index[1])
        voltage_rows = _read_csv(logger.voltage_path_by_address["A0"])

    _assert(len(tx_rows) == 2, "TX log row count mismatch")
    _assert(len(rx_rows) == 2, "RX log row count mismatch")
    _assert(runtime_rows[1][1:] == ["88", "5"], "runtime snapshot mismatch")
    _assert(voltage_rows[1][1:] == ["3301", "3302"], "voltage snapshot mismatch")


def test_module_cell_grid_module_extrema():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from UI import module_cell_grid

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    original_module_count = module_cell_grid.config.get("LECU_NUM")
    try:
        module_cell_grid.config["LECU_NUM"] = 2
        grid = module_cell_grid.ModuleCellGrid("self test", "mV", mode="numeric", cells_per_module=2)
        try:
            grid.setVoltageValues([1, 9, 100, 200])
            _assert("#fef9c3" in grid.lineEdits[0].styleSheet(), "module 1 minimum should be highlighted")
            _assert("#fee2e2" in grid.lineEdits[1].styleSheet(), "module 1 maximum should be highlighted")
            _assert("#fef9c3" in grid.lineEdits[2].styleSheet(), "module 2 minimum should be highlighted")
            _assert("#fee2e2" in grid.lineEdits[3].styleSheet(), "module 2 maximum should be highlighted")
        finally:
            grid.close()
    finally:
        module_cell_grid.config["LECU_NUM"] = original_module_count
        if created_app:
            app.quit()


def test_cell_visualization_page():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from UI.T37 import CellVisualizationPage

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    page = CellVisualizationPage()
    try:
        voltage_count = page.voltage_panel.module_count * page.voltage_panel.cells_per_module
        temperature_count = page.temperature_panel.module_count * page.temperature_panel.cells_per_module
        voltage_values = [3300] * voltage_count
        voltage_values[0] = 3288
        voltage_values[1] = 0
        voltage_values[-1] = 3321
        temperature_values = [250] * temperature_count
        temperature_values[0] = -55
        temperature_values[-1] = 407
        page.show()
        page.set_values(voltage_values, temperature_values)
        page.redraw_timer.stop()
        page._redraw_active_chart()

        _assert(page.voltage_panel.summary["count"] == voltage_count - 1, "voltage 3D count mismatch")
        _assert(page.voltage_panel.summary["minimum"] == 3288, "voltage 3D minimum mismatch")
        _assert(page.voltage_panel.summary["maximum"] == 3321, "voltage 3D maximum mismatch")
        _assert(page.voltage_panel.summary["minimum_index"] == 0, "voltage 3D minimum position mismatch")
        _assert(
            page.voltage_panel.summary["maximum_index"] == voltage_count - 1,
            "voltage 3D maximum position mismatch",
        )
        _assert(page.temperature_panel.summary["minimum"] == -5.5, "temperature scaling mismatch")
        _assert(page.temperature_panel.summary["maximum"] == 40.7, "temperature maximum mismatch")

        page.resize(1366, 768)
        for _ in range(3):
            app.processEvents()
        _assert(page.chart_tabs.width() > 1000, "3D chart should fill laptop width")
        _assert(len(page.voltage_panel.canvas.entries) == voltage_count - 1, "voltage bars were not rendered")
        _assert(
            page.voltage_panel.view_buttons["perspective"].isChecked(),
            "perspective view should be selected by default",
        )
        _assert(page.voltage_panel.canvas.module_axes.get_visible(), "module profile should be visible")
        _assert(
            len(page.voltage_panel.canvas.module_axes.get_yticklabels()) == page.voltage_panel.module_count,
            "module profile labels mismatch",
        )
        page.voltage_panel.view_buttons["top"].click()
        _assert(page.voltage_panel.canvas.elevation == 72, "top view elevation mismatch")
        _assert(page.voltage_panel.canvas.azimuth == -90, "top view azimuth mismatch")
        page.voltage_panel.view_buttons["perspective"].click()
        _assert(page.voltage_panel.canvas.elevation == 27, "perspective elevation mismatch")
        page.voltage_panel.average_plane_checkbox.setChecked(False)
        _assert(not page.voltage_panel.canvas.show_average_plane, "average plane should be hidden")
        page.voltage_panel.average_plane_checkbox.setChecked(True)
        _assert(page.voltage_panel.canvas.show_average_plane, "average plane should be restored")

        page.resize(1920, 1080)
        for _ in range(3):
            app.processEvents()
        _assert(page.chart_tabs.width() > 1500, "3D chart should expand at desktop width")
        page.chart_tabs.setCurrentIndex(1)
        for _ in range(3):
            app.processEvents()
        _assert(len(page.temperature_panel.canvas.entries) == temperature_count, "temperature bars were not rendered")

        page.clear_values()
        _assert(page.voltage_panel.summary["count"] == 0, "voltage 3D chart should clear")
        _assert(page.temperature_panel.summary["count"] == 0, "temperature 3D chart should clear")
    finally:
        page.close()
        if created_app:
            app.quit()


def test_system_kline_page():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from UI.T38 import SystemKLinePage, aggregate_period_statistics

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    page = SystemKLinePage()
    try:
        bucket_start = 1_700_000_000
        bucket_start -= bucket_start % 5
        samples = [
            (bucket_start + 0.2, 600.0),
            (bucket_start + 1.0, 602.5),
            (bucket_start + 2.0, 598.5),
            (bucket_start + 4.8, 601.0),
            (bucket_start + 5.1, 603.0),
        ]
        bars = aggregate_period_statistics(samples, 5, 120)
        _assert(len(bars) == 2, "K-line aggregation should produce two buckets")
        _assert(bars[0].first == 600.0, "K-line period-first value mismatch")
        _assert(bars[0].maximum == 602.5, "K-line period-maximum mismatch")
        _assert(bars[0].minimum == 598.5, "K-line period-minimum mismatch")
        _assert(bars[0].latest == 601.0, "K-line latest value mismatch")
        _assert(bars[0].sample_count == 4, "K-line sample count mismatch")

        page.set_cluster_context(1, "A0")
        for timestamp, value in samples:
            _assert(page.add_sample(1, "voltage", value, timestamp), "voltage sample should be accepted")
        page.add_sample(1, "hall_current", -12.5, bucket_start + 0.5)
        page.add_sample(1, "hall_current", 8.0, bucket_start + 1.5)
        page.add_sample(1, "shunt_current", -7.8, bucket_start + 0.8)
        page.add_sample(1, "shunt_current", 4.2, bucket_start + 1.8)
        page.add_sample(2, "voltage", 700.0, bucket_start + 0.5)
        _assert(len(page.bars_for(1, "voltage", 5, 120)) == 2, "cluster 1 K-line count mismatch")
        _assert(page.bars_for(2, "voltage", 5, 120)[0].latest == 700.0, "cluster 2 data missing")
        _assert(page.bars_for(1, "voltage", 5, 120)[0].maximum == 602.5, "cluster data should be isolated")
        current_bar = page.bars_for(1, "hall_current", 5, 120)[0]
        _assert(
            current_bar.minimum == -12.5 and current_bar.maximum == 8.0,
            "signed Hall current K-line mismatch",
        )
        shunt_bar = page.bars_for(1, "shunt_current", 5, 120)[0]
        _assert(
            shunt_bar.minimum == -7.8 and shunt_bar.maximum == 4.2,
            "signed shunt current K-line mismatch",
        )

        page.show()
        page.resize(1366, 768)
        page.refresh_active_chart(force=True)
        for _ in range(3):
            app.processEvents()
        _assert(page.chart_tabs.width() > 1000, "K-line chart should fill laptop width")
        _assert(len(page.panels["voltage"].canvas.bars) == 2, "voltage candles were not rendered")

        stream_bucket = bucket_start + 10
        for sample_index in range(9):
            page.add_sample(
                1,
                "voltage",
                604.0 + sample_index * 0.1,
                stream_bucket + sample_index * 0.05,
            )
            app.processEvents()
            time.sleep(0.05)
        app.processEvents()
        _assert(
            len(page.panels["voltage"].canvas.bars) == 3,
            "continuous samples should not postpone the scheduled chart redraw",
        )

        page.resize(1920, 1080)
        page.chart_tabs.setCurrentIndex(1)
        page.refresh_active_chart(force=True)
        for _ in range(3):
            app.processEvents()
        _assert(page.chart_tabs.width() > 1500, "K-line chart should expand at desktop width")
        _assert(len(page.panels["hall_current"].canvas.bars) == 1, "Hall current candles were not rendered")

        page.chart_tabs.setCurrentIndex(2)
        page.refresh_active_chart(force=True)
        for _ in range(3):
            app.processEvents()
        _assert(
            len(page.panels["shunt_current"].canvas.bars) == 1,
            "shunt current candles were not rendered",
        )

        page.pause_checkbox.setChecked(True)
        paused_count = page.sample_count(1, "shunt_current")
        page.add_sample(1, "shunt_current", -3.0, bucket_start + 2.0)
        _assert(
            page.sample_count(1, "shunt_current") == paused_count + 1,
            "paused chart should keep collecting shunt data",
        )
        page.pause_checkbox.setChecked(False)
        page.set_cluster_context(0, "00")
        _assert(
            not page.panels["shunt_current"].canvas.bars,
            "00 cluster should show an empty K-line chart",
        )
        _assert(
            page.sample_count(1, "voltage") == len(samples) + 9,
            "00 selection should preserve compiled cluster history",
        )
    finally:
        page.close()
        if created_app:
            app.quit()


def test_dbc_parser():
    from application.dbc_parser import parse_dbc_file

    database = parse_dbc_file(PROJECT_DIR / "IDC.dbc")
    _assert(len(database.messages) >= 20, "DBC parser should load messages")
    _assert(database.signal_count >= 90, "DBC parser should load signals")
    _assert(set(database.nodes) >= {"BAU", "BCU"}, "DBC parser should load nodes")
    _assert(not database.parse_warnings, "IDC.dbc should parse without warnings")

    message = next((item for item in database.messages if item.name == "BCU1204EFA0"), None)
    _assert(message is not None, "DBC parser should expose BCU1204EFA0")
    signal_names = {signal.name for signal in message.signals}
    _assert("Chargeable_battery_KWH_UP" in signal_names, "DBC parser should expose message signals")
    decoded = database.decode_frame(
        0x1204EFA0,
        bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F]),
    )
    _assert(decoded is not None, "DBC parser should match live CAN frame id")
    decoded_values = {
        signal.signal.name: signal.physical_value
        for signal in decoded.signals
    }
    _assert(decoded_values["Chargeable_battery_KWH_UP"] == 10, "DBC live decode value mismatch")
    _assert(decoded_values["Current_Discharging_KWH_UP"] == 40, "DBC live decode high word mismatch")


def test_index_catalog_and_browser():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from application.index_catalog import IndexCatalog
    from UI.T24 import HostControlPage

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="aidc_index_catalog_test_") as temp_dir:
        custom_path = Path(temp_dir) / "index_custom.yaml"
        catalog = IndexCatalog.from_json(
            PROJECT_DIR / "resources" / "index_catalog.json",
            custom_path=custom_path,
        )
        runtime_config = {
            "BCU_NUM": 2,
            "LECU_NUM": 6,
            "CELL_NUM": 16,
            "Alarm_name_key": {"001": "单体电压过高"},
        }

        hall = catalog.resolve(818, runtime_config)
        _assert(hall.symbol == "VAR_HALL_CURR", "Hall index symbol mismatch")
        _assert(hall.signed and hall.scale == 0.1, "Hall index type or scale mismatch")
        _assert(hall.format_physical_value(0xFF85) == "-12.3 A", "Hall physical decode mismatch")
        shunt = catalog.resolve(819, runtime_config)
        _assert("分流器" in shunt.name, "shunt index description mismatch")
        precharge = catalog.resolve(0x90479, runtime_config)
        _assert(precharge.symbol == "PAR_SYS_PRECHARGE_MODE", "parameter index resolution mismatch")
        _assert(len(catalog.iter_entries(runtime_config)) > 4000, "runtime index catalog was not expanded")

        source_config = Path(temp_dir) / "factory_indexes.json"
        source_config.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "id": "0x332",
                            "name": "厂内霍尔电流",
                            "description": "覆盖固件目录中的显示名称与缩放。",
                            "signed": True,
                            "scale": 0.01,
                            "display_unit": "A",
                            "access": "read_only",
                        },
                        {
                            "id": "0x8FFFF",
                            "name": "厂内扩展状态",
                            "symbol": "CUSTOM_FACTORY_STATE",
                            "category": "custom",
                            "category_label": "自定义",
                            "value_map": {"0": "关闭", "1": "开启"},
                            "access": "read_only",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _assert(catalog.import_custom_config(source_config) == 2, "custom index import count mismatch")
        _assert(custom_path.exists(), "custom index config should persist beside the application")
        custom_hall = catalog.resolve(818, runtime_config)
        _assert(custom_hall.custom and custom_hall.name == "厂内霍尔电流", "custom override mismatch")
        _assert(custom_hall.format_physical_value(0xFF85) == "-1.23 A", "custom scaling mismatch")
        custom_state = catalog.resolve(0x8FFFF, runtime_config)
        _assert(custom_state.known and custom_state.custom, "new custom index was not resolved")
        _assert(custom_state.format_physical_value(1) == "开启", "custom value map mismatch")

        page = HostControlPage(catalog, runtime_config)
        try:
            page.show()
            page.index_edits[0].setText("0x332")
            page.index_edits[0].setFocus()
            page.set_request_value(0, 818, str(0xFF85))
            for _ in range(3):
                app.processEvents()
            _assert("厂内霍尔" in page.index_name_labels[0].text(), "index row name was not resolved")
            _assert("-1.23 A" in page.index_detail_value.text(), "index detail physical value mismatch")

            dialog = page.create_index_browser_dialog()
            try:
                dialog.search_edit.setText("厂内扩展状态")
                app.processEvents()
                _assert(dialog.proxy_model.rowCount() == 1, "custom browser search mismatch")
                _assert(dialog.clear_custom_button.isEnabled(), "custom clear action should be enabled")
                dialog.clear_custom_config()
                _assert(catalog.custom_count == 0, "custom index config should clear")
                _assert(catalog.resolve(818, runtime_config).name != "厂内霍尔电流", "base catalog should restore")
            finally:
                dialog.close()
        finally:
            page.close()
        template_path = Path(temp_dir) / "exported_template.yaml"
        catalog.export_custom_template(template_path)
        _assert(template_path.exists(), "custom template export failed")
    if created_app:
        app.quit()


def test_power_diagnostics():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from application.power_diagnostics import PowerDiagnosticAnalyzer
    from UI.T39 import PowerDiagnosticPage

    raw = {
        12: 2,
        23: 4,
        28: 0xA0,
        39: 0xFFFF,
        91: 6000,
        92: 5950,
        276: 0,
        280: 0,
        289: 0xAAAA,
        290: 0,
        296: 0,
        404: 1,
        617: 10,
        904: 1,
        0x83001: 0,
        0x83002: 0,
        0x83004: 0,
        0x90479: 50,
        0x9047A: 15,
        0x9047C: 2,
        0x9047D: 60,
    }
    for number in range(1, 11):
        raw[47 + number] = 0
        raw[57 + number] = 0

    analyzer = PowerDiagnosticAnalyzer(has_neutral=False)
    report = analyzer.analyze(raw)
    _assert(report["summary_status"] == "ok", "valid power-on conditions should pass")
    _assert(report["blocked_count"] == 0, "valid diagnostic should have no blocker")

    ignored_vms_requests = dict(raw)
    ignored_vms_requests.update({0x83001: 1, 0x83002: 0, 0x83004: 1})
    ignored_vms_report = analyzer.analyze(ignored_vms_requests)
    _assert(
        not any(item["category"] == "外部请求" for item in ignored_vms_report["conditions"]),
        "VMS request conditions should be hidden from power-on diagnostics",
    )
    _assert(
        ignored_vms_report["blocked_count"] == 0,
        "VMS request values should not block power-on diagnostics",
    )

    relay_low_side_fault = dict(raw)
    relay_low_side_fault[61] = 2
    relay_low_side_fault[67] = 2
    relay_feedback_report = analyzer.analyze(relay_low_side_fault)
    relay_self_test = next(
        item for item in relay_feedback_report["conditions"] if "粘连自检" in item["name"]
    )
    relay_feedback = next(
        item for item in relay_feedback_report["conditions"] if "反馈诊断" in item["name"]
    )
    _assert(relay_self_test["status"] == "ok", "low-side relay feedback must not fail stick self-test")
    _assert(relay_feedback["status"] == "warning", "relay feedback fault should be shown as evidence")
    _assert(
        "R4=0x0002(对地短路)" in relay_feedback["value"]
        and "R10=0x0002(对地短路)" in relay_feedback["value"],
        "relay feedback bit decoding mismatch",
    )
    _assert(relay_feedback_report["blocked_count"] == 0, "low-side feedback must not become a direct blocker")
    _assert(
        relay_feedback_report["summary_title"] == "具备条件，存在注意项",
        "ordinary relay feedback should not be described as a firmware bypass",
    )

    relay_stick_fault = dict(raw)
    relay_stick_fault[61] = 0x0100
    relay_stick_report = analyzer.analyze(relay_stick_fault)
    _assert(
        next(item for item in relay_stick_report["conditions"] if "粘连自检" in item["name"])["status"]
        == "blocked",
        "relay 1-8 stick feedback should fail firmware self-test",
    )

    current_fault = dict(raw)
    current_fault[290] = 3
    fault_report = analyzer.analyze(current_fault)
    _assert(fault_report["summary_status"] == "blocked", "current sensor fault should block")
    _assert("电流传感器" in fault_report["summary_title"], "primary blocker mismatch")

    precharge_fault = dict(raw)
    precharge_fault[92] = 4000
    precharge_report = analyzer.analyze(precharge_fault)
    _assert(
        any(item["category"] == "预充" and item["status"] == "blocked" for item in precharge_report["conditions"]),
        "precharge voltage mismatch should block",
    )

    abnormal_values = dict(raw)
    abnormal_values[276] = 0x08
    abnormal_event = analyzer.build_transition_event(4, 10, abnormal_values)
    _assert(abnormal_event["type"] == "异常下电", "cutoff transition should be abnormal")
    _assert("严重告警" in abnormal_event["cause"], "abnormal cause mismatch")
    requested_values = dict(raw)
    requested_values[0x83002] = 2
    requested_event = analyzer.build_transition_event(5, 2, requested_values)
    _assert(requested_event["type"] == "正常请求下电", "VMS open request should be normal")

    neutral_values = dict(raw)
    neutral_values.update({894: 0, 895: 0, 900: 3000, 901: 3000, 902: 2980, 903: 2980, 0x8301B: 0, 0x8301C: 0})
    neutral_report = PowerDiagnosticAnalyzer(has_neutral=True).analyze(neutral_values)
    _assert(
        len([item for item in neutral_report["conditions"] if item["category"] == "预充"]) == 2,
        "neutral mode should diagnose both half-clusters",
    )

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    page = PowerDiagnosticPage()
    try:
        page.set_cluster_context(1, "A0")
        page.update_report(fault_report, [abnormal_event])
        app.processEvents()
        _assert(page.conditions_table.rowCount() == len(fault_report["conditions"]), "diagnostic table mismatch")
        _assert(page.events_table.rowCount() == 1, "shutdown event table mismatch")
        _assert("无法上电" in page.summary_banner.text(), "diagnostic summary was not rendered")
    finally:
        page.close()
    if created_app:
        app.quit()


def test_alarm_parameter_transfer():
    from application.alarm_parameter_transfer import AlarmParameterTransfer

    transfer = AlarmParameterTransfer(0x94900, 47, response_timeout_s=0.1, max_retries=1)
    transfer.start_summary([0, 2])
    _assert(transfer.progress()["total"] == 20, "summary should request ten fields per alarm")
    actions = transfer.next_actions(now=1.0, burst=3, max_in_flight=12)
    _assert(len(actions) == 3, "summary scheduler burst mismatch")
    for action in actions:
        transfer.accept_read(action["data_id"], action["field_index"] + 100, success=True)
    _assert(transfer.progress()["completed"] == 3, "summary response progress mismatch")

    transfer.start_detail(1)
    while transfer.is_busy():
        actions = transfer.next_actions(now=2.0, burst=6, max_in_flight=12)
        _assert(actions, "detail scheduler stalled")
        for action in actions:
            transfer.accept_read(action["data_id"], action["field_index"], success=True)
    _assert(transfer.is_record_complete(1), "detail read should cache all 30 valid fields")

    transfer.start_write(1, {0: 321, 5: 45})
    write_actions = transfer.next_actions(now=3.0, burst=2, max_in_flight=4)
    _assert([action["kind"] for action in write_actions] == ["write", "write"], "write queue mismatch")
    for action in write_actions:
        transfer.accept_write(action["data_id"], success=True)
    _assert(transfer.phase == "verify", "successful writes should enter readback verification")
    verify_actions = transfer.next_actions(now=3.1, burst=2, max_in_flight=4)
    for action in verify_actions:
        transfer.accept_read(action["data_id"], transfer.expected[action["data_id"]], success=True)
    _assert(transfer.phase == "complete", "verified write should complete")
    _assert(not transfer.failures, "verified write should have no failures")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from UI.T28 import MainWindow as AlarmParameterPage

    created_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    page = AlarmParameterPage()
    try:
        page.select_alarm(0)
        page.update_alarm_row(0, [0] * 30)
        _assert(page.has_complete_current_record(), "full alarm record should enable editing")
        page.level_boxes[1].setValue(123)
        alarm_id, changed = page.build_changed_raw_fields()
        _assert(alarm_id == 0 and changed == {0: 123}, "write should include changed fields only")
    finally:
        page.close()
    if created_app:
        app.quit()


def test_cluster_overview_decoder():
    from application.cluster_overview import ClusterOverviewDecoder

    decoder = ClusterOverviewDecoder(False)
    payload = bytes((0x4C, 0x1D, 0x83, 0xFF, 5, 1, 0, 0))
    snapshot = decoder.decode_broadcast(0x1201EFA0, payload)
    _assert(snapshot["battery_voltage"] == 750.0, "703 B-terminal voltage decode mismatch")
    _assert(snapshot["system_current"] == -12.5, "703 signed current decode mismatch")
    _assert(snapshot["run_status"] == 5, "703 run-state decode mismatch")
    _assert(snapshot["insulation_finished"], "703 insulation-finished decode mismatch")

    snapshot.update(decoder.decode_broadcast(0x1202EFA0, bytes((0xD2, 0x04, 0x2E, 0x16, 1, 2, 0x52, 0x03))))
    _assert(snapshot["positive_insulation_resistance"] == 123.4, "positive insulation decode mismatch")
    _assert(snapshot["negative_insulation_resistance"] == 567.8, "negative insulation decode mismatch")
    _assert(snapshot["soc"] == 85.0, "703 SOC scale mismatch")

    extrema = decoder.decode_broadcast(0x1209EFA0, bytes((0xD0, 0x0C, 0xA4, 0x0C, 0x07, 0x03, 0x02, 0x05)))
    _assert(extrema["max_cell_voltage"] == 3280, "maximum cell voltage decode mismatch")
    _assert(extrema["max_cell_voltage_position"] == "模组3 / 点位7", "voltage position decode mismatch")
    _assert(
        decoder.decode_index(324, 0xFF85)["average_cell_temperature"] == -12.3,
        "signed indexed temperature decode mismatch",
    )

    neutral = ClusterOverviewDecoder(True)
    combined = {}
    combined.update(neutral.decode_broadcast(0x1201EFA0, bytes((0x10, 0x0E, 0x64, 0, 5, 6, 0x20, 0x0E))))
    combined.update(neutral.decode_broadcast(0x1301EFA0, bytes((0x08, 0x0E, 0xCE, 0xFF, 0x18, 0x1C, 0x10, 0x0E))))
    combined.update(neutral.decode_broadcast(0x1202EFA0, bytes((1, 0, 2, 0, 1, 0, 0x20, 0x03))))
    combined.update(neutral.decode_broadcast(0x1302EFA0, bytes((1, 0, 2, 0, 1, 0, 0x84, 0x03))))
    display = neutral.display_snapshot(combined)
    _assert(display["soc"] == 85.0, "neutral upper/lower SOC aggregation mismatch")
    _assert(display["allow_high_voltage"], "neutral high-voltage permission aggregation mismatch")
    _assert(display["hall_current"] == 10.0, "neutral Hall current decode mismatch")
    _assert(display["shunt_current"] == -5.0, "neutral shunt current decode mismatch")
    invalid = decoder.display_snapshot({"upper_alarm_level": 10753, "pack_voltage": 6551.9})
    _assert(invalid["alarm_level"] is None, "out-of-range alarm level should be rejected")
    _assert(invalid["pack_voltage"] is None, "out-of-range voltage sentinel should be rejected")
    _assert(not decoder.decode_broadcast(0x1201EFA0, b"\x00"), "short frame should be ignored")


def test_cluster_custom_monitor():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from application.cluster_view_config import (
        load_cluster_view_fields,
        save_cluster_view_fields,
    )
    from UI.T41 import ClusterCustomMonitorPage

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "cluster_view.yaml"
        fields = [
            {"data_id": 16, "label": "SOC", "enabled": True},
            {"data_id": 14, "label": "电流", "enabled": False},
        ]
        saved = save_cluster_view_fields(fields, config_path)
        _assert(load_cluster_view_fields(config_path) == saved, "cluster view config round trip failed")

        page = ClusterCustomMonitorPage(config_path=config_path)
        _assert(page.request_indexes() == (16,), "disabled custom index should not be requested")
        page.set_cluster_context(2, "A1")
        page.set_snapshot({16: 865, 14: 0xFF9C})
        _assert("86.5" in page.table.item(0, page.VALUE_COLUMN).text(), "custom SOC scaling mismatch")
        page.table.item(1, page.ENABLED_COLUMN).setCheckState(Qt.CheckState.Checked)
        _assert(page.request_indexes() == (16, 14), "enabled custom index was not added")
        page.update_raw_value(14, 0xFF9C)
        _assert("-10" in page.table.item(1, page.VALUE_COLUMN).text(), "custom signed decode mismatch")
        _assert(page.save_configuration(), "custom monitor configuration save failed")
        _assert(
            tuple(field["data_id"] for field in load_cluster_view_fields(config_path)) == (16, 14),
            "custom monitor order was not persisted",
        )
        page.deleteLater()
        app.processEvents()


def test_main_window_offscreen_logging():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication, QTableWidgetItem

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
        compiled_cluster = int(window.cluster_selector.currentData())
        compiled_address = int(window._cluster_address(compiled_cluster), 16)
        _assert(
            window._cluster_indices_for_frame_id(0x1881F200 | compiled_address) == (compiled_cluster,),
            "addressed CAN frame should route directly to one cluster",
        )

        window.show()
        current_page = window.tabWidget.currentWidget()
        window._defer_visible_page_repaint()
        _assert(current_page.updatesEnabled(), "receive batching must not disable the visible page")
        _assert(window._visible_page_repaint_pending, "receive batching should coalesce repaint requests")
        window._resume_page_updates(current_page)
        _assert(not window._visible_page_repaint_pending, "coalesced repaint should clear its pending state")
        _assert(current_page.updatesEnabled(), "coalesced repaint must keep the visible page enabled")
        for width, height in ((1024, 640), (1280, 720), (1366, 768), (1440, 900), (1920, 1080)):
            window.resize(width, height)
            for _ in range(3):
                app.processEvents()

            for command_layout, command_row in (
                (window.product_bus_layout, window.product_bus_row),
                (window.product_action_layout, window.product_action_row),
            ):
                visible_controls = []
                for item_index in range(command_layout.count()):
                    item = command_layout.itemAt(item_index)
                    widget = item.widget() if item is not None else None
                    if widget is not None and widget.isVisible():
                        visible_controls.append(widget)
                        _assert(
                            command_row.rect().contains(widget.geometry()),
                            f"header control escaped its command row at {width}x{height}",
                        )
                for left_index, left_widget in enumerate(visible_controls):
                    for right_widget in visible_controls[left_index + 1:]:
                        _assert(
                            not left_widget.geometry().intersects(right_widget.geometry()),
                            f"header controls overlap at {width}x{height}",
                        )
            _assert(
                not window.product_bus_row.geometry().intersects(window.product_action_row.geometry()),
                f"header command rows overlap at {width}x{height}",
            )

            window.tabWidget.setCurrentIndex(window.CLUSTER_TAB_INDEX)
            for _ in range(2):
                app.processEvents()
            _assert(window.cluster_view_tabs.count() == 3, "cluster page should expose three data views")
            window.cluster_view_tabs.setCurrentIndex(0)
            app.processEvents()
            _assert(
                window.cluster_section_splitters[window.CLUSTER_TAB_INDEX].isVisible(),
                "legacy cluster data tables should remain visible",
            )
            _assert(
                all(table.rowCount() >= 100 for table in window.TW[window.CLUSTER_TAB_INDEX]),
                "legacy cluster data rows were removed",
            )
            window.cluster_view_tabs.setCurrentIndex(1)
            app.processEvents()
            cluster_groups = [group for group in window.S33.groups if group.isVisible()]
            _assert(all(group.width() > 0 for group in cluster_groups), "cluster overview section collapsed")
            for left_index, left_group in enumerate(cluster_groups):
                for right_group in cluster_groups[left_index + 1:]:
                    _assert(
                        not left_group.geometry().intersects(right_group.geometry()),
                        f"cluster overview sections overlap at {width}x{height}",
                    )
            window.cluster_view_tabs.setCurrentIndex(2)
            app.processEvents()
            _assert(
                window.cluster_custom_page.table.isVisible(),
                "custom indexed monitor should be visible",
            )

            window.tabWidget.setCurrentIndex(window._realtime_monitor_tab_index())
            for _ in range(3):
                app.processEvents()
            viewport_width = window.S27.content_scroll.viewport().width()
            expected_columns = 3 if viewport_width >= 1680 else 2 if viewport_width >= 1120 else 1
            _assert(
                window.S27.layout_column_count == expected_columns,
                f"realtime monitor responsive columns mismatch at {width}x{height}",
            )
            _assert(window.S17.body_scroll.widgetResizable(), "host control page should remain scrollable")
        window.hide()

        original_log_interval = main_module.config.get(
            main_module.LOG_INTERVAL_CONFIG_KEY,
            main_module.LOG_INTERVAL_DEFAULT_MS,
        )
        try:
            main_module.config[main_module.LOG_INTERVAL_CONFIG_KEY] = 2500
            _assert(window._log_save_interval_ms() == 2500, "log interval helper should read runtime config")
            window.timerResData.start(1000)
            window._apply_log_save_interval()
            _assert(window.timerResData.interval() == 2500, "log timer should apply configured interval")
            window.timerResData.stop()
        finally:
            main_module.config[main_module.LOG_INTERVAL_CONFIG_KEY] = original_log_interval

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

        original_active_cluster = window._active_cluster_index()
        window._set_active_cluster(1, refresh=False, source="self_test")
        original_cluster_has_n = main_module.config.get("Has_N", 0)
        try:
            window._set_has_neutral(0, persist=False, refresh=True)
            window.cluster_overview_snapshots[1] = {}
            window._handle_cluster_overview_broadcast(
                1,
                0x1201EFA0,
                bytes((0x4C, 0x1D, 0x83, 0xFF, 5, 1, 0, 0)),
            )
            _assert(
                window.cluster_overview_snapshots[1]["system_current"] == -12.5,
                "main window should route 703 broadcast data into the selected cluster cache",
            )
            window._cache_cluster_overview_index_value(1, main_module.VAR_SYS_SOC, 864)
            _assert(
                window.cluster_overview_snapshots[1]["soc"] == 86.4,
                "cluster overview should merge indexed foreground data into its broadcast cache",
            )
            shared_ids = set(main_module.SYSTEM_KLINE_SHARED_SIGNAL_IDS)
            queue_ids = set(window.cluster_page_signal_ids)
            _assert(
                set(window.BCUSignalQ) - shared_ids <= queue_ids,
                "cluster page should retain the legacy full-data index queue",
            )
            _assert(
                set(main_module.CLUSTER_OVERVIEW_INDEX_IDS) - shared_ids <= queue_ids,
                "cluster page should retain the 703 overview indexes",
            )
            _assert(
                set(window.cluster_custom_page.request_indexes()) - shared_ids <= queue_ids,
                "cluster page should include enabled custom indexes",
            )
            window._handle_index_var_response(1, main_module.VAR_SYS_SOC, 777, True)
            _assert(
                window.cluster_custom_raw_words[1][main_module.VAR_SYS_SOC] == 777,
                "custom indexed data should be cached per cluster",
            )
        finally:
            window._set_has_neutral(original_cluster_has_n, persist=False, refresh=True)
        original_c = getattr(window, "c", None)
        original_can_ready = getattr(window, "can_ready", False)
        original_table_index = getattr(window, "table_index", 0)
        original_signal_ids = tuple(window.realtime_monitor_signal_ids)
        original_query_index = window.realtime_monitor_query_index
        original_kline_query_index = window.system_kline_query_index
        original_kline_request_time = window.system_kline_last_request_monotonic
        original_diagnostic_query_index = window.power_diagnostic_query_index
        original_diagnostic_request_time = window.power_diagnostic_last_request_monotonic
        original_query_data = window.QueryData
        try:
            window.c = SimpleNamespace()
            window.can_ready = True
            window.can_connected_monotonic = time.monotonic()
            window.last_can_rx_monotonic = time.monotonic()
            window.table_index = window._realtime_monitor_tab_index()
            window.realtime_monitor_signal_ids = (101, 102, 103, 104)
            window.realtime_monitor_query_index = 0
            window.system_kline_last_request_monotonic = time.monotonic()
            window.power_diagnostic_last_request_monotonic = time.monotonic()
            sent_monitor_queries = []
            window.QueryData = lambda cluster_index, data: sent_monitor_queries.append((cluster_index, list(data)))
            window._start_can_timers()
            _assert(window.timerRealtimeMonitor.isActive(), "realtime UI timer should restart with CAN")
            _assert(window.timerActiveAlarm.isActive(), "active alarm UI timer should restart with CAN")
            _assert(window.timerPowerDiagnostic.isActive(), "diagnostic UI timer should restart with CAN")
            _assert(
                window.timer1.interval() == main_module.CAN_REQUEST_FOREGROUND_INTERVAL_MS,
                "visible request-driven page should use the foreground request interval",
            )
            _assert(
                window.send_time.interval() == main_module.CAN_RX_FOREGROUND_INTERVAL_MS,
                "visible data page should use the foreground receive interval",
            )
            window._stop_can_timers()

            window.RequestBCUVAR()
            _assert(
                len(sent_monitor_queries) == main_module.CAN_REQUEST_FOREGROUND_BURST_PER_TICK,
                "realtime monitor request should batch multiple indexes per tick",
            )
            _assert(
                window.realtime_monitor_query_index
                == main_module.CAN_REQUEST_FOREGROUND_BURST_PER_TICK % len(window.realtime_monitor_signal_ids),
                "realtime monitor query cursor should advance by request burst",
            )
            window.table_index = window._balance_control_tab_index()
            window._apply_page_refresh_profile()
            window.system_kline_last_request_monotonic = time.monotonic()
            window.power_diagnostic_last_critical_request_monotonic = time.monotonic()
            window.power_diagnostic_last_static_request_monotonic = time.monotonic()
            sent_monitor_queries.clear()
            window.RequestBCUVAR()
            _assert(
                len(sent_monitor_queries) == 2,
                "visible balance-control page should continuously request both balance words",
            )
            window.table_index = window._history_log_tab_index()
            window._apply_page_refresh_profile()
            _assert(
                window.timer1.interval() == main_module.CAN_REQUEST_NORMAL_INTERVAL_MS,
                "background page should release the foreground request interval",
            )
            _assert(
                window.send_time.interval() == main_module.CAN_RX_POLL_INTERVAL_MS,
                "background page should release the foreground receive interval",
            )
            window.system_kline_query_index = 0
            window.system_kline_last_request_monotonic = 0.0
            sent_monitor_queries.clear()
            window.RequestBCUVAR()
            window.system_kline_last_request_monotonic = 0.0
            window.RequestBCUVAR()
            window.system_kline_last_request_monotonic = 0.0
            window.RequestBCUVAR()
            requested_ids = [
                sum(query[1][offset] << (8 * offset) for offset in range(4))
                for query in sent_monitor_queries
            ]
            requested_kline_ids = [
                data_id for data_id in requested_ids if data_id in main_module.SYSTEM_KLINE_SHARED_SIGNAL_IDS
            ]
            _assert(
                requested_kline_ids
                == [main_module.VAR_SYS_VOLT, main_module.VAR_HALL_CURR, main_module.VAR_SHUNT_CURR],
                "background polling should cache voltage and both current sensors outside the K-line page",
            )
            _assert(
                not set(main_module.SYSTEM_KLINE_SHARED_SIGNAL_IDS).intersection(
                    main_module.REALTIME_MONITOR_SIGNAL_IDS
                ),
                "realtime page queue should not duplicate shared trend requests",
            )
            _assert(
                not set(main_module.SYSTEM_KLINE_SHARED_SIGNAL_IDS).intersection(
                    window.cluster_page_signal_ids
                ),
                "cluster page queue should not duplicate shared trend requests",
            )
            sent_monitor_queries.clear()
            window.power_diagnostic_query_index = 9
            window.on_tab_changed(window._power_diagnostic_tab_index())
            _assert(len(sent_monitor_queries) == 1, "entering diagnostic page should request immediately")
            entered_diagnostic_id = sum(
                sent_monitor_queries[0][1][offset] << (8 * offset) for offset in range(4)
            )
            _assert(
                entered_diagnostic_id == main_module.VAR_SYS_RUN_STATUS,
                "diagnostic page entry should restart from the run-state index",
            )
            sent_monitor_queries.clear()
            window.power_diagnostic_query_index = 0
            window._request_power_diagnostic_background(force=True)
            _assert(len(sent_monitor_queries) == 1, "diagnostic background poll should be non-blocking")
            requested_diagnostic_id = sum(
                sent_monitor_queries[0][1][offset] << (8 * offset) for offset in range(4)
            )
            _assert(
                requested_diagnostic_id == main_module.VAR_SYS_RUN_STATUS,
                "diagnostic poll should prioritize the run-state index",
            )
        finally:
            window.QueryData = original_query_data
            window.realtime_monitor_signal_ids = original_signal_ids
            window.realtime_monitor_query_index = original_query_index
            window.system_kline_query_index = original_kline_query_index
            window.system_kline_last_request_monotonic = original_kline_request_time
            window.power_diagnostic_query_index = original_diagnostic_query_index
            window.power_diagnostic_last_request_monotonic = original_diagnostic_request_time
            window.table_index = original_table_index
            window.can_ready = original_can_ready
            window.c = original_c
            window._set_active_cluster(original_active_cluster, refresh=False, source="self_test")

        window._start_power_alarm_flash()
        app.processEvents()
        _assert(not window.power_alarm_overlay.isHidden(), "power alarm should cover the full window")
        _assert(window.power_alarm_flash_timer.isActive(), "power alarm flash timer should run")
        _assert(window.power_alarm_overlay.geometry() == window.rect(), "power alarm overlay geometry mismatch")
        window.power_alarm_flash_timer.stop()
        window.power_alarm_overlay.hide()

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
            current_key = window._runtime_log_key(1)
            current_kline_count = window.S31.sample_count(1, "hall_current")
            window._handle_index_var_response(1, main_module.VAR_HALL_CURR, main_module.to_unsigned_16bit(-125), True)
            _assert(window.ResDataRec[1][current_key] == "-12.5", "index runtime Hall current decode mismatch")
            _assert(
                window.S31.sample_count(1, "hall_current") == current_kline_count + 1,
                "successful Hall response should append a K-line sample",
            )
            window._handle_index_var_response(1, main_module.VAR_HALL_CURR, 100, False)
            _assert(window.ResDataRec[1][current_key] == "-12.5", "failed index response should not overwrite runtime data")
            _assert(
                window.S31.sample_count(1, "hall_current") == current_kline_count + 1,
                "failed Hall response should not append a K-line sample",
            )
            shunt_key = window._runtime_log_key(14)
            shunt_kline_count = window.S31.sample_count(1, "shunt_current")
            window._handle_index_var_response(
                1,
                main_module.VAR_SHUNT_CURR,
                main_module.to_unsigned_16bit(-78),
                True,
            )
            _assert(window.ResDataRec[1][shunt_key] == "-7.8", "index runtime shunt decode mismatch")
            _assert(
                window.S31.sample_count(1, "shunt_current") == shunt_kline_count + 1,
                "successful shunt response should append a K-line sample",
            )
            cluster2_table_index = window._shadow_cluster_tab_index(2)
            window.TW[cluster2_table_index][0].setItem(4, 1, QTableWidgetItem("99"))

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

            window._cluster_snapshot_store("cluster_voltage_snapshots")[2] = [4300 + index for index in range(cell_count)]
            window._cluster_snapshot_store("cluster_temperature_snapshots")[2] = [350 + index for index in range(temp_count)]
            window._cluster_snapshot_store("cluster_balance_snapshots")[2] = [1 for _ in range(cell_count)]
            window._cluster_snapshot_store("cluster_abnormal_snapshots")[2] = [2 for _ in range(cell_count)]
            for kind in ("voltage", "temperature", "balance", "abnormal"):
                window._mark_cluster_snapshot_dirty(kind, 2)

            window.log_scope_selector.setCurrentIndex(window.log_scope_selector.findData("all"))
            sent_log_queries = []
            original_query_data = window.QueryData
            original_log_request_time = window.log_last_request_monotonic
            try:
                window.QueryData = lambda cluster_index, data: sent_log_queries.append((cluster_index, list(data)))
                window.BCUSignalQ = [0x1234]
                window.log_poll_cluster_cursor = 0
                window.log_poll_signal_index = 0
                window.log_last_request_monotonic = 0.0
                window._request_all_cluster_log_runtime_data()
                window.log_last_request_monotonic = 0.0
                window._request_all_cluster_log_runtime_data()
            finally:
                window.QueryData = original_query_data
                window.log_last_request_monotonic = original_log_request_time
            _assert([cluster_index for cluster_index, _data in sent_log_queries] == [1, 2], "all-scope log polling should cycle clusters")
            window.SaveRunData()

            tab_names = [
                window.tabWidget.tabText(index)
                for index in range(window.tabWidget.count())
            ]
            _assert("实时告警" in tab_names, "active alarm tab is missing")
            _assert("实时监控" in tab_names, "realtime monitor tab is missing")
            _assert("DBC解析" in tab_names, "DBC parser tab is missing")
            _assert("单体3D" in tab_names, "cell 3D tab is missing")
            _assert("总压电流K线" in tab_names, "system voltage/current K-line tab is missing")
            active_cluster = window._active_cluster_index()
            visualization_voltages = [3310 + (index % 7) for index in range(cell_count)]
            visualization_temperatures = [245 + (index % 11) for index in range(temp_count)]
            window._cluster_snapshot_store("cluster_voltage_snapshots")[active_cluster] = visualization_voltages
            window._cluster_snapshot_store("cluster_temperature_snapshots")[active_cluster] = visualization_temperatures
            window.tabWidget.setCurrentIndex(window._cell_visualization_tab_index())
            _assert(
                window.S30.voltage_panel.summary["count"] == cell_count,
                "cell visualization should load current cluster voltage cache",
            )
            _assert(
                window.S30.temperature_panel.summary["count"] == temp_count,
                "cell visualization should load current cluster temperature cache",
            )
            window._set_active_cluster(0, refresh=True, source="self_test")
            _assert(window.S30.voltage_panel.summary["count"] == 0, "00 cluster should clear voltage heatmap")
            _assert(window.S30.temperature_panel.summary["count"] == 0, "00 cluster should clear temperature heatmap")
            window._set_active_cluster(active_cluster, refresh=True, source="self_test")
            voltage_kline_count = window.S31.sample_count(active_cluster, "voltage")
            window._handle_index_var_response(active_cluster, main_module.VAR_SYS_VOLT, 6110, True)
            _assert(
                window.S31.sample_count(active_cluster, "voltage") == voltage_kline_count + 1,
                "system voltage response should append a K-line sample",
            )
            _assert(
                window.S31.bars_for(active_cluster, "voltage")[-1].latest == 611.0,
                "system voltage K-line scaling mismatch",
            )
            hall_kline_count = window.S31.sample_count(active_cluster, "hall_current")
            window._handle_index_var_response(
                active_cluster,
                main_module.VAR_HALL_CURR,
                main_module.to_unsigned_16bit(-123),
                True,
            )
            _assert(
                window.S31.sample_count(active_cluster, "hall_current") == hall_kline_count + 1,
                "Hall current response should append an isolated K-line sample",
            )
            _assert(
                window.S31.bars_for(active_cluster, "hall_current")[-1].latest == -12.3,
                "Hall current K-line scaling mismatch",
            )
            shunt_kline_count = window.S31.sample_count(active_cluster, "shunt_current")
            window._handle_index_var_response(
                active_cluster,
                main_module.VAR_SHUNT_CURR,
                main_module.to_unsigned_16bit(456),
                True,
            )
            _assert(
                window.S31.sample_count(active_cluster, "shunt_current") == shunt_kline_count + 1,
                "shunt current response should append an isolated K-line sample",
            )
            _assert(
                window.S31.bars_for(active_cluster, "shunt_current")[-1].latest == 45.6,
                "shunt current K-line scaling mismatch",
            )
            window._handle_index_var_response(2, main_module.VAR_SYS_VOLT, 7200, True)
            _assert(
                window.S31.bars_for(2, "voltage")[-1].latest == 720.0,
                "secondary cluster K-line scaling mismatch",
            )
            _assert(
                window.S31.bars_for(active_cluster, "voltage")[-1].latest == 611.0,
                "secondary cluster K-line data should not leak into the active cluster",
            )
            window.tabWidget.setCurrentIndex(window._system_kline_tab_index())
            window.S31.refresh_active_chart(force=True)
            _assert(window.S31.panels["voltage"].canvas.bars, "K-line tab should render current cluster history")
            _assert(window.S29.database is not None, "DBC parser page should load default IDC.dbc")
            _assert(window.S29.database.signal_count >= 90, "DBC parser page should expose default DBC signals")
            window.S29.clear_live_values()
            for timestamp in range(50):
                window._handle_dbc_received_frame(
                    0x1204EFA0,
                    bytes([0xE8, 0x03, 0xD0, 0x07, 0xB8, 0x0B, 0xA0, 0x0F]),
                    timestamp=timestamp + 1,
                )
            _assert(window.S29.live_matched_count == 50, "DBC live decode should match received frames")
            _assert(
                window.S29.live_table.rowCount() == 0,
                "hidden DBC page should defer table updates",
            )
            _assert(
                0 < len(window.S29.live_pending_updates) < 20,
                "DBC pending updates should retain only the latest value per signal",
            )
            window.S29.flush_live_updates()
            live_values = {}
            for row in range(window.S29.live_table.rowCount()):
                signal_name = window.S29.live_table.item(row, 3).text()
                physical_value = window.S29.live_table.item(row, 5).text()
                live_values[signal_name] = physical_value
            _assert(live_values.get("Chargeable_battery_KWH_UP") == "10", "DBC live table value mismatch")
            _assert(window.S28.auto_refresh_checkbox.isChecked(), "active alarm auto refresh should be enabled by default")
            _assert(not window.send_time1.isActive(), "alarm parameter poll timer should stay stopped by default")
            window.can_ready = True
            window.can_connected_monotonic = time.monotonic() - main_module.CAN_LOWER_SILENCE_TIMEOUT_S - 1
            window.last_can_rx_monotonic = 0
            window.timer1.setInterval(main_module.CAN_REQUEST_NORMAL_INTERVAL_MS)
            window._update_can_link_health()
            _assert(window.can_link_silent is True, "silent CAN link should enter degraded mode")
            _assert(
                window.timer1.interval() == main_module.CAN_REQUEST_SILENT_INTERVAL_MS,
                "silent CAN link should slow request polling",
            )
            refresh_calls = []
            original_refresh_active_alarm = window.refresh_active_alarm_page
            try:
                window.table_index = window._active_alarm_tab_index()
                window.refresh_active_alarm_page = lambda show_dialog=False: refresh_calls.append(show_dialog)
                window._refresh_active_alarm_page_if_visible(force=True)
            finally:
                window.refresh_active_alarm_page = original_refresh_active_alarm
            _assert(not refresh_calls, "active alarm auto refresh should skip blocking reads while CAN is silent")
            window._record_rx_frames(1)
            _assert(window.can_link_silent is False, "CAN RX should restore normal link mode")
            _assert(
                window.timer1.interval() == main_module.CAN_REQUEST_NORMAL_INTERVAL_MS,
                "CAN RX should restore normal request polling",
            )
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
            all_scope_voltage_files = list(log_dir.rglob("*voltage_A1.csv"))
            all_scope_temperature_files = list(log_dir.rglob("*temperature_A1.csv"))
            all_scope_balance_files = list(log_dir.rglob("*balance_A1.csv"))
            all_scope_abnormal_files = list(log_dir.rglob("*abnormal_A1.csv"))

            _assert(runtime_files, "runtime CSV was not created")
            _assert(all_scope_runtime_files, "all-scope runtime CSV was not created")
            _assert(voltage_files, "voltage CSV was not created")
            _assert(temperature_files, "temperature CSV was not created")
            _assert(balance_files, "balance CSV was not created")
            _assert(abnormal_files, "abnormal CSV was not created")
            _assert(all_scope_voltage_files, "all-scope voltage CSV was not created")
            _assert(all_scope_temperature_files, "all-scope temperature CSV was not created")
            _assert(all_scope_balance_files, "all-scope balance CSV was not created")
            _assert(all_scope_abnormal_files, "all-scope abnormal CSV was not created")

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
            all_scope_voltage_rows = _read_csv(all_scope_voltage_files[0])
            all_scope_temperature_rows = _read_csv(all_scope_temperature_files[0])
            all_scope_balance_rows = _read_csv(all_scope_balance_files[0])
            all_scope_abnormal_rows = _read_csv(all_scope_abnormal_files[0])
            _assert(all_scope_voltage_rows[1][1] == "4300", "all-scope voltage snapshot mismatch")
            _assert(all_scope_temperature_rows[1][1] == "350", "all-scope temperature snapshot mismatch")
            _assert(all_scope_balance_rows[1][1] == "1", "all-scope balance snapshot mismatch")
            _assert(all_scope_abnormal_rows[1][1] == "2", "all-scope abnormal snapshot mismatch")
    finally:
        window.close()
        if QApplication.instance() is app:
            app.quit()


def main():
    tests = [
        test_configuration_round_trip,
        test_trend_data_store,
        test_session_logger_files,
        test_module_cell_grid_module_extrema,
        test_cell_visualization_page,
        test_system_kline_page,
        test_dbc_parser,
        test_index_catalog_and_browser,
        test_power_diagnostics,
        test_alarm_parameter_transfer,
        test_cluster_overview_decoder,
        test_cluster_custom_monitor,
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
