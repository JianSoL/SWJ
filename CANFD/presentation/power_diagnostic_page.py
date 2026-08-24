import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from presentation.cluster_display import format_cluster_context


class PowerDiagnosticPage(QWidget):
    refreshRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_cluster_index = None
        self.current_cluster_address = ""
        self.current_report = {}
        self.current_events = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("上下电诊断", self)
        title.setObjectName("pageTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.cluster_label = QLabel("当前簇: --", self)
        self.cluster_label.setObjectName("contextLabel")
        title_row.addWidget(self.cluster_label)
        root.addLayout(title_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.auto_refresh_checkbox = QCheckBox("自动刷新", self)
        self.auto_refresh_checkbox.setChecked(True)
        toolbar.addWidget(self.auto_refresh_checkbox)
        toolbar.addWidget(QLabel("界面间隔", self))
        self.interval_spinbox = QSpinBox(self)
        self.interval_spinbox.setRange(200, 5000)
        self.interval_spinbox.setSingleStep(100)
        self.interval_spinbox.setValue(500)
        self.interval_spinbox.setSuffix(" ms")
        self.interval_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.interval_spinbox.setFixedWidth(108)
        toolbar.addWidget(self.interval_spinbox)
        self.refresh_button = QPushButton("立即刷新", self)
        self.refresh_button.setObjectName("primaryButton")
        toolbar.addWidget(self.refresh_button)
        self.export_button = QPushButton("导出快照", self)
        toolbar.addWidget(self.export_button)
        toolbar.addStretch(1)
        self.source_label = QLabel("固件: BCU615/06.bcu_app_02v01", self)
        self.source_label.setObjectName("sectionHint")
        toolbar.addWidget(self.source_label)
        root.addLayout(toolbar)

        self.summary_banner = QLabel("等待诊断数据", self)
        self.summary_banner.setObjectName("diagnosticBanner")
        self.summary_banner.setProperty("severity", "unknown")
        self.summary_banner.setWordWrap(True)
        root.addWidget(self.summary_banner)

        metrics = QFrame(self)
        metrics.setObjectName("diagnosticMetricBand")
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setContentsMargins(12, 8, 12, 8)
        metrics_layout.setSpacing(20)
        self.state_value = self._metric(metrics_layout, "当前状态")
        self.blocked_value = self._metric(metrics_layout, "阻断项")
        self.warning_value = self._metric(metrics_layout, "注意项")
        self.shutdown_value = self._metric(metrics_layout, "下电判断")
        self.updated_value = self._metric(metrics_layout, "更新时间")
        root.addWidget(metrics)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setChildrenCollapsible(False)

        conditions_group = QGroupBox("上电条件与实时证据", splitter)
        conditions_layout = QVBoxLayout(conditions_group)
        self.conditions_table = QTableWidget(conditions_group)
        self.conditions_table.setColumnCount(6)
        self.conditions_table.setHorizontalHeaderLabels(
            ["类别", "条件", "当前值", "判断", "证据", "处理建议"]
        )
        self._configure_table(self.conditions_table)
        header = self.conditions_table.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        conditions_layout.addWidget(self.conditions_table)
        splitter.addWidget(conditions_group)

        events_group = QGroupBox("下电事件记录", splitter)
        events_layout = QVBoxLayout(events_group)
        self.events_table = QTableWidget(events_group)
        self.events_table.setColumnCount(5)
        self.events_table.setHorizontalHeaderLabels(
            ["时间", "状态变化", "类型", "原因", "关联证据"]
        )
        self._configure_table(self.events_table)
        event_header = self.events_table.horizontalHeader()
        for column in range(3):
            event_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        event_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        event_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        events_layout.addWidget(self.events_table)
        splitter.addWidget(events_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("CANFD连接后按当前簇自动采集诊断索引。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.export_button.clicked.connect(self.export_snapshot)

    def _metric(self, layout, title):
        block = QWidget(self)
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(2)
        caption = QLabel(title, block)
        caption.setObjectName("fieldCaption")
        value = QLabel("--", block)
        value.setObjectName("diagnosticMetricValue")
        block_layout.addWidget(caption)
        block_layout.addWidget(value)
        layout.addWidget(block, 1)
        return value

    @staticmethod
    def _configure_table(table):
        table.setMinimumSize(0, 80)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)

    @staticmethod
    def _refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def set_cluster_context(self, cluster_index, address):
        self.current_cluster_index = None if cluster_index is None else int(cluster_index)
        self.current_cluster_address = str(address or "").upper()
        if self.current_cluster_index is None:
            self.cluster_label.setText("当前簇: --")
        else:
            self.cluster_label.setText(
                format_cluster_context(
                    self.current_cluster_index,
                    self.current_cluster_address,
                )
            )

    def set_status_text(self, text, failed=False):
        self.status_label.setText(str(text or ""))
        self.status_label.setProperty("status", "danger" if failed else "info")
        self._refresh_style(self.status_label)

    def refresh_interval_ms(self):
        return int(self.interval_spinbox.value())

    def auto_refresh_enabled(self):
        return self.auto_refresh_checkbox.isChecked()

    def clear_values(self):
        self.current_report = {}
        self.current_events = []
        self.conditions_table.setRowCount(0)
        self.events_table.setRowCount(0)
        self.summary_banner.setText("等待诊断数据")
        self.summary_banner.setProperty("severity", "unknown")
        self._refresh_style(self.summary_banner)
        for label in (
            self.state_value,
            self.blocked_value,
            self.warning_value,
            self.shutdown_value,
            self.updated_value,
        ):
            label.setText("--")

    def update_report(self, report, events=None):
        self.current_report = dict(report or {})
        self.current_events = list(events or [])
        if not self.current_report:
            self.clear_values()
            return

        severity = self.current_report.get("summary_status", "unknown")
        title = self.current_report.get("summary_title", "等待诊断数据")
        primary = self.current_report.get("primary_reason", "")
        self.summary_banner.setText(f"{title}\n{primary}" if primary else title)
        self.summary_banner.setProperty("severity", severity)
        self._refresh_style(self.summary_banner)

        self.state_value.setText(self.current_report.get("run_status_name", "--"))
        self.blocked_value.setText(str(self.current_report.get("blocked_count", 0)))
        self.warning_value.setText(str(self.current_report.get("warning_count", 0)))
        shutdown_abnormal = self.current_report.get("shutdown_status") == "abnormal"
        self.shutdown_value.setText("异常" if shutdown_abnormal else "正常")
        self.shutdown_value.setProperty("severity", "danger" if shutdown_abnormal else "ok")
        self._refresh_style(self.shutdown_value)
        self.updated_value.setText(self.current_report.get("generated_at", "--"))
        self.source_label.setText(f"固件: {self.current_report.get('firmware_source', '--')}")

        conditions = self.current_report.get("conditions", [])
        self.conditions_table.setRowCount(len(conditions))
        status_colors = {
            "ok": QColor(22, 132, 74, 28),
            "blocked": QColor(217, 45, 32, 28),
            "warning": QColor(217, 119, 6, 28),
            "unknown": QColor(95, 111, 131, 28),
        }
        for row, condition in enumerate(conditions):
            values = (
                condition.get("category", ""),
                condition.get("name", ""),
                condition.get("value", ""),
                condition.get("status_text", ""),
                condition.get("evidence", ""),
                condition.get("advice", ""),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(
                    f"{condition.get('source', '')}\n{condition.get('evidence', '')}\n"
                    f"{condition.get('advice', '')}"
                )
                if column in (0, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    item.setBackground(
                        status_colors.get(condition.get("status"), status_colors["unknown"])
                    )
                self.conditions_table.setItem(row, column, item)

        self.events_table.setRowCount(len(self.current_events))
        for row, event in enumerate(reversed(self.current_events)):
            values = (
                event.get("time", ""),
                event.get("transition", ""),
                event.get("type", ""),
                event.get("cause", ""),
                event.get("evidence", ""),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column in (0, 1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.events_table.setItem(row, column, item)

    def export_snapshot(self):
        if not self.current_report:
            self.set_status_text("没有可导出的诊断数据。", failed=True)
            return
        cluster = "unknown" if self.current_cluster_index is None else self.current_cluster_index
        default_name = f"power_diagnostic_cluster_{cluster}.json"
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出上下电诊断快照",
            str(Path.home() / default_name),
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        payload = {
            "cluster_index": self.current_cluster_index,
            "cluster_address": self.current_cluster_address,
            "report": self.current_report,
            "events": self.current_events,
        }
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.set_status_text(f"诊断快照已导出: {path}")
