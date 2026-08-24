"""Capture the real Qt dashboard with deterministic maintenance test data."""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANFD_ROOT = REPOSITORY_ROOT / "CANFD"
TEST_ROOT = CANFD_ROOT / "tests"
for import_root in (CANFD_ROOT, TEST_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from application.dashboard_service import (
    ClusterDashboardView,
    ClusterHealth,
    FleetDashboardView,
)
from data_center.models import DataQuality
from presentation.main_window import MainWindow
from test_main_window import FakeService


REFERENCE_WIDTH = 1487
REFERENCE_HEIGHT = 1058


def build_visual_comparison(
    reference_path: Path,
    implementation_path: Path,
    output_path: Path,
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    reference = Image.open(reference_path).convert("RGB")
    implementation = Image.open(implementation_path).convert("RGB")
    if reference.size != implementation.size:
        raise ValueError(
            "Reference and implementation must use the same viewport: "
            f"{reference.size} != {implementation.size}"
        )

    label_height = 34
    comparison = Image.new(
        "RGB",
        (
            reference.width,
            reference.height + implementation.height + label_height * 2,
        ),
        "white",
    )
    comparison.paste(reference, (0, label_height))
    implementation_top = reference.height + label_height * 2
    comparison.paste(implementation, (0, implementation_top))
    draw = ImageDraw.Draw(comparison)
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    font = (
        ImageFont.truetype(str(font_path), 18)
        if font_path.is_file()
        else ImageFont.load_default()
    )
    draw.rectangle((0, 0, reference.width, label_height), fill="#e8eef8")
    draw.text((12, 6), "REFERENCE", fill="#172033", font=font)
    second_label_top = reference.height + label_height
    draw.rectangle(
        (0, second_label_top, reference.width, implementation_top),
        fill="#e8eef8",
    )
    draw.text(
        (12, second_label_top + 6),
        "IMPLEMENTATION",
        fill="#172033",
        font=font,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison.save(output_path)


def build_preview_dashboard() -> FleetDashboardView:
    generated_at = datetime(2026, 8, 21, 10, 24, 36)
    addresses = ["00"] + [f"A{offset:X}" for offset in range(15)]
    soc_values = [88, 74, 92, 68, 81, 0, 78, 76, 65, 72, 69, 86, 90, 84, 73, 77]
    voltage_values = [
        798.2,
        790.5,
        801.1,
        764.3,
        793.7,
        None,
        787.1,
        782.4,
        759.8,
        775.2,
        768.9,
        795.4,
        799.1,
        792.6,
        780.7,
        784.5,
    ]
    current_values = [
        -12.4,
        -14.8,
        -11.9,
        -16.7,
        -13.2,
        None,
        -14.1,
        -15.4,
        -18.2,
        -15.9,
        -17.1,
        -12.8,
        -11.7,
        -13.6,
        -15.6,
        -14.9,
    ]
    voltage_differences = [86, 76, 64, 118, 180, None, 72, 91, 166, 83, 98, 61, 58, 69, 105, 88]
    temperature_differences = [5.6, 4.6, 2.3, 5.1, 7.2, None, 3.4, 4.8, 6.8, 4.2, 5.0, 2.7, 2.1, 3.2, 5.4, 4.5]
    maximum_temperatures = [36.8, 52.3, 35.2, 48.6, 61.5, None, 38.7, 45.9, 59.1, 43.7, 50.4, 37.2, 34.8, 39.1, 51.7, 46.2]
    maximum_cell_voltages = [3458, 3476, 3442, 3481, 3512, None, 3463, 3491, 3506, 3478, 3489, 3448, 3439, 3467, 3498, 3472]
    minimum_cell_voltages = [3372, 3400, 3378, 3363, 3332, None, 3391, 3400, 3340, 3395, 3391, 3387, 3381, 3398, 3393, 3384]

    health_by_index = {
        1: ClusterHealth.WARNING,
        4: ClusterHealth.ALARM,
        5: ClusterHealth.OFFLINE,
        7: ClusterHealth.WARNING,
        8: ClusterHealth.ALARM,
        10: ClusterHealth.WARNING,
        14: ClusterHealth.WARNING,
    }
    alarms_by_index = {
        4: ("单体压差二级告警", "最高温度二级告警"),
        8: ("系统压差二级告警",),
        1: ("最高温度预警",),
        7: ("系统温差预警",),
        10: ("系统压差预警",),
        14: ("系统温差预警",),
    }
    clusters = []
    for cluster_index, address in enumerate(addresses):
        health = health_by_index.get(cluster_index, ClusterHealth.NORMAL)
        quality = (
            DataQuality.OFFLINE
            if health == ClusterHealth.OFFLINE
            else DataQuality.GOOD
        )
        alarms = alarms_by_index.get(cluster_index, ())
        clusters.append(
            ClusterDashboardView(
                cluster_index=cluster_index,
                address=address,
                communication_quality=quality,
                health=health,
                run_status=None if quality == DataQuality.OFFLINE else 5,
                run_status_text="--" if quality == DataQuality.OFFLINE else "放电",
                soc=None if quality == DataQuality.OFFLINE else soc_values[cluster_index],
                system_voltage=voltage_values[cluster_index],
                system_current=current_values[cluster_index],
                voltage_difference=voltage_differences[cluster_index],
                maximum_cell_voltage=maximum_cell_voltages[cluster_index],
                minimum_cell_voltage=minimum_cell_voltages[cluster_index],
                maximum_temperature=maximum_temperatures[cluster_index],
                temperature_difference=temperature_differences[cluster_index],
                alarm_count=len(alarms),
                alarm_names=alarms,
                last_update=(
                    None
                    if quality == DataQuality.OFFLINE
                    else generated_at - timedelta(milliseconds=cluster_index * 37)
                ),
            )
        )

    return FleetDashboardView(
        clusters=tuple(clusters),
        total_count=len(clusters),
        online_count=sum(cluster.communication_quality == DataQuality.GOOD for cluster in clusters),
        normal_count=sum(cluster.health == ClusterHealth.NORMAL for cluster in clusters),
        warning_count=sum(cluster.health == ClusterHealth.WARNING for cluster in clusters),
        alarm_count=sum(cluster.health == ClusterHealth.ALARM for cluster in clusters),
        offline_count=sum(cluster.health == ClusterHealth.OFFLINE for cluster in clusters),
        generated_at=generated_at,
    )


def capture(output_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    yahei_font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    if yahei_font_path.is_file():
        QFontDatabase.addApplicationFont(str(yahei_font_path))
        app.setFont(QFont("Microsoft YaHei UI", 9))
    dashboard = build_preview_dashboard()
    service = FakeService()
    service.cluster_indices = [cluster.cluster_index for cluster in dashboard.clusters]
    service.cluster_addresses = [cluster.address for cluster in dashboard.clusters]
    runtime_config = dict(service.runtime_config)
    runtime_config.update(
        {
            "BCU_NUM": sum(
                cluster.address != "00"
                for cluster in dashboard.clusters
            ),
            "ADDRESLIST": list(service.cluster_addresses),
            "SAVE_INTERVAL_MS": 1000,
        }
    )

    window = MainWindow(service, runtime_config)
    window.resize(REFERENCE_WIDTH, REFERENCE_HEIGHT)
    window.show()
    window.tabWidget.setCurrentIndex(window.CLUSTER_DASHBOARD_TAB_INDEX)
    window.cluster_dashboard_page.update_dashboard(dashboard)
    for timer in (
        window.poll_timer,
        window.query_timer,
        window.save_timer,
        window.index_read_timer,
    ):
        timer.stop()
    app.processEvents()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output_path), "PNG"):
        raise RuntimeError(f"Unable to save dashboard screenshot: {output_path}")
    window.close()
    app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "docs" / "screenshots" / "cluster_dashboard_implementation.png",
    )
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=REPOSITORY_ROOT
        / "docs"
        / "screenshots"
        / "cluster_dashboard_comparison.png",
    )
    args = parser.parse_args()
    implementation_path = args.output.resolve()
    capture(implementation_path)
    print(implementation_path)
    if args.reference is not None:
        comparison_path = args.comparison_output.resolve()
        build_visual_comparison(
            args.reference.resolve(),
            implementation_path,
            comparison_path,
        )
        print(comparison_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
