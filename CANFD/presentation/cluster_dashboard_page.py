"""All-cluster operations dashboard.

This presentation component consumes immutable dashboard view models. Protocol
indexes, device polling and persistence remain owned by the lower application
layers so the screen can be maintained independently from data acquisition.
"""

from enum import IntEnum
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.dashboard_service import (
    ClusterHealth,
    FleetDashboardView,
)
from data_center.models import DataQuality
from presentation.cluster_display import format_cluster_short_name


HEALTH_SORT_ORDER = {
    ClusterHealth.OFFLINE: 0,
    ClusterHealth.ALARM: 1,
    ClusterHealth.WARNING: 2,
    ClusterHealth.UNKNOWN: 3,
    ClusterHealth.NORMAL: 4,
}

HEALTH_ACCENT_COLORS = {
    ClusterHealth.NORMAL: "#168a4a",
    ClusterHealth.WARNING: "#ed8b16",
    ClusterHealth.ALARM: "#e23c3c",
    ClusterHealth.OFFLINE: "#9099a6",
    ClusterHealth.UNKNOWN: "#9099a6",
}

ROW_BACKGROUND_COLORS = {
    ClusterHealth.ALARM: QColor("#fff5f4"),
    ClusterHealth.WARNING: QColor("#fff9f0"),
    ClusterHealth.NORMAL: QColor("#ffffff"),
    ClusterHealth.UNKNOWN: QColor("#fafbfc"),
    ClusterHealth.OFFLINE: QColor("#f5f6f8"),
}

class DashboardColumn(IntEnum):
    """Stable column identifiers for the fleet table."""

    ADDRESS = 0
    COMMUNICATION = 1
    RUN_STATE = 2
    SOC = 3
    SYSTEM_VOLTAGE = 4
    SYSTEM_CURRENT = 5
    VOLTAGE_DIFFERENCE = 6
    MAXIMUM_CELL_VOLTAGE = 7
    MINIMUM_CELL_VOLTAGE = 8
    MAXIMUM_TEMPERATURE = 9
    TEMPERATURE_DIFFERENCE = 10
    ALARM = 11
    LAST_UPDATE = 12


TABLE_HEADERS = (
    "簇",
    "通讯",
    "运行状态",
    "SOC",
    "总压(V)",
    "电流(A)",
    "压差(mV)",
    "最高单体(mV)",
    "最低单体(mV)",
    "最高温度(℃)",
    "温差(℃)",
    "告警",
    "更新时间",
)


def _format_number(value, digits=1):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


class DashboardSummaryCard(QFrame):
    """Compact fleet statistic matching the selected operations template."""

    def __init__(self, status, title, icon, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardSummaryCard")
        self.setProperty("status", status)
        self.setMinimumHeight(78)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        icon_label = QLabel(self)
        icon_label.setObjectName("dashboardSummaryIcon")
        icon_label.setProperty("status", status)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(40, 40)
        icon_label.setPixmap(
            QApplication.style().standardIcon(icon).pixmap(22, 22)
        )
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title_label = QLabel(title, self)
        title_label.setObjectName("dashboardSummaryTitle")
        text_layout.addWidget(title_label)
        self.value_label = QLabel("—", self)
        self.value_label.setObjectName("dashboardSummaryValue")
        self.value_label.setProperty("role", "time" if status == "time" else "count")
        text_layout.addWidget(self.value_label)
        layout.addLayout(text_layout, 1)


class DashboardToggle(QWidget):
    """Labeled two-state slider with the same affordance as the reference."""

    toggled = pyqtSignal(bool)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardPrioritySwitch")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        label = QLabel(text, self)
        label.setObjectName("dashboardPriorityLabel")
        layout.addWidget(label)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setObjectName("dashboardPrioritySlider")
        self.slider.setRange(0, 1)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setFixedSize(44, 24)
        self.slider.valueChanged.connect(
            lambda value: self.toggled.emit(bool(value))
        )
        layout.addWidget(self.slider)

    def isChecked(self):
        return bool(self.slider.value())

    def setChecked(self, checked):
        self.slider.setValue(1 if checked else 0)


class ClusterDashboardPage(QWidget):
    """Fleet-level dashboard with summary cards and an actionable data table."""

    cluster_activated = pyqtSignal(int, str)
    fullscreen_requested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("clusterDashboardPage")
        self._dashboard: Optional[FleetDashboardView] = None
        self._ordered_clusters = []
        self._selected_cluster_index = None
        self._summary_labels = {}
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(26, 20, 28, 22)
        root_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title = QLabel("全簇运行大屏", self)
        title.setObjectName("dashboardPageTitle")
        title_row.addWidget(title)
        hint = QLabel("点击任意簇进入实时监控", self)
        hint.setObjectName("dashboardPageHint")
        title_row.addWidget(hint)
        title_row.addStretch(1)

        self.abnormal_first_toggle = DashboardToggle("异常优先", self)
        self.abnormal_first_toggle.setChecked(True)
        self.abnormal_first_toggle.toggled.connect(self._refresh_cluster_order)
        title_row.addWidget(self.abnormal_first_toggle)

        self.fullscreen_button = QPushButton("全屏", self)
        self.fullscreen_button.setObjectName("dashboardFullscreenButton")
        self.fullscreen_button.setCheckable(True)
        self.fullscreen_button.toggled.connect(self._on_fullscreen_toggled)
        title_row.addWidget(self.fullscreen_button)
        root_layout.addLayout(title_row)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        summary_definitions = (
            (
                "online",
                "在线簇",
                QStyle.StandardPixmap.SP_DriveNetIcon,
            ),
            (
                "normal",
                "运行",
                QStyle.StandardPixmap.SP_MediaPlay,
            ),
            (
                "alarm",
                "告警",
                QStyle.StandardPixmap.SP_MessageBoxWarning,
            ),
            (
                "offline",
                "离线",
                QStyle.StandardPixmap.SP_DialogCancelButton,
            ),
            (
                "time",
                "当前时间",
                QStyle.StandardPixmap.SP_BrowserReload,
            ),
        )
        for key, label, icon in summary_definitions:
            card = DashboardSummaryCard(key, label, icon, self)
            summary_row.addWidget(card, 1)
            self._summary_labels[key] = card.value_label
        root_layout.addLayout(summary_row)

        self.cluster_table = QTableWidget(0, len(TABLE_HEADERS), self)
        self.cluster_table.setObjectName("clusterDashboardTable")
        self.cluster_table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.cluster_table.verticalHeader().setVisible(False)
        self.cluster_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.cluster_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.cluster_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.cluster_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cluster_table.setAlternatingRowColors(False)
        self.cluster_table.setShowGrid(True)
        self.cluster_table.setWordWrap(False)
        self.cluster_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.cluster_table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.cluster_table.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        # The dashboard is refreshed frequently while CAN data is arriving.
        # React on mouse press so a refresh between press and release cannot
        # swallow the user's navigation action.
        self.cluster_table.cellPressed.connect(self._on_table_row_pressed)

        header = self.cluster_table.horizontalHeader()
        header.setMinimumSectionSize(58)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for column in DashboardColumn:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            DashboardColumn.COMMUNICATION,
            QHeaderView.ResizeMode.Fixed,
        )
        header.resizeSection(DashboardColumn.COMMUNICATION, 96)
        header.setSectionResizeMode(
            DashboardColumn.RUN_STATE,
            QHeaderView.ResizeMode.Fixed,
        )
        header.resizeSection(DashboardColumn.RUN_STATE, 92)
        header.setSectionResizeMode(
            DashboardColumn.SOC,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            DashboardColumn.ALARM,
            QHeaderView.ResizeMode.Stretch,
        )
        header.resizeSection(DashboardColumn.SOC, 145)
        header.resizeSection(DashboardColumn.ALARM, 130)
        root_layout.addWidget(self.cluster_table, 1)

    def update_dashboard(self, dashboard: FleetDashboardView):
        self._dashboard = dashboard
        self._summary_labels["online"].setText(
            f"{dashboard.online_count} / {dashboard.total_count}"
        )
        self._summary_labels["normal"].setText(str(dashboard.normal_count))
        self._summary_labels["alarm"].setText(str(dashboard.alarm_count))
        self._summary_labels["offline"].setText(str(dashboard.offline_count))
        self._summary_labels["time"].setText(
            dashboard.generated_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        self._refresh_cluster_order()

    def select_cluster(self, cluster_index):
        self._selected_cluster_index = int(cluster_index)
        for row_index, cluster in enumerate(self._ordered_clusters):
            if cluster.cluster_index == self._selected_cluster_index:
                self.cluster_table.selectRow(row_index)
                return

    def _refresh_cluster_order(self):
        if self._dashboard is None:
            return
        clusters = list(self._dashboard.clusters)
        if self.abnormal_first_toggle.isChecked():
            clusters.sort(
                key=lambda cluster: (
                    HEALTH_SORT_ORDER[cluster.health],
                    cluster.cluster_index,
                )
            )
        else:
            clusters.sort(key=lambda cluster: cluster.cluster_index)
        self._ordered_clusters = clusters

        valid_indices = {cluster.cluster_index for cluster in clusters}
        if self._selected_cluster_index not in valid_indices:
            self._selected_cluster_index = None
        self._populate_cluster_table()

    def _populate_cluster_table(self):
        self.cluster_table.setUpdatesEnabled(False)
        try:
            self.cluster_table.clearContents()
            self.cluster_table.setRowCount(len(self._ordered_clusters))
            for row_index, cluster in enumerate(self._ordered_clusters):
                self._populate_cluster_row(row_index, cluster)
            if self._selected_cluster_index is not None:
                self.select_cluster(self._selected_cluster_index)
        finally:
            self.cluster_table.setUpdatesEnabled(True)
            self.cluster_table.viewport().update()

    def _populate_cluster_row(self, row_index, cluster):
        row_status = cluster.health.value
        row_background = ROW_BACKGROUND_COLORS[cluster.health]
        tooltip = "点击进入该簇的实时监控"

        item_values = {
            DashboardColumn.ADDRESS: format_cluster_short_name(
                cluster.cluster_index,
                cluster.address,
            ),
            DashboardColumn.SYSTEM_VOLTAGE: _format_number(cluster.system_voltage, 1),
            DashboardColumn.SYSTEM_CURRENT: _format_number(cluster.system_current, 1),
            DashboardColumn.VOLTAGE_DIFFERENCE: _format_number(
                cluster.voltage_difference,
                0,
            ),
            DashboardColumn.MAXIMUM_CELL_VOLTAGE: _format_number(
                cluster.maximum_cell_voltage,
                0,
            ),
            DashboardColumn.MINIMUM_CELL_VOLTAGE: _format_number(
                cluster.minimum_cell_voltage,
                0,
            ),
            DashboardColumn.MAXIMUM_TEMPERATURE: _format_number(
                cluster.maximum_temperature,
                1,
            ),
            DashboardColumn.TEMPERATURE_DIFFERENCE: _format_number(
                cluster.temperature_difference,
                1,
            ),
            DashboardColumn.LAST_UPDATE: (
                "—"
                if cluster.last_update is None
                else cluster.last_update.strftime("%Y-%m-%d %H:%M:%S")
            ),
        }
        for column in DashboardColumn:
            item = QTableWidgetItem(item_values.get(column, ""))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(row_background)
            item.setToolTip(tooltip)
            if column == DashboardColumn.ADDRESS:
                item.setData(Qt.ItemDataRole.UserRole, cluster.cluster_index)
                item.setData(
                    int(Qt.ItemDataRole.UserRole) + 1,
                    cluster.address,
                )
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor(HEALTH_ACCENT_COLORS[cluster.health]))
            self.cluster_table.setItem(row_index, column, item)

        communication_text, communication_status, communication_icon = (
            self._communication_display(cluster.communication_quality)
        )
        self.cluster_table.setCellWidget(
            row_index,
            DashboardColumn.COMMUNICATION,
            self._build_badge_cell(
                communication_text,
                communication_status,
                row_status,
                communication_icon,
            ),
        )
        self.cluster_table.setCellWidget(
            row_index,
            DashboardColumn.RUN_STATE,
            self._build_badge_cell(
                self._run_state_text(cluster),
                self._run_state_style(cluster),
                row_status,
                tooltip=self._run_state_tooltip(cluster),
            ),
        )
        self.cluster_table.setCellWidget(
            row_index,
            DashboardColumn.SOC,
            self._build_soc_cell(cluster.soc, row_status),
        )

        alarm_text = cluster.alarm_names[0] if cluster.alarm_names else "无"
        if cluster.alarm_count > 1:
            alarm_text = f"{alarm_text} 等{cluster.alarm_count}项"
        self.cluster_table.setCellWidget(
            row_index,
            DashboardColumn.ALARM,
            self._build_badge_cell(
                alarm_text,
                row_status if cluster.alarm_names else "none",
                row_status,
                tooltip="\n".join(cluster.alarm_names) or "当前无活动告警",
            ),
        )

        self.cluster_table.setRowHeight(row_index, 42)

    def _build_badge_cell(
        self,
        text,
        status,
        row_status,
        icon=None,
        tooltip="",
    ):
        container = QWidget(self.cluster_table)
        container.setObjectName("dashboardTableCell")
        container.setProperty("rowStatus", row_status)
        container.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon is not None:
            icon_label = QLabel(container)
            icon_label.setObjectName("dashboardStatusIcon")
            icon_label.setPixmap(
                QApplication.style().standardIcon(icon).pixmap(13, 13)
            )
            layout.addWidget(icon_label)

        badge = QLabel(text, container)
        badge.setObjectName("dashboardStatusBadge")
        badge.setProperty("status", status)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setToolTip(tooltip)
        layout.addWidget(badge)
        return container

    def _build_soc_cell(self, value, row_status):
        container = QWidget(self.cluster_table)
        container.setObjectName("dashboardSocCell")
        container.setProperty("rowStatus", row_status)
        container.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        value_label = QLabel(
            "—" if value is None else f"{float(value):.0f}%",
            container,
        )
        value_label.setObjectName("dashboardSocValue")
        value_label.setFixedWidth(38)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_label)

        progress = QProgressBar(container)
        progress.setObjectName("dashboardSocProgress")
        progress.setProperty("status", row_status)
        progress.setRange(0, 100)
        progress.setValue(0 if value is None else round(float(value)))
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        layout.addWidget(progress, 1)
        return container

    @staticmethod
    def _communication_display(quality):
        if quality == DataQuality.GOOD:
            return (
                "在线",
                "normal",
                QStyle.StandardPixmap.SP_DialogApplyButton,
            )
        if quality in (DataQuality.OFFLINE, DataQuality.STALE):
            return (
                "离线",
                "offline",
                QStyle.StandardPixmap.SP_DialogCancelButton,
            )
        return (
            "等待",
            "unknown",
            QStyle.StandardPixmap.SP_MessageBoxQuestion,
        )

    @staticmethod
    def _run_state_text(cluster):
        text = str(cluster.run_status_text or "").strip()
        return "—" if not text or text == "--" else text

    @staticmethod
    def _run_state_style(cluster):
        if cluster.communication_quality in (
            DataQuality.OFFLINE,
            DataQuality.STALE,
        ):
            return "offline"
        if cluster.run_status is None:
            return "unknown"
        return "none"

    @classmethod
    def _run_state_tooltip(cls, cluster):
        text = cls._run_state_text(cluster)
        if cluster.run_status is None:
            return f"簇运行状态：{text}"
        return f"簇运行状态：{text}（状态码 {cluster.run_status}）"

    def _on_table_row_pressed(self, row_index, column_index):
        del column_index
        item = self.cluster_table.item(row_index, DashboardColumn.ADDRESS)
        if item is None:
            return
        cluster_index = item.data(Qt.ItemDataRole.UserRole)
        if cluster_index is None:
            return
        self._selected_cluster_index = int(cluster_index)
        address = str(
            item.data(int(Qt.ItemDataRole.UserRole) + 1) or ""
        ).strip().upper()
        if not address:
            return
        self.cluster_activated.emit(self._selected_cluster_index, address)

    def _on_fullscreen_toggled(self, enabled):
        self.fullscreen_button.setText("退出全屏" if enabled else "全屏")
        self.fullscreen_requested.emit(bool(enabled))

    def set_fullscreen_state(self, enabled):
        enabled = bool(enabled)
        self.fullscreen_button.blockSignals(True)
        self.fullscreen_button.setChecked(enabled)
        self.fullscreen_button.setText("退出全屏" if enabled else "全屏")
        self.fullscreen_button.blockSignals(False)
