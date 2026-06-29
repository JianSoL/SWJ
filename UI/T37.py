import math
import time

import numpy as np
from matplotlib import cm, colors, patheffects, rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .conf import config


rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


BAR_COLORMAP = colors.LinearSegmentedColormap.from_list(
    "aidc_cell_value",
    ("#00a6ff", "#00d4ff", "#00e5a8", "#f2cf5b", "#ff7a45", "#ff3158"),
)

CHART_BACKGROUND = "#061119"
PANE_BACKGROUND = (0.035, 0.105, 0.145, 0.96)
FLOOR_COLOR = "#0a202a"
GRID_COLOR = (0.12, 0.50, 0.58, 0.42)
TEXT_PRIMARY = "#d9fbff"
TEXT_MUTED = "#7db8c4"
CYAN = "#22d3ee"
ALERT = "#ff4d6d"


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
        self.figure = Figure(figsize=(10, 6), dpi=100, facecolor=CHART_BACKGROUND)
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
        self.raw_values = []
        self.axes = None
        self.module_axes = None
        self.annotation = None
        self.elevation = 27
        self.azimuth = -55
        self.focal_length = 0.46
        self.show_average_plane = True
        self.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.mpl_connect("button_release_event", self._remember_view)
        self.draw_values([])

    def draw_values(self, values):
        self.raw_values = list(values or [])
        expected_count = self.module_count * self.cells_per_module
        self.entries = _normalized_values(self.raw_values, expected_count, self.scale, self.zero_is_missing)
        self.figure.clear()
        self.axes = self.figure.add_axes([0.055, 0.065, 0.70, 0.89], projection="3d")
        self.module_axes = self.figure.add_axes([0.79, 0.17, 0.19, 0.66])
        self.axes.set_facecolor(CHART_BACKGROUND)
        self.module_axes.set_facecolor(CHART_BACKGROUND)

        if not self.entries:
            self._configure_axes(0.0, 1.0)
            self.axes.text2D(
                0.5,
                0.5,
                "等待当前簇单体数据",
                transform=self.axes.transAxes,
                ha="center",
                va="center",
                color=TEXT_MUTED,
                fontsize=13,
            )
            self.axes.text2D(
                0.5,
                0.43,
                "NO CELL TELEMETRY",
                transform=self.axes.transAxes,
                ha="center",
                va="center",
                color="#2d6670",
                fontsize=8,
            )
            self.annotation = None
            self.module_axes.set_visible(False)
            self.draw()
            return

        indexes = np.asarray([index for index, _value in self.entries], dtype=int)
        display_values = np.asarray([value for _index, value in self.entries], dtype=float)
        module_indexes = indexes // self.cells_per_module
        cell_indexes = indexes % self.cells_per_module

        minimum = float(display_values.min())
        maximum = float(display_values.max())
        average = float(display_values.mean())
        span = maximum - minimum
        baseline_margin = max(span * 0.30, 5.0 if self.unit == "mV" else 1.2)
        baseline = math.floor((minimum - baseline_margin) * 10.0) / 10.0
        heights = np.maximum(display_values - baseline, 0.001)

        normalizer = colors.Normalize(vmin=minimum, vmax=maximum if maximum != minimum else minimum + 1.0)
        bar_colors = BAR_COLORMAP(normalizer(display_values))
        self._draw_floor(baseline)
        if self.show_average_plane:
            self._draw_average_plane(average)
        self.axes.bar3d(
            cell_indexes + 0.14,
            module_indexes + 0.14,
            np.full(len(display_values), baseline),
            np.full(len(display_values), 0.70),
            np.full(len(display_values), 0.70),
            heights,
            color=bar_colors,
            edgecolor="#b8f7ff",
            linewidth=0.32,
            shade=True,
            zsort="average",
        )

        upper_margin = max(span * 0.24, 4.0 if self.unit == "mV" else 1.0)
        self._configure_axes(baseline, maximum + upper_margin)
        self._draw_extrema(indexes, display_values, minimum, maximum, upper_margin)
        self._draw_hud(len(display_values), minimum, maximum, average)
        self._draw_module_profile(indexes, display_values, normalizer, minimum, maximum)
        colorbar_axes = self.figure.add_axes([0.025, 0.22, 0.010, 0.56])
        colorbar = self.figure.colorbar(
            cm.ScalarMappable(norm=normalizer, cmap=BAR_COLORMAP),
            cax=colorbar_axes,
        )
        colorbar.set_label(f"{self.value_name} ({self.unit})", color=TEXT_MUTED, labelpad=8)
        colorbar.ax.tick_params(labelsize=8, colors=TEXT_MUTED, length=2)
        colorbar.outline.set_edgecolor("#245461")
        colorbar.ax.set_facecolor(CHART_BACKGROUND)

        self.annotation = self.axes.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.45", "fc": "#071923", "ec": CYAN, "alpha": 0.97},
            color=TEXT_PRIMARY,
            fontsize=9,
            visible=False,
        )
        self.draw()

    def _draw_module_profile(self, indexes, values, normalizer, minimum, maximum):
        axes = self.module_axes
        module_stats = []
        for module_index in range(self.module_count):
            mask = (indexes // self.cells_per_module) == module_index
            module_values = values[mask]
            if len(module_values) == 0:
                continue
            module_stats.append(
                (
                    module_index,
                    float(module_values.min()),
                    float(module_values.max()),
                    float(module_values.mean()),
                )
            )
        if not module_stats:
            axes.set_visible(False)
            return

        axes.set_visible(True)
        y_values = np.arange(len(module_stats))
        means = np.asarray([item[3] for item in module_stats])
        lows = np.asarray([item[1] for item in module_stats])
        highs = np.asarray([item[2] for item in module_stats])
        profile_colors = BAR_COLORMAP(normalizer(means))
        axes.hlines(y_values, lows, highs, color=profile_colors, linewidth=5.0, alpha=0.72)
        axes.scatter(
            means,
            y_values,
            s=34,
            color=profile_colors,
            edgecolor="#d9fbff",
            linewidth=0.7,
            zorder=3,
        )
        span = max(maximum - minimum, 1.0)
        axes.set_xlim(minimum - span * 0.18, maximum + span * 0.34)
        axes.set_ylim(-0.65, len(module_stats) - 0.35)
        axes.set_yticks(y_values)
        axes.set_yticklabels([f"M{item[0] + 1}" for item in module_stats])
        axes.invert_yaxis()
        axes.set_title("模组均值 / 极差", loc="left", color=TEXT_PRIMARY, fontsize=10, fontweight="bold", pad=12)
        axes.set_xlabel(self.unit, color=TEXT_MUTED, fontsize=8)
        axes.tick_params(axis="both", colors=TEXT_MUTED, labelsize=8, length=0)
        axes.grid(True, axis="x", color="#174653", linewidth=0.65, alpha=0.7)
        axes.set_axisbelow(True)
        for spine in axes.spines.values():
            spine.set_visible(False)
        for y_value, mean in zip(y_values, means):
            axes.text(
                mean + span * 0.035,
                y_value,
                f"{mean:.{self.precision}f}",
                color=TEXT_PRIMARY,
                fontsize=8,
                va="center",
            )

    def _draw_floor(self, baseline):
        x_grid, y_grid = np.meshgrid(
            np.arange(self.cells_per_module + 1),
            np.arange(self.module_count + 1),
        )
        z_grid = np.full_like(x_grid, baseline, dtype=float)
        self.axes.plot_surface(
            x_grid,
            y_grid,
            z_grid,
            color=FLOOR_COLOR,
            edgecolor="#174d58",
            linewidth=0.42,
            alpha=0.94,
            antialiased=True,
            shade=False,
            zorder=0,
        )
        for module_boundary in range(self.module_count + 1):
            self.axes.plot(
                [0, self.cells_per_module],
                [module_boundary, module_boundary],
                [baseline, baseline],
                color="#1c6975",
                linewidth=0.75,
                alpha=0.72,
                zorder=1,
            )

    def _draw_average_plane(self, average):
        x_grid, y_grid = np.meshgrid(
            [0, self.cells_per_module],
            [0, self.module_count],
        )
        z_grid = np.full_like(x_grid, average, dtype=float)
        self.axes.plot_surface(
            x_grid,
            y_grid,
            z_grid,
            color=CYAN,
            alpha=0.10,
            linewidth=0,
            antialiased=False,
            shade=False,
            zorder=1,
        )

    def _draw_extrema(self, indexes, values, minimum, maximum, upper_margin):
        extrema = (
            (int(indexes[int(np.argmin(values))]), minimum, CYAN, "MIN"),
            (int(indexes[int(np.argmax(values))]), maximum, ALERT, "MAX"),
        )
        label_offset = max(upper_margin * 0.16, 0.5)
        for absolute_index, value, color, label in extrema:
            module_index = absolute_index // self.cells_per_module
            cell_index = absolute_index % self.cells_per_module
            x_value = cell_index + 0.49
            y_value = module_index + 0.49
            self.axes.scatter(
                [x_value],
                [y_value],
                [value],
                s=34,
                color=color,
                edgecolor="#ffffff",
                linewidth=0.65,
                depthshade=False,
                zorder=8,
            )
            text = self.axes.text(
                x_value,
                y_value,
                value + label_offset,
                f"{label} {value:.{self.precision}f}",
                color=color,
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="bottom",
                zorder=9,
            )
            text.set_path_effects([patheffects.withStroke(linewidth=2.2, foreground=CHART_BACKGROUND)])

    def _draw_hud(self, count, minimum, maximum, average):
        self.axes.text2D(
            0.985,
            0.965,
            f"LIVE  {count:03d} PTS\nAVG {average:.{self.precision}f}  Δ {maximum - minimum:.{self.precision}f} {self.unit}",
            transform=self.axes.transAxes,
            ha="right",
            va="top",
            color=TEXT_PRIMARY,
            fontsize=8,
            linespacing=1.45,
            bbox={"boxstyle": "round,pad=0.45", "fc": "#081d27", "ec": "#1c5c67", "alpha": 0.88},
        )

    def _configure_axes(self, z_minimum, z_maximum):
        axes = self.axes
        axes.set_xlim(0, self.cells_per_module)
        axes.set_ylim(0, self.module_count)
        axes.set_zlim(z_minimum, max(z_maximum, z_minimum + 1.0))
        axes.set_xlabel("单体编号", labelpad=9, color=TEXT_MUTED)
        axes.set_ylabel("模组", labelpad=9, color=TEXT_MUTED)
        axes.set_zlabel(f"{self.value_name} ({self.unit})", labelpad=8, color=TEXT_MUTED)

        x_step = 1 if self.cells_per_module <= 16 else max(1, math.ceil(self.cells_per_module / 16))
        x_ticks = np.arange(0, self.cells_per_module, x_step) + 0.5
        axes.set_xticks(x_ticks)
        axes.set_xticklabels([str(index + 1) for index in range(0, self.cells_per_module, x_step)])
        axes.set_yticks(np.arange(self.module_count) + 0.5)
        axes.set_yticklabels([f"M{index + 1}" for index in range(self.module_count)])
        axes.tick_params(axis="x", labelsize=8, colors=TEXT_MUTED, pad=1)
        axes.tick_params(axis="y", labelsize=8, colors=TEXT_MUTED, pad=1)
        axes.tick_params(axis="z", labelsize=8, colors=TEXT_MUTED, pad=2)
        axes.grid(True)
        axes.set_proj_type("persp", focal_length=self.focal_length)
        for axis in (axes.xaxis, axes.yaxis, axes.zaxis):
            axis.pane.set_facecolor(PANE_BACKGROUND)
            axis.pane.set_edgecolor("#174653")
            axis.line.set_color("#2a6975")
            axis._axinfo["grid"]["color"] = GRID_COLOR
            axis._axinfo["grid"]["linewidth"] = 0.62
        axes.view_init(elev=self.elevation, azim=self.azimuth)
        responsive_zoom = max(1.05, min(1.25, self.height() / 420.0 * 1.25))
        axes.set_box_aspect((2.9, 1.5, 1.35), zoom=responsive_zoom)

    def set_view_preset(self, preset):
        presets = {
            "perspective": (27, -55, 0.46),
            "top": (72, -90, 0.62),
            "side": (20, -18, 0.58),
        }
        if preset not in presets:
            return
        self.elevation, self.azimuth, self.focal_length = presets[preset]
        if self.axes is not None:
            self.axes.set_proj_type("persp", focal_length=self.focal_length)
            self.axes.view_init(elev=self.elevation, azim=self.azimuth)
            self.draw_idle()

    def set_average_plane(self, enabled):
        enabled = bool(enabled)
        if enabled == self.show_average_plane:
            return
        self.show_average_plane = enabled
        self.draw_values(self.raw_values)

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

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(0)
        controls.addStretch(1)
        view_caption = QLabel("视角", self)
        view_caption.setObjectName("sectionHint")
        controls.addWidget(view_caption)
        controls.addSpacing(8)
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_buttons = {}
        for preset, text in (("perspective", "透视"), ("top", "俯视"), ("side", "侧视")):
            button = QToolButton(self)
            button.setText(text)
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setProperty("viewSegment", True)
            button.setToolTip(f"切换到{text}视角")
            button.clicked.connect(lambda _checked, preset=preset: self.canvas.set_view_preset(preset))
            self.view_group.addButton(button)
            self.view_buttons[preset] = button
            controls.addWidget(button)
        self.view_buttons["perspective"].setChecked(True)
        controls.addSpacing(12)
        self.average_plane_checkbox = QCheckBox("平均面", self)
        self.average_plane_checkbox.setChecked(True)
        self.average_plane_checkbox.setToolTip("显示当前数据平均值参考面")
        self.average_plane_checkbox.toggled.connect(self.canvas.set_average_plane)
        controls.addWidget(self.average_plane_checkbox)
        layout.addLayout(controls)

        layout.addWidget(self.canvas, 1)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.toolbar.setStyleSheet(
            "QToolBar { background: #f5f8fb; border: 1px solid #cbd7e4; padding: 2px; }"
            "QToolButton { background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 3px; }"
            "QToolButton:hover { background: #e4f4f7; border-color: #83c7d2; }"
        )
        layout.addWidget(self.toolbar, 0, Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet(
            "QToolButton[viewSegment='true'] { background: #f6f8fb; color: #526173; border: 1px solid #c9d4e2; padding: 4px 10px; }"
            "QToolButton[viewSegment='true']:checked { background: #0a2631; color: #7ff4ff; border-color: #20b9cf; }"
        )
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
