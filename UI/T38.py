import math
import time
from datetime import datetime

import numpy as np
from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from application.trend_store import TrendDataStore, aggregate_period_statistics


rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


class KLineCanvas(FigureCanvasQTAgg):
    UP_COLOR = "#e53935"
    DOWN_COLOR = "#16a05d"
    FLAT_COLOR = "#64748b"

    def __init__(self, value_name, unit, precision, parent=None):
        self.figure = Figure(figsize=(11, 6), dpi=100, facecolor="#ffffff")
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(360)
        self.value_name = str(value_name)
        self.unit = str(unit)
        self.precision = int(precision)
        self.bars = []
        self.main_axes = None
        self.count_axes = None
        self.annotation = None
        self.mpl_connect("motion_notify_event", self._on_mouse_move)
        self._create_axes()
        self.draw_bars([])

    def _create_axes(self):
        grid = self.figure.add_gridspec(5, 1, hspace=0.06)
        self.main_axes = self.figure.add_subplot(grid[:4, 0])
        self.count_axes = self.figure.add_subplot(grid[4, 0], sharex=self.main_axes)
        self.figure.subplots_adjust(left=0.07, right=0.985, bottom=0.11, top=0.96)

    def draw_bars(self, bars):
        self.bars = list(bars or [])
        self.main_axes.clear()
        self.count_axes.clear()
        self.count_axes.set_visible(True)
        self._style_axes()

        if not self.bars:
            self.main_axes.text(
                0.5,
                0.5,
                f"等待当前簇{self.value_name}索引数据",
                transform=self.main_axes.transAxes,
                ha="center",
                va="center",
                color="#7b8797",
                fontsize=13,
            )
            self.main_axes.set_xticks([])
            self.main_axes.set_yticks([])
            self.count_axes.set_visible(False)
            self.annotation = None
            self.draw()
            return

        x_values = np.arange(len(self.bars), dtype=float)
        latest_values = np.asarray([bar.latest for bar in self.bars], dtype=float)
        y_min = min(bar.minimum for bar in self.bars)
        y_max = max(bar.maximum for bar in self.bars)
        y_span = max(y_max - y_min, max(abs(y_min), abs(y_max), 1.0) * 0.004)
        body_epsilon = y_span * 0.012

        candle_colors = []
        wick_segments = []
        body_vertices = []
        for x_value, bar in zip(x_values, self.bars):
            color = self._bar_color(bar)
            candle_colors.append(color)
            wick_segments.append(((x_value, bar.minimum), (x_value, bar.maximum)))
            body_bottom = min(bar.first, bar.latest)
            body_height = max(abs(bar.latest - bar.first), body_epsilon)
            if bar.first == bar.latest:
                body_bottom -= body_epsilon / 2.0
            body_vertices.append(
                (
                    (x_value - 0.31, body_bottom),
                    (x_value + 0.31, body_bottom),
                    (x_value + 0.31, body_bottom + body_height),
                    (x_value - 0.31, body_bottom + body_height),
                )
            )
        self.main_axes.add_collection(
            LineCollection(wick_segments, colors=candle_colors, linewidths=1.1, zorder=2)
        )
        self.main_axes.add_collection(
            PolyCollection(
                body_vertices,
                facecolors=candle_colors,
                edgecolors=candle_colors,
                linewidths=0.8,
                alpha=0.9,
                zorder=3,
            )
        )

        self.main_axes.plot(
            x_values,
            latest_values,
            color="#2563eb",
            linewidth=1.05,
            alpha=0.82,
            label=f"{self.value_name}趋势",
            zorder=4,
        )
        if len(latest_values) >= 2:
            moving_average = np.asarray(
                [
                    np.mean(latest_values[max(0, index - 4):index + 1])
                    for index in range(len(latest_values))
                ]
            )
            self.main_axes.plot(
                x_values,
                moving_average,
                color="#f59e0b",
                linewidth=1.25,
                label="5周期均值",
                zorder=4,
            )
        self.main_axes.set_xlim(-0.8, len(self.bars) - 0.2)
        self.main_axes.set_ylim(y_min - y_span * 0.14, y_max + y_span * 0.14)
        self.main_axes.legend(loc="upper left", frameon=False, fontsize=8, ncol=2)
        self.main_axes.tick_params(axis="x", labelbottom=False)

        counts = [bar.sample_count for bar in self.bars]
        count_segments = [((x_value, 0), (x_value, count)) for x_value, count in zip(x_values, counts)]
        self.count_axes.add_collection(
            LineCollection(count_segments, colors=candle_colors, linewidths=5.0, alpha=0.78)
        )
        self.count_axes.set_ylabel("采样", color="#526173", fontsize=8)
        self.count_axes.set_ylim(0, max(counts) * 1.2 + 0.5)
        tick_step = max(1, math.ceil(len(self.bars) / 8))
        tick_indexes = list(range(0, len(self.bars), tick_step))
        if tick_indexes[-1] != len(self.bars) - 1:
            tick_indexes.append(len(self.bars) - 1)
        self.count_axes.set_xticks(tick_indexes)
        self.count_axes.set_xticklabels(
            [datetime.fromtimestamp(self.bars[index].bucket_start).strftime("%H:%M:%S") for index in tick_indexes],
            rotation=0,
            ha="center",
        )

        self.annotation = self.main_axes.annotate(
            "",
            xy=(0, 0),
            xytext=(14, 14),
            textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.45", "fc": "white", "ec": "#1f66e5", "alpha": 0.97},
            color="#172033",
            fontsize=9,
            visible=False,
            zorder=8,
        )
        self.draw()

    def _style_axes(self):
        for axes in (self.main_axes, self.count_axes):
            axes.set_facecolor("#ffffff")
            axes.grid(True, color="#d8dee8", linewidth=0.7, alpha=0.82)
            axes.set_axisbelow(True)
            axes.tick_params(axis="both", colors="#526173", labelsize=8)
            axes.spines["top"].set_visible(False)
            axes.spines["right"].set_visible(False)
            axes.spines["left"].set_color("#cbd5e1")
            axes.spines["bottom"].set_color("#cbd5e1")
        self.main_axes.set_ylabel(f"{self.value_name} ({self.unit})", color="#344256", fontsize=9)
        self.main_axes.ticklabel_format(axis="y", style="plain", useOffset=False)

    def _bar_color(self, bar):
        if bar.latest > bar.first:
            return self.UP_COLOR
        if bar.latest < bar.first:
            return self.DOWN_COLOR
        return self.FLAT_COLOR

    def _on_mouse_move(self, event):
        if self.annotation is None or not self.bars:
            return
        if event.inaxes is not self.main_axes or event.xdata is None:
            if self.annotation.get_visible():
                self.annotation.set_visible(False)
                self.draw_idle()
            return
        index = int(round(event.xdata))
        if index < 0 or index >= len(self.bars) or abs(event.xdata - index) > 0.6:
            if self.annotation.get_visible():
                self.annotation.set_visible(False)
                self.draw_idle()
            return
        bar = self.bars[index]
        timestamp = datetime.fromtimestamp(bar.bucket_start).strftime("%Y-%m-%d %H:%M:%S")
        self.annotation.xy = (index, bar.maximum)
        self.annotation.set_text(
            f"{timestamp}\n"
            f"周期首值 {bar.first:.{self.precision}f}  周期最高 {bar.maximum:.{self.precision}f}\n"
            f"周期最低 {bar.minimum:.{self.precision}f}  最新值 {bar.latest:.{self.precision}f} {self.unit}\n"
            f"采样 {bar.sample_count}"
        )
        self.annotation.set_visible(True)
        self.draw_idle()


class KLinePanel(QWidget):
    def __init__(self, value_name, unit, precision, parent=None):
        super().__init__(parent)
        self.value_name = value_name
        self.unit = unit
        self.precision = precision
        self.summary = {"count": 0, "first": None, "maximum": None, "minimum": None, "latest": None}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("sectionHint")
        self.summary_label.setMinimumHeight(26)
        root.addWidget(self.summary_label)
        self.canvas = KLineCanvas(value_name, unit, precision, self)
        root.addWidget(self.canvas, 1)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        toolbar.setObjectName("chartToolbar")
        root.addWidget(toolbar)
        self.toolbar = toolbar
        self.set_bars([])

    def set_bars(self, bars):
        bars = list(bars or [])
        if not bars:
            self.summary = {"count": 0, "first": None, "maximum": None, "minimum": None, "latest": None}
            self.summary_label.setText(
                "K线 0 根    最新值 --    周期首值 --    周期最高 --    周期最低 --"
            )
        else:
            latest = bars[-1]
            self.summary = {
                "count": len(bars),
                "first": latest.first,
                "maximum": latest.maximum,
                "minimum": latest.minimum,
                "latest": latest.latest,
                "sample_count": latest.sample_count,
            }
            value = lambda number: f"{number:.{self.precision}f} {self.unit}"
            self.summary_label.setText(
                f"K线 {len(bars)} 根    最新值 {value(latest.latest)}    "
                f"周期首值 {value(latest.first)}    周期最高 {value(latest.maximum)}    "
                f"周期最低 {value(latest.minimum)}    "
                f"本周期采样 {latest.sample_count}"
            )
        self.canvas.draw_bars(bars)


class SystemKLinePage(QWidget):
    METRICS = {
        "voltage": {"name": "总压", "unit": "V", "precision": 1},
        "hall_current": {"name": "霍尔电流", "unit": "A", "precision": 1},
        "shunt_current": {"name": "分流器电流", "unit": "A", "precision": 1},
    }

    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_address = ""
        self.data_store = TrendDataStore(metrics=self.METRICS.keys())
        self._build_ui()

    def set_data_store(self, data_store):
        if data_store is None or data_store is self.data_store:
            return
        self.data_store = data_store
        if self.isVisible():
            self.refresh_active_chart(force=True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("总压 / 霍尔电流 / 分流器电流 K 线", self)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)
        self.cluster_label = QLabel("当前簇: -", self)
        self.cluster_label.setObjectName("contextLabel")
        toolbar_row.addWidget(self.cluster_label)
        toolbar_row.addStretch(1)

        toolbar_row.addWidget(QLabel("周期", self))
        self.period_selector = QComboBox(self)
        for text, seconds in (("1 秒", 1), ("5 秒", 5), ("10 秒", 10), ("30 秒", 30), ("1 分钟", 60)):
            self.period_selector.addItem(text, seconds)
        self.period_selector.setCurrentIndex(self.period_selector.findData(5))
        self.period_selector.setToolTip("每根K线聚合的采样时间")
        toolbar_row.addWidget(self.period_selector)

        toolbar_row.addWidget(QLabel("窗口", self))
        self.window_selector = QComboBox(self)
        for text, count in (("60 根", 60), ("120 根", 120), ("240 根", 240)):
            self.window_selector.addItem(text, count)
        self.window_selector.setCurrentIndex(self.window_selector.findData(120))
        self.window_selector.setToolTip("图表保留的最近K线数量")
        toolbar_row.addWidget(self.window_selector)

        self.pause_checkbox = QCheckBox("暂停刷新", self)
        self.pause_checkbox.setToolTip("暂停画面刷新，后台仍继续采集数据")
        toolbar_row.addWidget(self.pause_checkbox)
        self.clear_button = QPushButton("清空当前簇", self)
        self.clear_button.setToolTip("清除当前簇的总压、霍尔电流和分流器电流趋势缓存")
        toolbar_row.addWidget(self.clear_button)
        root.addLayout(toolbar_row)

        self.status_label = QLabel("等待索引数据", self)
        self.status_label.setObjectName("sectionHint")
        root.addWidget(self.status_label)

        self.chart_tabs = QTabWidget(self)
        self.chart_tabs.setDocumentMode(True)
        self.panels = {}
        for metric, definition in self.METRICS.items():
            panel = KLinePanel(
                definition["name"],
                definition["unit"],
                definition["precision"],
                self.chart_tabs,
            )
            self.panels[metric] = panel
            self.chart_tabs.addTab(panel, f"{definition['name']} K线")
        root.addWidget(self.chart_tabs, 1)

        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(320)
        self.redraw_timer.timeout.connect(self._redraw_active_chart)
        self.period_selector.currentIndexChanged.connect(self.refresh_active_chart)
        self.window_selector.currentIndexChanged.connect(self.refresh_active_chart)
        self.pause_checkbox.toggled.connect(self._on_pause_toggled)
        self.clear_button.clicked.connect(self.clear_current_cluster)
        self.chart_tabs.currentChanged.connect(self.refresh_active_chart)

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
        if self.isVisible():
            self.refresh_active_chart(force=True)
        else:
            self._update_status()

    def add_sample(self, cluster_index, metric, value, timestamp=None):
        try:
            cluster_index = int(cluster_index)
            value = float(value)
            timestamp = time.time() if timestamp is None else float(timestamp)
        except (TypeError, ValueError):
            return False
        if cluster_index <= 0 or metric not in self.METRICS:
            return False
        if not math.isfinite(value) or not math.isfinite(timestamp):
            return False
        accepted = self.data_store.add_sample(cluster_index, metric, value, timestamp)
        if not accepted:
            return False
        self.notify_sample_added(cluster_index, metric)
        return True

    def notify_sample_added(self, cluster_index, metric):
        if (
            cluster_index == self.current_cluster_index
            and metric in self.METRICS
            and not self.pause_checkbox.isChecked()
            and self.isVisible()
            and not self.redraw_timer.isActive()
        ):
            self.redraw_timer.start()

    def sample_count(self, cluster_index, metric):
        return self.data_store.sample_count(cluster_index, metric)

    def bars_for(self, cluster_index, metric, period_seconds=None, max_bars=None):
        if metric not in self.METRICS:
            return []
        if period_seconds is None:
            period_seconds = self.period_selector.currentData()
        if max_bars is None:
            max_bars = self.window_selector.currentData()
        return self.data_store.bars_for(cluster_index, metric, period_seconds, max_bars)

    def refresh_active_chart(self, _value=None, force=False):
        if self.pause_checkbox.isChecked() and not force:
            self._update_status()
            return
        self.redraw_timer.stop()
        self._redraw_active_chart()

    def _active_metric(self):
        metric_order = tuple(self.METRICS)
        index = self.chart_tabs.currentIndex()
        if index < 0 or index >= len(metric_order):
            return metric_order[0]
        return metric_order[index]

    def _redraw_active_chart(self):
        metric = self._active_metric()
        cluster_index = self.current_cluster_index or 0
        bars = self.bars_for(cluster_index, metric) if cluster_index > 0 else []
        self.panels[metric].set_bars(bars)
        self._update_status(metric, bars)

    def _update_status(self, metric=None, bars=None):
        if not self.current_cluster_index:
            self.status_label.setText("当前选择 00（未编制），不会采集趋势数据。")
            return
        if self.pause_checkbox.isChecked():
            self.status_label.setText("画面已暂停，后台仍在采集当前簇数据。")
            return
        metric = metric or self._active_metric()
        if bars is None:
            bars = self.bars_for(self.current_cluster_index, metric)
        sample_count = self.sample_count(self.current_cluster_index, metric)
        definition = self.METRICS[metric]
        if bars:
            latest_time = datetime.fromtimestamp(bars[-1].bucket_start).strftime("%H:%M:%S")
            self.status_label.setText(
                f"{definition['name']}已采样 {sample_count} 次，显示最近 {len(bars)} 根K线，最新周期 {latest_time}。"
            )
        else:
            self.status_label.setText(f"等待当前簇{definition['name']}索引数据。")

    def _on_pause_toggled(self, paused):
        if not paused:
            self.refresh_active_chart(force=True)
        else:
            self.redraw_timer.stop()
            self._update_status()

    def clear_current_cluster(self):
        cluster_index = self.current_cluster_index or 0
        if cluster_index > 0:
            self.data_store.clear_cluster(cluster_index)
        for panel in self.panels.values():
            panel.set_bars([])
        self._update_status()

    def closeEvent(self, event):
        self.redraw_timer.stop()
        super().closeEvent(event)
