import math
import time

import numpy as np
from matplotlib import cm, colors, rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .conf import config


rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


BAR_COLORMAP = colors.LinearSegmentedColormap.from_list(
    "aidc_cell_value",
    ("#3547a8", "#79add2", "#d9f0e3", "#fee08b", "#f46d43", "#a50026"),
)


def _normalized_values(values, expected_count, scale, zero_is_missing):
    result = []
    normalized = list(values or [])[:expected_count]
    normalized += [None] * max(0, expected_count - len(normalized))
    for index, value in enumerate(normalized):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        if zero_is_missing and numeric == 0:
            continue
        result.append((index, numeric / float(scale)))
    if result and not any(value != 0 for _index, value in result):
        return []
    return result


class Bar3DCanvas(FigureCanvasQTAgg):
    def __init__(
        self,
        module_count,
        cells_per_module,
        value_name,
        unit,
        scale=1.0,
        precision=0,
        zero_is_missing=False,
        parent=None,
    ):
        self.figure = Figure(figsize=(10, 6), dpi=100, facecolor="#ffffff")
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.module_count = max(1, int(module_count))
        self.cells_per_module = max(1, int(cells_per_module))
        self.value_name = str(value_name)
        self.unit = str(unit)
        self.scale = float(scale)
        self.precision = int(precision)
        self.zero_is_missing = bool(zero_is_missing)
        self.entries = []
        self.axes = None
        self.annotation = None
        self.elevation = 24
        self.azimuth = -62
        self.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.mpl_connect("button_release_event", self._remember_view)
        self.draw_values([])

    def draw_values(self, values):
        expected_count = self.module_count * self.cells_per_module
        self.entries = _normalized_values(values, expected_count, self.scale, self.zero_is_missing)
        self.figure.clear()
        self.axes = self.figure.add_subplot(111, projection="3d")
        self.axes.set_facecolor("#ffffff")
        self.figure.subplots_adjust(left=0.01, right=0.93, bottom=0.08, top=0.95)

        if not self.entries:
            self._configure_axes(0.0, 1.0)
            self.axes.text2D(
                0.5,
                0.5,
                "等待当前簇单体数据",
                transform=self.axes.transAxes,
                ha="center",
                va="center",
                color="#7b8797",
                fontsize=13,
            )
            self.annotation = None
            self.draw()
            return

        indexes = np.asarray([index for index, _value in self.entries], dtype=int)
        display_values = np.asarray([value for _index, value in self.entries], dtype=float)
        module_indexes = indexes // self.cells_per_module
        cell_indexes = indexes % self.cells_per_module

        minimum = float(display_values.min())
        maximum = float(display_values.max())
        span = maximum - minimum
        baseline_margin = max(span * 0.18, 5.0 if self.unit == "mV" else 1.0)
        baseline = math.floor((minimum - baseline_margin) * 10.0) / 10.0
        heights = np.maximum(display_values - baseline, 0.001)

        normalizer = colors.Normalize(vmin=minimum, vmax=maximum if maximum != minimum else minimum + 1.0)
        bar_colors = BAR_COLORMAP(normalizer(display_values))
        self.axes.bar3d(
            cell_indexes + 0.1,
            module_indexes + 0.1,
            np.full(len(display_values), baseline),
            np.full(len(display_values), 0.76),
            np.full(len(display_values), 0.76),
            heights,
            color=bar_colors,
            edgecolor="#ffffff",
            linewidth=0.35,
            shade=True,
            zsort="average",
        )

        upper_margin = max(span * 0.16, 4.0 if self.unit == "mV" else 1.0)
        self._configure_axes(baseline, maximum + upper_margin)
        colorbar = self.figure.colorbar(
            cm.ScalarMappable(norm=normalizer, cmap=BAR_COLORMAP),
            ax=self.axes,
            shrink=0.63,
            pad=0.03,
            aspect=22,
            location="left",
        )
        colorbar.set_label(f"{self.value_name} ({self.unit})", color="#526173", labelpad=8)
        colorbar.ax.tick_params(labelsize=8, colors="#526173")

        self.annotation = self.axes.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.45", "fc": "white", "ec": "#1f66e5", "alpha": 0.96},
            color="#172033",
            fontsize=9,
            visible=False,
        )
        self.draw()

    def _configure_axes(self, z_minimum, z_maximum):
        axes = self.axes
        axes.set_xlim(0, self.cells_per_module)
        axes.set_ylim(0, self.module_count)
        axes.set_zlim(z_minimum, max(z_maximum, z_minimum + 1.0))
        axes.set_xlabel("单体编号", labelpad=9, color="#344256")
        axes.set_ylabel("模组", labelpad=9, color="#344256")
        axes.set_zlabel(f"{self.value_name} ({self.unit})", labelpad=8, color="#344256")

        x_step = 1 if self.cells_per_module <= 16 else max(1, math.ceil(self.cells_per_module / 16))
        x_ticks = np.arange(0, self.cells_per_module, x_step) + 0.5
        axes.set_xticks(x_ticks)
        axes.set_xticklabels([str(index + 1) for index in range(0, self.cells_per_module, x_step)])
        axes.set_yticks(np.arange(self.module_count) + 0.5)
        axes.set_yticklabels([f"M{index + 1}" for index in range(self.module_count)])
        axes.tick_params(axis="x", labelsize=8, colors="#526173", pad=1)
        axes.tick_params(axis="y", labelsize=8, colors="#526173", pad=1)
        axes.tick_params(axis="z", labelsize=8, colors="#526173", pad=2)
        axes.grid(True)
        axes.set_proj_type("persp", focal_length=0.68)
        for axis in (axes.xaxis, axes.yaxis, axes.zaxis):
            axis.pane.set_facecolor((0.98, 0.99, 1.0, 1.0))
            axis.pane.set_edgecolor("#cbd5e1")
            axis._axinfo["grid"]["color"] = (0.78, 0.82, 0.87, 0.78)
            axis._axinfo["grid"]["linewidth"] = 0.65
        axes.view_init(elev=self.elevation, azim=self.azimuth)
        axes.set_box_aspect((3.2, 1.2, 1.25), zoom=1.22)

    def _remember_view(self, _event):
        if self.axes is not None:
            self.elevation = self.axes.elev
            self.azimuth = self.axes.azim

    def resizeEvent(self, event):
        if event.size().width() <= 0 or event.size().height() <= 0:
            self._draw_pending = False
            return
        super().resizeEvent(event)

    def hideEvent(self, event):
        self._draw_pending = False
        super().hideEvent(event)

    def closeEvent(self, event):
        self._draw_pending = False
        super().closeEvent(event)

    def _on_mouse_move(self, event):
        if self.axes is None or self.annotation is None:
            return
        if event.inaxes is not self.axes or event.x is None or event.y is None or not self.entries:
            if self.annotation.get_visible():
                self.annotation.set_visible(False)
                self.draw_idle()
            return

        nearest = None
        for absolute_index, value in self.entries:
            module_index = absolute_index // self.cells_per_module
            cell_index = absolute_index % self.cells_per_module
            x_2d, y_2d, _depth = proj3d.proj_transform(
                cell_index + 0.48,
                module_index + 0.48,
                value,
                self.axes.get_proj(),
            )
            pixel_x, pixel_y = self.axes.transData.transform((x_2d, y_2d))
            distance = math.hypot(pixel_x - event.x, pixel_y - event.y)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, x_2d, y_2d, absolute_index, value)

        if nearest is None or nearest[0] > 24:
            if self.annotation.get_visible():
                self.annotation.set_visible(False)
                self.draw_idle()
            return

        _distance, x_2d, y_2d, absolute_index, value = nearest
        module_index = absolute_index // self.cells_per_module
        cell_index = absolute_index % self.cells_per_module
        self.annotation.xy = (x_2d, y_2d)
        self.annotation.set_text(
            f"模组 {module_index + 1} / 单体 {cell_index + 1:02d}\n"
            f"{value:.{self.precision}f} {self.unit}"
        )
        self.annotation.set_visible(True)
        self.draw_idle()


class ChartPanel(QWidget):
    def __init__(
        self,
        module_count,
        cells_per_module,
        value_name,
        unit,
        scale,
        precision,
        zero_is_missing=False,
        parent=None,
    ):
        super().__init__(parent)
        self.unit = str(unit)
        self.value_name = str(value_name)
        self.scale = float(scale)
        self.precision = int(precision)
        self.zero_is_missing = bool(zero_is_missing)
        self.module_count = int(module_count)
        self.cells_per_module = int(cells_per_module)
        self.values = []
        self.summary = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(6)
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("sectionHint")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.canvas = Bar3DCanvas(
            module_count,
            cells_per_module,
            value_name,
            unit,
            scale=scale,
            precision=precision,
            zero_is_missing=zero_is_missing,
            parent=self,
        )
        layout.addWidget(self.canvas, 1)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)
        self.set_values([], redraw=False)

    def set_values(self, values, redraw=True):
        self.values = list(values or [])
        expected_count = self.module_count * self.cells_per_module
        entries = _normalized_values(
            self.values,
            expected_count,
            self.scale,
            self.zero_is_missing,
        )
        if not entries:
            self.summary = {"count": 0, "minimum": None, "maximum": None, "average": None, "delta": None}
            self.summary_label.setText(f"有效 0 / {expected_count}    最小 --    最大 --    平均 --    极差 --")
        else:
            minimum_index, minimum = min(entries, key=lambda item: item[1])
            maximum_index, maximum = max(entries, key=lambda item: item[1])
            average = sum(value for _index, value in entries) / len(entries)
            delta = maximum - minimum
            self.summary = {
                "count": len(entries),
                "minimum": minimum,
                "minimum_index": minimum_index,
                "maximum": maximum,
                "maximum_index": maximum_index,
                "average": average,
                "delta": delta,
            }
            self.summary_label.setText(
                f"有效 {len(entries)} / {expected_count}    "
                f"最小 {self._format_summary_value(minimum)}（{self._location_text(minimum_index)}）    "
                f"最大 {self._format_summary_value(maximum)}（{self._location_text(maximum_index)}）    "
                f"平均 {self._format_summary_value(average)}    极差 {self._format_summary_value(delta)}"
            )
        if redraw:
            self.redraw()

    def redraw(self):
        self.canvas.draw_values(self.values)

    def clear_values(self, redraw=True):
        self.set_values([], redraw=redraw)

    def _location_text(self, absolute_index):
        module_index = absolute_index // self.cells_per_module
        cell_index = absolute_index % self.cells_per_module
        return f"模组 {module_index + 1} / 单体 {cell_index + 1:02d}"

    def _format_summary_value(self, value):
        return f"{value:.{self.precision}f} {self.unit}"


class CellVisualizationPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = None
        self._build_ui()
        self.clear_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("单体 3D 柱状图", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        context = QHBoxLayout()
        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        context.addWidget(self.cluster_label)
        context.addStretch(1)
        self.status_label = QLabel("等待单体数据", self)
        self.status_label.setObjectName("sectionHint")
        context.addWidget(self.status_label)
        root.addLayout(context)

        self.chart_tabs = QTabWidget(self)
        self.chart_tabs.setDocumentMode(True)
        root.addWidget(self.chart_tabs, 1)

        module_count = int(config.get("LECU_NUM", 1))
        self.voltage_panel = ChartPanel(
            module_count,
            int(config.get("CELL_NUM", 1)),
            "单体电压",
            "mV",
            scale=1.0,
            precision=0,
            zero_is_missing=True,
            parent=self.chart_tabs,
        )
        self.temperature_panel = ChartPanel(
            module_count,
            int(config.get("CELL_Tem_NUM", 1)),
            "单体温度",
            "℃",
            scale=10.0,
            precision=1,
            parent=self.chart_tabs,
        )
        self.chart_tabs.addTab(self.voltage_panel, "单体电压 3D")
        self.chart_tabs.addTab(self.temperature_panel, "单体温度 3D")
        self.chart_tabs.currentChanged.connect(self._on_chart_changed)
        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(250)
        self.redraw_timer.timeout.connect(self._redraw_active_chart)

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = None if cluster_index is None else int(cluster_index)
        self.current_address = "" if address is None else str(address).upper()
        if self.current_cluster_index is None:
            self.cluster_label.setText("当前簇: -")
        elif self.current_cluster_index == 0:
            self.cluster_label.setText("当前簇: 00（未编制）")
        else:
            self.cluster_label.setText(
                f"当前簇: 簇{self.current_cluster_index} / 地址 {self.current_address or '--'}"
            )

    def set_values(self, voltage_values, temperature_values):
        self.voltage_panel.set_values(voltage_values, redraw=False)
        self.temperature_panel.set_values(temperature_values, redraw=False)
        self._update_status()
        self._schedule_redraw()

    def set_voltage_values(self, values):
        self.voltage_panel.set_values(values, redraw=False)
        self._update_status()
        if self.chart_tabs.currentIndex() == 0:
            self._schedule_redraw()

    def set_temperature_values(self, values):
        self.temperature_panel.set_values(values, redraw=False)
        self._update_status()
        if self.chart_tabs.currentIndex() == 1:
            self._schedule_redraw()

    def _on_chart_changed(self, index):
        if hasattr(self, "redraw_timer"):
            self.redraw_timer.stop()
        self._redraw_active_chart()

    def _schedule_redraw(self):
        if self.isVisible() and not self.redraw_timer.isActive():
            self.redraw_timer.start()

    def _redraw_active_chart(self):
        panel = self.voltage_panel if self.chart_tabs.currentIndex() == 0 else self.temperature_panel
        panel.redraw()

    def _update_status(self):
        voltage_count = self.voltage_panel.summary.get("count", 0)
        temperature_count = self.temperature_panel.summary.get("count", 0)
        if voltage_count or temperature_count:
            self.status_label.setText(
                f"刷新 {time.strftime('%H:%M:%S')}    电压 {voltage_count} 点 / 温度 {temperature_count} 点"
            )
        else:
            self.status_label.setText("等待单体数据")

    def set_status_text(self, text):
        self.status_label.setText("" if text is None else str(text))

    def clear_values(self):
        if hasattr(self, "redraw_timer"):
            self.redraw_timer.stop()
        active_index = self.chart_tabs.currentIndex() if hasattr(self, "chart_tabs") else 0
        self.voltage_panel.clear_values(redraw=active_index == 0)
        self.temperature_panel.clear_values(redraw=active_index == 1)
        self.status_label.setText("等待单体数据")

    def closeEvent(self, event):
        if hasattr(self, "redraw_timer"):
            self.redraw_timer.stop()
        for panel in (getattr(self, "voltage_panel", None), getattr(self, "temperature_panel", None)):
            if panel is not None:
                panel.canvas._draw_pending = False
                panel.canvas.setUpdatesEnabled(False)
        super().closeEvent(event)
