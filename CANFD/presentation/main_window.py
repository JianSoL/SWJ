from contextlib import contextmanager
from pathlib import Path
import time

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.config_loader import save_runtime_config_fields
from application.power_diagnostics import PowerDiagnosticAnalyzer
from application.trend_store import TrendDataStore
from UI.Q14 import Ui_Form
from UI.T25 import BatteryMonitor
from UI.T26 import BatteryMonitorBAL
from UI.T27 import BatteryMonitorTem
from UI.T28 import BatteryMonitorBalanceTem
from domain.dbc_runtime import DbcRuntime
from domain.index_catalog import IndexCatalog
from presentation.alarm_parameter_page import AlarmParameterPage
from presentation.balance_control_page import BalanceControlPage
from presentation.cluster_dashboard_page import ClusterDashboardPage
from presentation.cluster_display import (
    cluster_display_number,
    format_cluster_name,
)
from presentation.history_log_page import HistoryLogPage
from presentation.index_browser_dialog import IndexBrowserDialog
from presentation.index_control_page import IndexControlPage
from presentation.index_monitor_page import IndexMonitorPage
from presentation.power_diagnostic_page import PowerDiagnosticPage
from presentation.signal_grid_page import SignalGridPage
from presentation.system_kline_page import SystemKLinePage


def _positive_config_int(runtime_config, key, default, minimum=1):
    try:
        value = int(runtime_config.get(key, default))
    except (TypeError, ValueError):
        value = int(default)
    return max(value, int(minimum))


class MainWindow(Ui_Form, QWidget):
    THEME_PATH = Path(__file__).resolve().parents[1] / "UI" / "release_theme.qss"
    MIN_WINDOW_WIDTH = 1180
    MIN_WINDOW_HEIGHT = 700
    DEFAULT_WINDOW_WIDTH = 1680
    DEFAULT_WINDOW_HEIGHT = 980
    POLL_INTERVAL_MS = 40
    ACTIVE_POLL_INTERVAL_MS = 10
    QUERY_INTERVAL_MS = 20
    BACKGROUND_QUERY_INTERVAL_MS = 80
    ACTIVE_QUERY_BURST_SIZE = 2
    UI_REFRESH_INTERVAL_MS = 50
    COMMUNICATION_TILE_REFRESH_MS = 250
    COMMUNICATION_ACTIVE_TIMEOUT_MS = 2000
    IDLE_QUERY_INTERVAL_MS = 1000
    IDLE_QUERY_BACKOFF_POLLS = 10
    INDEX_READ_INTERVAL_MS = 1000
    INDEX_READ_TIMEOUT_S = 0.05
    DEFAULT_SAVE_INTERVAL_MS = 500
    AUTO_ALARM_READ_TIMEOUT_S = 0.5
    FACTORY_STATUS_READ_TIMEOUT_S = 0.15
    DEFAULT_CLUSTER_ADDRESS = "A0"
    SAVE_SCOPE_CURRENT = "current"
    SAVE_SCOPE_ALL = "all"

    LEGACY_OVERVIEW_PAGE_INDEX = 0
    LEGACY_REQUEST_PAGE_INDEX = 1

    CLUSTER_DASHBOARD_TAB_INDEX = 0
    OVERVIEW_TAB_INDEX = 1
    REQUEST_TAB_INDEX = 2
    REALTIME_MONITOR_TAB_INDEX = 3
    HOST_CONTROL_TAB_INDEX = 4
    ALARM_PARAMETER_TAB_INDEX = 5
    HISTORY_LOG_TAB_INDEX = 6
    DBC_TAB_INDEX = 7
    VOLTAGE_TAB_INDEX = 8
    TEMPERATURE_TAB_INDEX = 9
    BALANCE_TAB_INDEX = 10
    BALANCE_TEMPERATURE_TAB_INDEX = 11
    BALANCE_CONTROL_TAB_INDEX = 12
    ALARM_TAB_INDEX = 13
    TERMINAL_TEMPERATURE_TAB_INDEX = 14
    KLINE_TAB_INDEX = 15
    POWER_DIAGNOSTIC_TAB_INDEX = 16
    CONFIG_TAB_INDEX = 17

    TREND_SIGNAL_METRICS = {
        0x0D: "voltage",
        0x315: "hall_current",
        0x316: "shunt_current",
    }

    PERIODIC_TAB_INDEXES = (
        VOLTAGE_TAB_INDEX,
        TEMPERATURE_TAB_INDEX,
        BALANCE_TAB_INDEX,
        BALANCE_TEMPERATURE_TAB_INDEX,
        BALANCE_CONTROL_TAB_INDEX,
        ALARM_TAB_INDEX,
        TERMINAL_TEMPERATURE_TAB_INDEX,
    )

    PRIORITY_QUERY_TAB_INDEXES = (
        OVERVIEW_TAB_INDEX,
        REQUEST_TAB_INDEX,
        REALTIME_MONITOR_TAB_INDEX,
        HOST_CONTROL_TAB_INDEX,
        BALANCE_TAB_INDEX,
        BALANCE_CONTROL_TAB_INDEX,
        KLINE_TAB_INDEX,
        POWER_DIAGNOSTIC_TAB_INDEX,
        CLUSTER_DASHBOARD_TAB_INDEX,
    )

    ACTIVE_POLL_TAB_INDEXES = (
        OVERVIEW_TAB_INDEX,
        REQUEST_TAB_INDEX,
        REALTIME_MONITOR_TAB_INDEX,
        HOST_CONTROL_TAB_INDEX,
        DBC_TAB_INDEX,
        VOLTAGE_TAB_INDEX,
        TEMPERATURE_TAB_INDEX,
        BALANCE_TAB_INDEX,
        BALANCE_TEMPERATURE_TAB_INDEX,
        BALANCE_CONTROL_TAB_INDEX,
        ALARM_TAB_INDEX,
        TERMINAL_TEMPERATURE_TAB_INDEX,
        KLINE_TAB_INDEX,
        POWER_DIAGNOSTIC_TAB_INDEX,
        CLUSTER_DASHBOARD_TAB_INDEX,
    )

    def __init__(
        self,
        service,
        runtime_config,
        runtime_paths=None,
        product_info=None,
        index_catalog=None,
        connect_on_init=True,
    ):
        super().__init__()
        self.service = service
        self.runtime_config = runtime_config
        self.runtime_paths = runtime_paths
        self.product_info = product_info
        self.index_catalog = index_catalog or IndexCatalog.empty()
        self.debug_ui = bool(runtime_config.get("DEBUG_UI", 0))
        self.snapshot_logging_enabled = bool(
            getattr(service, "snapshot_logging_enabled", True)
        )
        self.snapshot_logging_scope = self._normalize_snapshot_logging_scope(
            runtime_config.get("SAVE_LOG_SCOPE", self.SAVE_SCOPE_CURRENT)
        )
        self.save_interval_ms = int(
            runtime_config.get("SAVE_INTERVAL_MS", self.DEFAULT_SAVE_INTERVAL_MS)
        )
        self.poll_interval_ms = _positive_config_int(
            runtime_config,
            "POLL_INTERVAL_MS",
            self.POLL_INTERVAL_MS,
            minimum=10,
        )
        self.active_poll_interval_ms = _positive_config_int(
            runtime_config,
            "ACTIVE_POLL_INTERVAL_MS",
            self.ACTIVE_POLL_INTERVAL_MS,
            minimum=5,
        )
        self.query_interval_ms = _positive_config_int(
            runtime_config,
            "QUERY_INTERVAL_MS",
            self.QUERY_INTERVAL_MS,
            minimum=10,
        )
        self.background_query_interval_ms = _positive_config_int(
            runtime_config,
            "BACKGROUND_QUERY_INTERVAL_MS",
            self.BACKGROUND_QUERY_INTERVAL_MS,
            minimum=20,
        )
        self.active_query_burst_size = _positive_config_int(
            runtime_config,
            "ACTIVE_QUERY_BURST_SIZE",
            self.ACTIVE_QUERY_BURST_SIZE,
        )
        self.ui_refresh_interval_s = _positive_config_int(
            runtime_config,
            "UI_REFRESH_INTERVAL_MS",
            self.UI_REFRESH_INTERVAL_MS,
            minimum=16,
        ) / 1000.0
        self.communication_tile_refresh_s = _positive_config_int(
            runtime_config,
            "COMMUNICATION_TILE_REFRESH_MS",
            self.COMMUNICATION_TILE_REFRESH_MS,
            minimum=100,
        ) / 1000.0
        self.communication_active_timeout_s = _positive_config_int(
            runtime_config,
            "COMMUNICATION_ACTIVE_TIMEOUT_MS",
            self.COMMUNICATION_ACTIVE_TIMEOUT_MS,
            minimum=500,
        ) / 1000.0
        self.cluster_indices = list(
            getattr(service, "cluster_indices", range(1, len(service.cluster_addresses) + 1))
        )
        self.cluster_addresses = list(service.cluster_addresses)
        self.cluster_options = list(zip(self.cluster_indices, self.cluster_addresses))
        self.cluster_count = len(self.cluster_options)
        if self.cluster_options:
            self.selected_cluster_index, self.selected_address = self.cluster_options[
                self._default_cluster_option_index()
            ]
        else:
            self.selected_cluster_index = None
            self.selected_address = None

        self.trend_store = TrendDataStore()
        self.power_diagnostic_analyzer = PowerDiagnosticAnalyzer()
        self._reset_window_runtime_state()
        self.can_ready = False
        self._dashboard_restore_maximized = False

        self.setupUi(self)
        self._apply_product_identity()
        self._apply_release_window_defaults()
        self._install_product_header()
        self._configure_pages()
        self.tabWidget.setCurrentIndex(self.CLUSTER_DASHBOARD_TAB_INDEX)
        self._connect_ui()
        self._sync_service_active_cluster()
        self._load_bus_config_controls()
        self._refresh_selected_cluster_views(force_periodic=True)
        if connect_on_init:
            self._open_bus(show_dialog=True)

    def schedule_startup_bus_open(self, delay_ms=150):
        QTimer.singleShot(delay_ms, self._open_startup_bus)

    def _open_startup_bus(self):
        if self.can_ready:
            return
        self._set_startup_bus_connecting_status()
        self._open_bus(show_dialog=False)

    def _set_startup_bus_connecting_status(self):
        device_index = self.device_index_spinbox.value()
        channel_index = self.channel_index_spinbox.value()
        text = f"\u6b63\u5728\u8fde\u63a5: dev {device_index} / ch {channel_index}"
        self.bus_status_text = text
        self.bus_status_state = "info"
        self._set_status_pill(self.bus_status_label, text, "info")
        self._set_overview_tile("bus", text, "info")

    def _apply_release_window_defaults(self):
        self.setMinimumSize(self.MIN_WINDOW_WIDTH, self.MIN_WINDOW_HEIGHT)
        self.resize(*self._preferred_initial_window_size())

        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)
            if root_layout.count() >= 3:
                top_spacer = root_layout.itemAt(0).spacerItem()
                bottom_spacer = root_layout.itemAt(root_layout.count() - 1).spacerItem()
                if top_spacer is not None:
                    top_spacer.changeSize(
                        0,
                        0,
                        QSizePolicy.Policy.Minimum,
                        QSizePolicy.Policy.Fixed,
                    )
                if bottom_spacer is not None:
                    bottom_spacer.changeSize(
                        0,
                        0,
                        QSizePolicy.Policy.Minimum,
                        QSizePolicy.Policy.Fixed,
                    )
                middle_layout = root_layout.itemAt(1).layout()
                if middle_layout is not None:
                    middle_layout.setContentsMargins(0, 0, 0, 0)
                    middle_layout.setSpacing(0)
                    if middle_layout.count() >= 3:
                        left_spacer = middle_layout.itemAt(0).spacerItem()
                        right_spacer = middle_layout.itemAt(
                            middle_layout.count() - 1
                        ).spacerItem()
                        if left_spacer is not None:
                            left_spacer.changeSize(
                                0,
                                0,
                                QSizePolicy.Policy.Fixed,
                                QSizePolicy.Policy.Minimum,
                            )
                        if right_spacer is not None:
                            right_spacer.changeSize(
                                0,
                                0,
                                QSizePolicy.Policy.Fixed,
                                QSizePolicy.Policy.Minimum,
                            )
                        middle_layout.setStretch(1, 1)
                root_layout.setStretch(1, 1)
            root_layout.invalidate()

        self.tabWidget.setMinimumSize(0, 0)
        self.tabWidget.setMaximumSize(16777215, 16777215)
        self.tabWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.tabWidget.setStyleSheet("")
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.setUsesScrollButtons(True)
        self.tabWidget.tabBar().setExpanding(False)
        stylesheet = self._load_release_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)

    def _preferred_initial_window_size(self):
        width = self.DEFAULT_WINDOW_WIDTH
        height = self.DEFAULT_WINDOW_HEIGHT
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, max(self.MIN_WINDOW_WIDTH, available.width() - 40))
            height = min(height, max(self.MIN_WINDOW_HEIGHT, available.height() - 60))
        return width, height

    def _default_cluster_option_index(self):
        for option_index, (_, address) in enumerate(self.cluster_options):
            if str(address).upper() == self.DEFAULT_CLUSTER_ADDRESS:
                return option_index
        return 0

    @property
    def selected_cluster_display_name(self):
        return format_cluster_name(
            self.selected_cluster_index,
            self.selected_address,
        )

    @property
    def selected_cluster_display_number(self):
        return cluster_display_number(
            self.selected_cluster_index,
            self.selected_address,
        )

    def _normalize_snapshot_logging_scope(self, scope):
        if str(scope).lower() == self.SAVE_SCOPE_ALL:
            return self.SAVE_SCOPE_ALL
        return self.SAVE_SCOPE_CURRENT

    def _snapshot_logging_scope_text(self):
        if self.snapshot_logging_scope == self.SAVE_SCOPE_ALL:
            return "\u6240\u6709\u7c07"
        return "\u5f53\u524d\u7c07"

    def _uses_all_cluster_snapshot_mode(self):
        return self.snapshot_logging_enabled and (
            self.snapshot_logging_scope == self.SAVE_SCOPE_ALL
        )

    def _apply_product_identity(self):
        if self.product_info is None:
            return
        self.setWindowTitle(
            f"{self.product_info.display_name} {self.product_info.version}"
        )

    def _load_release_stylesheet(self):
        if self.runtime_paths is not None:
            try:
                return self.runtime_paths.theme_path.read_text(encoding="utf-8")
            except OSError:
                return ""
        try:
            return self.THEME_PATH.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _install_product_header(self):
        root_layout = self.layout()
        if root_layout is None:
            self.product_command_layout = None
            return

        self.product_header = QFrame(self)
        self.product_header.setObjectName("productHeader")
        header_layout = QVBoxLayout(self.product_header)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(6)

        identity_row = QHBoxLayout()
        identity_row.setContentsMargins(0, 0, 0, 0)
        identity_row.setSpacing(14)

        brand_block = QWidget(self.product_header)
        brand_block.setObjectName("productBrandBlock")
        brand_layout = QVBoxLayout(brand_block)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)

        display_name = (
            self.product_info.display_name
            if self.product_info is not None
            else "DCBMS CANFD Host"
        )
        product_version = (
            self.product_info.version
            if self.product_info is not None
            else str(self.runtime_config.get("Version", ""))
        )
        self.product_title_label = QLabel("DCBMS", brand_block)
        self.product_title_label.setObjectName("productLogo")
        self.product_subtitle_label = QLabel(
            f"{display_name}  v{product_version}",
            brand_block,
        )
        self.product_subtitle_label.setObjectName("productSubtitle")
        brand_layout.addWidget(self.product_title_label)
        brand_layout.addWidget(self.product_subtitle_label)
        identity_row.addWidget(brand_block, 0)

        profile_text = str(self.runtime_config.get("_CONFIG_PROFILE", "Test_4_10"))
        self.product_context_label = QLabel(
            f"项目: DCBMS    配置: {profile_text}",
            self.product_header,
        )
        self.product_context_label.setObjectName("productContext")
        identity_row.addWidget(self.product_context_label, 0)
        identity_row.addStretch(1)
        header_layout.addLayout(identity_row)

        self.product_command_scroll = QScrollArea(self.product_header)
        self.product_command_scroll.setObjectName("productCommandScroll")
        self.product_command_scroll.setWidgetResizable(False)
        self.product_command_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.product_command_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.product_command_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.product_command_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.product_command_bar = QFrame()
        self.product_command_bar.setObjectName("productCommandBar")
        self.product_command_layout = QHBoxLayout(self.product_command_bar)
        self.product_command_layout.setContentsMargins(0, 0, 0, 0)
        self.product_command_layout.setSpacing(8)
        self.product_command_scroll.setWidget(self.product_command_bar)
        self.product_command_scroll.setMinimumHeight(58)
        header_layout.addWidget(self.product_command_scroll)

        root_layout.insertWidget(0, self.product_header)

    def _set_dynamic_status(self, widget, status):
        if widget is None:
            return
        if widget.property("status") == status:
            return
        widget.setProperty("status", status)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _set_status_pill(self, label, text, status):
        if label.text() != text:
            label.setText(text)
        if label.styleSheet():
            label.setStyleSheet("")
        self._set_dynamic_status(label, status)

    def _build_overview_tile(self, parent, key, title, value="--", status="neutral"):
        tile = QFrame(parent)
        tile.setObjectName("overviewTile")
        tile.setMinimumHeight(96)
        self._set_dynamic_status(tile, status)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(16, 14, 16, 14)
        tile_layout.setSpacing(6)

        title_label = QLabel(title, tile)
        title_label.setObjectName("overviewTileTitle")
        value_label = QLabel(value, tile)
        value_label.setObjectName("overviewTileValue")
        value_label.setWordWrap(True)

        tile_layout.addWidget(title_label)
        tile_layout.addWidget(value_label)
        tile_layout.addStretch(1)

        self.overview_tiles[key] = tile
        self.overview_tile_values[key] = value_label
        return tile

    def _set_overview_tile(self, key, value, status="neutral"):
        if not hasattr(self, "overview_tile_values"):
            return
        value_label = self.overview_tile_values.get(key)
        tile = self.overview_tiles.get(key)
        if value_label is None or tile is None:
            return
        text = str(value)
        if value_label.text() != text:
            value_label.setText(text)
        self._set_dynamic_status(tile, status)

    def _configure_pages(self):
        self._configure_overview_page()
        self._configure_request_page()
        self._configure_compact_tabs()
        self._setup_top_controls()
        self._create_index_monitor_page()
        self._create_index_control_page()
        self._create_alarm_parameter_page()
        self._create_history_log_page()
        self._create_dbc_page()
        self._create_periodic_pages()
        self._create_kline_page()
        self._create_power_diagnostic_page()
        self._create_config_page()
        self._create_cluster_dashboard_page()
        self.cluster_dashboard_page.cluster_activated.connect(
            self.on_cluster_dashboard_activated
        )
        self.cluster_dashboard_page.fullscreen_requested.connect(
            self.on_cluster_dashboard_fullscreen_requested
        )
        self.periodic_tab_refreshers = {
            self.VOLTAGE_TAB_INDEX: self._refresh_voltage_page,
            self.TEMPERATURE_TAB_INDEX: self._refresh_temperature_page,
            self.BALANCE_TAB_INDEX: self._refresh_balance_page,
            self.BALANCE_TEMPERATURE_TAB_INDEX: self._refresh_balance_temperature_page,
            self.BALANCE_CONTROL_TAB_INDEX: self._refresh_balance_control_page,
            self.ALARM_TAB_INDEX: self._refresh_alarm_page,
            self.TERMINAL_TEMPERATURE_TAB_INDEX: self._refresh_terminal_temperature_page,
        }

    def _style_data_table(self, table_widget):
        table_widget.setAlternatingRowColors(True)
        table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        table_widget.setShowGrid(False)
        table_widget.setWordWrap(False)
        table_widget.verticalHeader().setVisible(False)
        table_widget.verticalHeader().setDefaultSectionSize(30)
        header = table_widget.horizontalHeader()
        header.setHighlightSections(False)
        header.setMinimumSectionSize(72)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    def _style_request_table(self, table_widget):
        self._style_data_table(table_widget)
        table_widget.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        table_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        table_widget.setWordWrap(False)
        header = table_widget.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table_widget.setColumnWidth(0, 280)
        table_widget.setColumnWidth(1, 100)
        table_widget.setColumnWidth(2, 420)

    def _configure_overview_page(self):
        for table in self.TW[self.LEGACY_OVERVIEW_PAGE_INDEX]:
            table.hide()
        for label in self.label[self.LEGACY_OVERVIEW_PAGE_INDEX]:
            label.hide()

        page = self.tab[self.LEGACY_OVERVIEW_PAGE_INDEX]
        layout = page.layout()
        if layout is None:
            layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        overview_panel = QFrame(page)
        overview_panel.setObjectName("overviewPanel")
        panel_layout = QVBoxLayout(overview_panel)
        panel_layout.setContentsMargins(24, 22, 24, 24)
        panel_layout.setSpacing(16)

        overview_title = QLabel("系统概览", overview_panel)
        overview_title.setObjectName("pageTitle")
        panel_layout.addWidget(overview_title)

        self.overview_tiles = {}
        self.overview_tile_values = {}
        tile_grid = QGridLayout()
        tile_grid.setHorizontalSpacing(12)
        tile_grid.setVerticalSpacing(12)
        tile_specs = (
            ("cluster", "\u5f53\u524d\u7c07"),
            ("bus", "CAN FD \u63a5\u53e3"),
            ("communication", "\u62a5\u6587\u6536\u53d1"),
            ("factory", "\u5de5\u88c5\u6a21\u5f0f"),
            ("log", "\u65e5\u5fd7\u8bb0\u5f55"),
            ("periodic", "\u5468\u671f\u6570\u636e"),
        )
        for tile_index, (key, title) in enumerate(tile_specs):
            tile_grid.addWidget(
                self._build_overview_tile(
                    overview_panel,
                    key,
                    title,
                ),
                tile_index // 3,
                tile_index % 3,
            )
        for column_index in range(3):
            tile_grid.setColumnStretch(column_index, 1)
        panel_layout.addLayout(tile_grid)

        self.overview_label = QLabel(overview_panel)
        self.overview_label.setObjectName("overviewCard")
        self.overview_label.setWordWrap(True)
        panel_layout.addWidget(self.overview_label)

        layout.addWidget(overview_panel)
        layout.addStretch(1)

    def _configure_request_page(self):
        self.request_group_definitions = self._read_request_groups_from_service()
        request_table_count = len(self.TW[self.LEGACY_REQUEST_PAGE_INDEX])
        section_titles = [
            f"\u8bf7\u6c42\u5206\u7ec4 {index + 1}"
            for index in range(max(3, min(request_table_count, len(self.request_group_definitions))))
        ]
        page = self.tab[self.LEGACY_REQUEST_PAGE_INDEX]
        layout = page.layout()
        if layout is None:
            layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        request_panel = QFrame(page)
        request_panel.setObjectName("dataSectionCard")
        panel_layout = QVBoxLayout(request_panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)

        request_title = QLabel("\u8bf7\u6c42\u6570\u636e", request_panel)
        request_title.setObjectName("pageTitle")
        panel_layout.addWidget(request_title)

        request_hint = QLabel(
            "\u5207\u6362\u5206\u7ec4\u67e5\u770b\u8bf7\u6c42\u53d8\u91cf\uff0c\u957f\u5b57\u6bb5\u652f\u6301\u6a2a\u5411\u6eda\u52a8\u548c\u60ac\u505c\u5b8c\u6574\u63d0\u793a\u3002",
            request_panel,
        )
        request_hint.setObjectName("sectionHint")
        request_hint.setWordWrap(True)
        panel_layout.addWidget(request_hint)

        config_toolbar = QHBoxLayout()
        config_toolbar.setSpacing(8)
        self.request_config_toggle_button = QPushButton("\u7f16\u8f91\u5f53\u524d\u5206\u7ec4", request_panel)
        config_toolbar.addWidget(self.request_config_toggle_button)
        self.request_config_add_button = QPushButton("\u65b0\u589e\u7d22\u5f15", request_panel)
        config_toolbar.addWidget(self.request_config_add_button)
        self.request_config_remove_button = QPushButton("\u5220\u9664\u9009\u4e2d", request_panel)
        config_toolbar.addWidget(self.request_config_remove_button)
        self.request_config_browse_button = QPushButton("\u6d4f\u89c8\u7d22\u5f15", request_panel)
        config_toolbar.addWidget(self.request_config_browse_button)
        self.request_config_apply_button = QPushButton("\u5e94\u7528\u8fd0\u884c", request_panel)
        self.request_config_apply_button.setObjectName("primaryButton")
        self.request_config_apply_button.setProperty("role", "primary")
        config_toolbar.addWidget(self.request_config_apply_button)
        self.request_config_save_button = QPushButton("\u4fdd\u5b58\u5230\u914d\u7f6e", request_panel)
        config_toolbar.addWidget(self.request_config_save_button)
        self.request_config_default_button = QPushButton("\u6062\u590d\u9ed8\u8ba4", request_panel)
        config_toolbar.addWidget(self.request_config_default_button)
        config_toolbar.addStretch(1)
        panel_layout.addLayout(config_toolbar)

        self.request_config_status_label = QLabel("", request_panel)
        self.request_config_status_label.setObjectName("sectionHint")
        self.request_config_status_label.setWordWrap(True)
        panel_layout.addWidget(self.request_config_status_label)

        self.request_config_table = QTableWidget(request_panel)
        self.request_config_table.setColumnCount(4)
        self.request_config_table.setHorizontalHeaderLabels(
            ["\u7d22\u5f15", "HEX", "\u4fe1\u53f7\u540d\u79f0", "\u5355\u4f4d/\u8bf4\u660e"]
        )
        self._style_data_table(self.request_config_table)
        self.request_config_table.setEditTriggers(
            QAbstractItemView.EditTrigger.AllEditTriggers
        )
        self.request_config_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.request_config_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.request_config_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        self.request_config_table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.request_config_table.setMinimumHeight(160)
        panel_layout.addWidget(self.request_config_table)

        self.request_group_tabs = QTabWidget(request_panel)
        self.request_group_tabs.setObjectName("requestGroupTabs")
        panel_layout.addWidget(self.request_group_tabs, stretch=1)
        layout.addWidget(request_panel)

        for table_index, title in enumerate(section_titles):
            label = self.label[self.LEGACY_REQUEST_PAGE_INDEX][table_index]
            table = self.TW[self.LEGACY_REQUEST_PAGE_INDEX][table_index]

            label.hide()
            self._style_request_table(table)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setMinimumWidth(0)
            table.setHorizontalHeaderLabels(["\u4fe1\u53f7", "\u503c", "\u5355\u4f4d/\u8bf4\u660e"])

            tab_page = QWidget(self.request_group_tabs)
            tab_layout = QVBoxLayout(tab_page)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab_layout.setSpacing(0)
            tab_layout.addWidget(table)
            self.request_group_tabs.addTab(tab_page, title)
        self.request_config_editor_visible = False
        self.request_config_loading = False
        self.request_groups_default_mode = self.runtime_config.get("REQUEST_GROUPS") is None
        self._set_request_config_editor_visible(False)
        self._rebuild_request_group_tables()
        self._load_request_config_editor(0)

    def _request_group_table_count(self):
        return len(self.TW[self.LEGACY_REQUEST_PAGE_INDEX])

    def _read_request_groups_from_service(self):
        getter = getattr(self.service, "get_request_group_definitions", None)
        raw_groups = getter() if callable(getter) else self.runtime_config.get("REQUEST_GROUPS", [])
        groups = []
        if isinstance(raw_groups, list):
            for raw_group in raw_groups[: self._request_group_table_count()]:
                group = []
                if isinstance(raw_group, list):
                    for raw_entry in raw_group:
                        entry = self._normalize_request_group_entry(raw_entry)
                        if entry is not None:
                            group.append(entry)
                groups.append(group)
        while len(groups) < min(3, self._request_group_table_count()):
            groups.append([])
        return groups

    def _normalize_request_group_entry(self, raw_entry):
        if raw_entry is None or raw_entry == "":
            return None
        if isinstance(raw_entry, dict):
            raw_index = raw_entry.get(
                "index",
                raw_entry.get("signal_id", raw_entry.get("data_id")),
            )
            name = str(raw_entry.get("name") or "")
            unit = str(raw_entry.get("unit") or "")
            signed = raw_entry.get("signed")
            bit_start = int(raw_entry.get("bit_start", 0) or 0)
            bit_length = int(raw_entry.get("bit_length", 16) or 16)
            row_index = raw_entry.get("row_index")
        else:
            raw_index = raw_entry
            name = ""
            unit = ""
            signed = None
            bit_start = 0
            bit_length = 16
            row_index = None
        try:
            data_id = int(str(raw_index), 0)
        except (TypeError, ValueError):
            return None
        entry = self._resolve_request_group_entry(data_id, name=name, unit=unit, signed=signed)
        entry["bit_start"] = bit_start
        entry["bit_length"] = bit_length
        if row_index is not None:
            entry["row_index"] = int(row_index)
        return entry

    def _resolve_request_group_entry(self, data_id, name="", unit="", signed=None):
        resolution = None
        if self.index_catalog is not None and not self.index_catalog.is_empty:
            resolution = self.index_catalog.resolve(data_id, self.runtime_config)
        resolved_name = name
        resolved_unit = unit
        resolved_signed = bool(signed) if signed is not None else False
        if resolution is not None:
            resolved_name = resolved_name or resolution.short_name
            resolved_unit = resolved_unit or resolution.unit
            if signed is None:
                resolved_signed = bool(resolution.signed)
        if not resolved_name:
            resolved_name = f"索引 0x{int(data_id):X}"
        return {
            "index": int(data_id),
            "name": resolved_name,
            "unit": resolved_unit,
            "signed": resolved_signed,
            "bit_start": 0,
            "bit_length": 16,
        }

    def _request_group_config_payload(self):
        return [
            [
                {
                    "index": int(entry["index"]),
                    "name": str(entry.get("name", "")),
                    "unit": str(entry.get("unit", "")),
                    "signed": bool(entry.get("signed", False)),
                    "bit_start": int(entry.get("bit_start", 0)),
                    "bit_length": int(entry.get("bit_length", 16)),
                }
                for entry in group
            ]
            for group in self.request_group_definitions
        ]

    def _set_request_config_editor_visible(self, visible):
        visible = bool(visible)
        self.request_config_editor_visible = visible
        self.request_config_table.setVisible(visible)
        self.request_config_status_label.setVisible(visible)
        for button in (
            self.request_config_add_button,
            self.request_config_remove_button,
            self.request_config_browse_button,
            self.request_config_apply_button,
            self.request_config_save_button,
            self.request_config_default_button,
        ):
            button.setVisible(visible)
        self.request_config_toggle_button.setText(
            "收起配置" if visible else "编辑当前分组"
        )

    def _create_request_config_item(self, value="", editable=True):
        item = QTableWidgetItem("" if value is None else str(value))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _load_request_config_editor(self, group_index):
        if not hasattr(self, "request_config_table"):
            return
        self.request_config_group_index = max(0, int(group_index))
        if self.request_config_group_index >= len(self.request_group_definitions):
            self.request_config_group_index = len(self.request_group_definitions) - 1
        if self.request_config_group_index < 0:
            self.request_config_group_index = 0

        entries = (
            self.request_group_definitions[self.request_config_group_index]
            if self.request_group_definitions
            else []
        )
        self.request_config_loading = True
        try:
            self.request_config_table.setRowCount(len(entries))
            for row_index, entry in enumerate(entries):
                self.request_config_table.setItem(
                    row_index,
                    0,
                    self._create_request_config_item(entry.get("index", "")),
                )
                self.request_config_table.setItem(
                    row_index,
                    1,
                    self._create_request_config_item(
                        f"0x{int(entry['index']):X}",
                        editable=False,
                    ),
                )
                self.request_config_table.setItem(
                    row_index,
                    2,
                    self._create_request_config_item(entry.get("name", "")),
                )
                self.request_config_table.setItem(
                    row_index,
                    3,
                    self._create_request_config_item(entry.get("unit", "")),
                )
        finally:
            self.request_config_loading = False
        self._set_label_text(
            self.request_config_status_label,
            f"当前编辑: 请求分组 {self.request_config_group_index + 1}",
        )

    def _request_config_table_text(self, row_index, column_index):
        item = self.request_config_table.item(row_index, column_index)
        return "" if item is None else item.text().strip()

    def _request_config_entries_from_table(self):
        entries = []
        for row_index in range(self.request_config_table.rowCount()):
            index_text = self._request_config_table_text(row_index, 0)
            if not index_text:
                continue
            try:
                data_id = int(index_text, 0)
            except ValueError as exc:
                raise ValueError(
                    f"请求分组 {self.request_config_group_index + 1} 第 {row_index + 1} 行索引格式错误。"
                ) from exc
            name = self._request_config_table_text(row_index, 2)
            unit = self._request_config_table_text(row_index, 3)
            entries.append(
                self._resolve_request_group_entry(
                    data_id,
                    name=name,
                    unit=unit,
                )
            )
        return entries

    def _commit_request_config_editor(self):
        if not hasattr(self, "request_config_table"):
            return
        if self.request_config_group_index < 0:
            return
        while len(self.request_group_definitions) <= self.request_config_group_index:
            self.request_group_definitions.append([])
        self.request_group_definitions[self.request_config_group_index] = (
            self._request_config_entries_from_table()
        )

    def _update_request_config_row_from_index(self, row_index, fill_empty_fields=True):
        index_text = self._request_config_table_text(row_index, 0)
        hex_item = self.request_config_table.item(row_index, 1)
        if hex_item is None:
            hex_item = self._create_request_config_item("", editable=False)
            self.request_config_table.setItem(row_index, 1, hex_item)
        if not index_text:
            hex_item.setText("--")
            return
        try:
            data_id = int(index_text, 0)
        except ValueError:
            hex_item.setText("ERR")
            return
        hex_item.setText(f"0x{data_id:X}")
        if not fill_empty_fields:
            return
        entry = self._resolve_request_group_entry(data_id)
        name_item = self.request_config_table.item(row_index, 2)
        unit_item = self.request_config_table.item(row_index, 3)
        if name_item is None:
            name_item = self._create_request_config_item("")
            self.request_config_table.setItem(row_index, 2, name_item)
        if unit_item is None:
            unit_item = self._create_request_config_item("")
            self.request_config_table.setItem(row_index, 3, unit_item)
        if not name_item.text().strip():
            name_item.setText(entry["name"])
        if not unit_item.text().strip():
            unit_item.setText(entry["unit"])

    def _rebuild_request_group_tables(self):
        table_count = self._request_group_table_count()
        for table_index in range(table_count):
            table = self.TW[self.LEGACY_REQUEST_PAGE_INDEX][table_index]
            definitions = (
                self.request_group_definitions[table_index]
                if table_index < len(self.request_group_definitions)
                else []
            )
            table.clearContents()
            if definitions:
                table.setRowCount(
                    max(int(entry.get("row_index", row_index)) for row_index, entry in enumerate(definitions))
                    + 1
                )
            else:
                table.setRowCount(0)
            for row_index, entry in enumerate(definitions):
                display_row = int(entry.get("row_index", row_index))
                self._set_table_item_text(table, display_row, 0, entry.get("name", ""))
                self._set_table_item_text(table, display_row, 1, "")
                unit = str(entry.get("unit", ""))
                index_text = f"0x{int(entry['index']):X}"
                detail = f"{unit} / {index_text}" if unit else index_text
                self._set_table_item_text(table, display_row, 2, detail)

    def on_request_group_tab_changed(self, group_index):
        if not hasattr(self, "request_config_table"):
            return
        if self.request_config_editor_visible:
            try:
                self._commit_request_config_editor()
            except ValueError as exc:
                QMessageBox.warning(self, "请求分组配置错误", str(exc))
                self.request_group_tabs.blockSignals(True)
                self.request_group_tabs.setCurrentIndex(self.request_config_group_index)
                self.request_group_tabs.blockSignals(False)
                return
        self._load_request_config_editor(group_index)

    def on_request_config_toggle(self):
        visible = not self.request_config_editor_visible
        self._set_request_config_editor_visible(visible)
        if visible:
            self._load_request_config_editor(self.request_group_tabs.currentIndex())

    def on_request_config_add(self):
        self.request_groups_default_mode = False
        row_index = self.request_config_table.rowCount()
        self.request_config_table.insertRow(row_index)
        self.request_config_table.setItem(row_index, 0, self._create_request_config_item(""))
        self.request_config_table.setItem(
            row_index,
            1,
            self._create_request_config_item("--", editable=False),
        )
        self.request_config_table.setItem(row_index, 2, self._create_request_config_item(""))
        self.request_config_table.setItem(row_index, 3, self._create_request_config_item(""))
        self.request_config_table.selectRow(row_index)

    def on_request_config_remove(self):
        self.request_groups_default_mode = False
        rows = sorted(
            {index.row() for index in self.request_config_table.selectedIndexes()},
            reverse=True,
        )
        for row_index in rows:
            self.request_config_table.removeRow(row_index)

    def on_request_config_browse(self):
        if self.index_catalog is None or self.index_catalog.is_empty:
            QMessageBox.warning(
                self,
                "索引目录不可用",
                "索引目录不可用，请检查发布资源 index_catalog.json。",
            )
            return
        row_index = self.request_config_table.currentRow()
        if row_index < 0:
            self.on_request_config_add()
            row_index = self.request_config_table.currentRow()
        dialog = IndexBrowserDialog(self.index_catalog, self.runtime_config, parent=self)
        current_text = self._request_config_table_text(row_index, 0)
        if current_text:
            dialog.set_initial_query(current_text)
        dialog.indexSelected.connect(
            lambda data_id, row_index=row_index: self._apply_request_browser_selection(
                row_index,
                data_id,
            )
        )
        dialog.exec()

    def _apply_request_browser_selection(self, row_index, data_id):
        self.request_groups_default_mode = False
        self.request_config_table.setItem(
            row_index,
            0,
            self._create_request_config_item(str(int(data_id))),
        )
        self.request_config_table.setItem(row_index, 2, self._create_request_config_item(""))
        self.request_config_table.setItem(row_index, 3, self._create_request_config_item(""))
        self._update_request_config_row_from_index(row_index)

    def on_request_config_item_changed(self, item):
        if self.request_config_loading or item is None:
            return
        self.request_groups_default_mode = False
        if item.column() == 0:
            self.request_config_loading = True
            try:
                self._update_request_config_row_from_index(item.row())
            finally:
                self.request_config_loading = False

    def _apply_request_groups_config(self, use_default=False):
        if use_default:
            payload = None
        else:
            self._commit_request_config_editor()
            payload = self._request_group_config_payload()
        self.runtime_config["REQUEST_GROUPS"] = payload
        update_runtime_config = getattr(self.service, "update_runtime_config", None)
        if callable(update_runtime_config):
            update_runtime_config({"REQUEST_GROUPS": payload})
        else:
            self.service.runtime_config["REQUEST_GROUPS"] = payload
        self.request_group_definitions = self._read_request_groups_from_service()
        self.legacy_cache = {cluster_index: {} for cluster_index in self.cluster_indices}
        self._reset_query_cursors()
        self._rebuild_request_group_tables()
        self._load_request_config_editor(self.request_group_tabs.currentIndex())
        self._refresh_request_page()
        self._update_query_timer_state()

    def on_request_config_apply(self):
        try:
            self.request_groups_default_mode = False
            self._apply_request_groups_config(use_default=False)
        except Exception as exc:
            QMessageBox.warning(self, "请求分组配置错误", str(exc))
            return False
        self._set_label_text(
            self.request_config_status_label,
            "请求分组配置已应用到当前运行。",
        )
        return True

    def on_request_config_save(self):
        use_default = bool(getattr(self, "request_groups_default_mode", False))
        try:
            self._apply_request_groups_config(use_default=use_default)
            if self.runtime_paths is None:
                raise RuntimeError("当前没有可写入的运行配置路径。")
            profile = str(self.runtime_config.get("_CONFIG_PROFILE", self.runtime_paths.profile))
            saved_config = save_runtime_config_fields(
                self.runtime_paths.config_path,
                profile,
                {"REQUEST_GROUPS": None if use_default else self._request_group_config_payload()},
            )
            self.runtime_config.update(saved_config)
        except Exception as exc:
            QMessageBox.warning(self, "请求分组保存失败", str(exc))
            return False
        self._set_label_text(
            self.request_config_status_label,
            f"请求分组配置已保存: {self.runtime_paths.config_path}",
        )
        return True

    def on_request_config_restore_default(self):
        self.request_groups_default_mode = True
        self._apply_request_groups_config(use_default=True)
        self._set_label_text(
            self.request_config_status_label,
            "已恢复默认请求分组；需要持久化时点击“保存到配置”。",
        )

    def _configure_compact_tabs(self):
        while self.tabWidget.count():
            self.tabWidget.removeTab(0)

        self.tabWidget.addTab(
            self.tab[self.LEGACY_OVERVIEW_PAGE_INDEX],
            "\u603b\u89c8",
        )
        self.tabWidget.addTab(
            self.tab[self.LEGACY_REQUEST_PAGE_INDEX],
            "\u8bf7\u6c42\u6570\u636e",
        )

    def _setup_top_controls(self):
        corner_widget = QWidget(self.tabWidget)
        corner_widget.setObjectName("topControlBar")
        layout = getattr(self, "product_command_layout", None)
        if layout is None:
            layout = QHBoxLayout(corner_widget)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(8)
        else:
            corner_widget.setVisible(False)

        control_parent = (
            self.product_command_bar
            if layout is self.product_command_layout
            else corner_widget
        )

        cluster_label = QLabel("\u5f53\u524d\u7c07", control_parent)
        cluster_label.setObjectName("fieldCaption")
        layout.addWidget(cluster_label)
        self.cluster_selector = QComboBox(control_parent)
        self.cluster_selector.setMinimumWidth(130)
        for cluster_index, address in self.cluster_options:
            self.cluster_selector.addItem(
                format_cluster_name(cluster_index, address),
                cluster_index,
            )
        if self.cluster_count:
            self.cluster_selector.setCurrentIndex(self._default_cluster_option_index())
        else:
            self.cluster_selector.setEnabled(False)
        layout.addWidget(self.cluster_selector)

        layout.addSpacing(8)
        device_label = QLabel("\u8bbe\u5907", control_parent)
        device_label.setObjectName("fieldCaption")
        layout.addWidget(device_label)
        self.device_index_spinbox = QSpinBox(control_parent)
        self.device_index_spinbox.setRange(0, 31)
        self.device_index_spinbox.setMinimumWidth(64)
        layout.addWidget(self.device_index_spinbox)

        channel_label = QLabel("\u901a\u9053", control_parent)
        channel_label.setObjectName("fieldCaption")
        layout.addWidget(channel_label)
        self.channel_index_spinbox = QSpinBox(control_parent)
        self.channel_index_spinbox.setRange(0, 31)
        self.channel_index_spinbox.setMinimumWidth(64)
        layout.addWidget(self.channel_index_spinbox)

        self.save_log_checkbox = QCheckBox("\u65e5\u5fd7", control_parent)
        layout.addWidget(self.save_log_checkbox)

        scope_label = QLabel("\u8303\u56f4", control_parent)
        scope_label.setObjectName("fieldCaption")
        layout.addWidget(scope_label)
        self.save_scope_selector = QComboBox(control_parent)
        self.save_scope_selector.setMinimumWidth(96)
        self.save_scope_selector.addItem(
            "\u5f53\u524d\u7c07",
            self.SAVE_SCOPE_CURRENT,
        )
        self.save_scope_selector.addItem(
            "\u6240\u6709\u7c07",
            self.SAVE_SCOPE_ALL,
        )
        layout.addWidget(self.save_scope_selector)

        interval_label = QLabel("\u95f4\u9694", control_parent)
        interval_label.setObjectName("fieldCaption")
        layout.addWidget(interval_label)
        self.save_interval_spinbox = QSpinBox(control_parent)
        self.save_interval_spinbox.setRange(100, 60000)
        self.save_interval_spinbox.setSingleStep(100)
        self.save_interval_spinbox.setSuffix(" ms")
        self.save_interval_spinbox.setMinimumWidth(92)
        layout.addWidget(self.save_interval_spinbox)

        self.apply_bus_button = QPushButton(
            "\u5e94\u7528\u5e76\u91cd\u8fde",
            control_parent,
        )
        self.apply_bus_button.setObjectName("primaryButton")
        self.apply_bus_button.setProperty("role", "primary")
        layout.addWidget(self.apply_bus_button)

        self.factory_mode_on_button = QPushButton("\u5de5\u88c5\u5f00", control_parent)
        self.factory_mode_on_button.setEnabled(bool(self.cluster_count))
        layout.addWidget(self.factory_mode_on_button)

        self.factory_mode_off_button = QPushButton("\u5de5\u88c5\u5173", control_parent)
        self.factory_mode_off_button.setEnabled(bool(self.cluster_count))
        layout.addWidget(self.factory_mode_off_button)

        self.factory_mode_status_label = QLabel(control_parent)
        self.factory_mode_status_label.setObjectName("statusPill")
        self.factory_mode_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.factory_mode_status_label.setMinimumWidth(120)
        layout.addWidget(self.factory_mode_status_label)

        self.bus_status_label = QLabel(control_parent)
        self.bus_status_label.setObjectName("statusPill")
        self.bus_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bus_status_label.setMinimumWidth(180)
        layout.addWidget(self.bus_status_label)

        self.log_status_label = QLabel(control_parent)
        self.log_status_label.setObjectName("statusPill")
        self.log_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_status_label.setMinimumWidth(100)
        layout.addWidget(self.log_status_label)

        if layout is not self.product_command_layout:
            self.tabWidget.setCornerWidget(corner_widget)
        else:
            self.product_command_bar.adjustSize()
        self._update_factory_mode_status_label()
        self._update_log_status_label()

    def _create_alarm_parameter_page(self):
        self.alarm_parameter_page = AlarmParameterPage(
            self.service.get_alarm_parameter_definitions(),
            self.service.get_alarm_parameter_fields(),
        )
        self._style_data_table(self.alarm_parameter_page.alarm_table)
        self.alarm_parameter_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.tabWidget.addTab(self.alarm_parameter_page, "\u544a\u8b66\u53c2\u6570")

    def _create_history_log_page(self):
        self.history_log_page = HistoryLogPage()
        self.history_log_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self._style_data_table(self.history_log_page.table)
        self.history_log_page.table.horizontalHeader().setStretchLastSection(False)
        self.tabWidget.addTab(self.history_log_page, "\u5386\u53f2\u65e5\u5fd7")

    def _create_index_monitor_page(self):
        self.index_monitor_page = IndexMonitorPage()
        self.index_monitor_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.tabWidget.addTab(self.index_monitor_page, "\u5b9e\u65f6\u76d1\u63a7")

    def _create_index_control_page(self):
        self.index_control_page = IndexControlPage(
            index_catalog=self.index_catalog,
            runtime_config=self.runtime_config,
        )
        self.index_control_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.tabWidget.addTab(self.index_control_page, "\u4e3b\u673a\u63a7\u5236")

    def _create_dbc_page(self):
        self.dbc_page = QWidget()
        layout = QVBoxLayout(self.dbc_page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        dbc_title = QLabel("DBC 周期解析", self.dbc_page)
        dbc_title.setObjectName("pageTitle")
        layout.addWidget(dbc_title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.dbc_source_label = QLabel(self.dbc_page)
        self.dbc_source_label.setObjectName("contextLabel")
        self.dbc_source_label.setWordWrap(True)
        toolbar.addWidget(self.dbc_source_label, stretch=1)
        self.dbc_load_button = QPushButton("加载DBC", self.dbc_page)
        toolbar.addWidget(self.dbc_load_button)
        layout.addLayout(toolbar)

        self.dbc_status_label = QLabel(self.dbc_page)
        self.dbc_status_label.setObjectName("sectionHint")
        self.dbc_status_label.setWordWrap(True)
        layout.addWidget(self.dbc_status_label)

        self.dbc_table = QTableWidget(self.dbc_page)
        self.dbc_table.setColumnCount(4)
        self.dbc_table.setHorizontalHeaderLabels(
            ["\u62a5\u6587", "\u4fe1\u53f7", "\u503c", "\u5355\u4f4d"]
        )
        self.dbc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._style_data_table(self.dbc_table)
        self.dbc_table.horizontalHeader().setDefaultSectionSize(220)
        self.dbc_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.dbc_table)

        self.tabWidget.addTab(self.dbc_page, "DBC\u5468\u671f")
        self._update_dbc_source_label()

    def _create_periodic_pages(self, insert_index=None):
        module_group_count = int(
            self.runtime_config.get(
                "LECU_NUM",
                self.runtime_config.get("BALANCE_MODULE_COUNT", 4),
            )
        )
        voltage_count = int(self.runtime_config.get("CELL_NUM", 104))
        temperature_count = int(self.runtime_config.get("CELL_Tem_NUM", voltage_count))
        balance_cells_per_module = int(
            self.runtime_config.get("BALANCE_CELLS_PER_MODULE", voltage_count)
        )
        balance_temperature_per_module = int(
            self.runtime_config.get("BALANCE_TEMP_PER_MODULE", 8)
        )

        self.voltage_page = BatteryMonitor(
            group_count=module_group_count,
            values_per_group=voltage_count,
        )
        self.temperature_page = BatteryMonitorTem(
            group_count=module_group_count,
            values_per_group=temperature_count,
        )
        self.balance_page = BatteryMonitorBAL(
            group_count=module_group_count,
            values_per_group=balance_cells_per_module,
        )
        self.balance_temperature_page = BatteryMonitorBalanceTem(
            group_count=module_group_count,
            values_per_group=balance_temperature_per_module,
        )
        self.balance_control_page = BalanceControlPage(
            group_count=module_group_count,
            values_per_group=balance_cells_per_module,
        )
        self.balance_control_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.alarm_page = SignalGridPage(
            "\u544a\u8b66\u72b6\u6001",
            items_per_row=4,
            color_mode="alarm",
        )
        self.terminal_temperature_page = SignalGridPage(
            "\u6781\u67f1\u6e29\u5ea6",
            items_per_row=4,
            color_mode="extrema",
        )

        periodic_tabs = [
            (self.voltage_page, "\u5355\u4f53\u7535\u538b"),
            (self.temperature_page, "\u5355\u4f53\u6e29\u5ea6"),
            (self.balance_page, "\u5747\u8861\u72b6\u6001"),
            (self.balance_temperature_page, "\u5747\u8861\u6e29\u5ea6"),
            (self.balance_control_page, "\u5747\u8861\u63a7\u5236"),
            (self.alarm_page, "\u544a\u8b66\u72b6\u6001"),
            (self.terminal_temperature_page, "\u6781\u67f1\u6e29\u5ea6"),
        ]
        for offset, (page, title) in enumerate(periodic_tabs):
            if insert_index is None:
                self.tabWidget.addTab(page, title)
            else:
                self.tabWidget.insertTab(insert_index + offset, page, title)

    def _create_kline_page(self):
        self.kline_page = SystemKLinePage(self.trend_store)
        self.kline_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.tabWidget.addTab(self.kline_page, "\u603b\u538b\u7535\u6d41K\u7ebf")

    def _create_power_diagnostic_page(self):
        self.power_diagnostic_page = PowerDiagnosticPage()
        self.power_diagnostic_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.tabWidget.addTab(self.power_diagnostic_page, "上下电诊断")

    def _create_config_page(self):
        self.config_page = QWidget()
        layout = QVBoxLayout(self.config_page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("CONFIG 基本参数", self.config_page)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        panel = QFrame(self.config_page)
        panel.setObjectName("dataSectionCard")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        panel_layout.addLayout(grid)

        self.config_spinboxes = {}
        spinbox_fields = [
            ("BCU_NUM", "簇数量", 0, 32, ""),
            ("LECU_NUM", "每簇模组数", 1, 64, ""),
            ("CELL_NUM", "单模组电芯数", 1, 512, ""),
            ("CELL_Tem_NUM", "单模组温度数", 1, 512, ""),
            ("BALANCE_CELLS_PER_MODULE", "均衡单模组电芯数", 1, 512, ""),
            ("BALANCE_TEMP_PER_MODULE", "单模组均衡温度数", 1, 64, ""),
        ]
        for row_index, field in enumerate(spinbox_fields):
            key, label_text, minimum, maximum, suffix = field
            label = QLabel(label_text, panel)
            label.setObjectName("fieldCaption")
            grid.addWidget(label, row_index, 0)
            spinbox = QSpinBox(panel)
            spinbox.setRange(minimum, maximum)
            spinbox.setMinimumWidth(150)
            if suffix:
                spinbox.setSuffix(suffix)
            grid.addWidget(spinbox, row_index, 1)
            self.config_spinboxes[key] = spinbox

        self.config_bau_addr_edit = QLineEdit(panel)
        self.config_bau_addr_edit.setMaxLength(4)
        self.config_bau_addr_edit.setMinimumWidth(150)
        grid.addWidget(QLabel("BAU 地址", panel), 0, 2)
        grid.addWidget(self.config_bau_addr_edit, 0, 3)

        self.config_ipc_addr_edit = QLineEdit(panel)
        self.config_ipc_addr_edit.setMaxLength(4)
        self.config_ipc_addr_edit.setMinimumWidth(150)
        grid.addWidget(QLabel("IPC 地址", panel), 1, 2)
        grid.addWidget(self.config_ipc_addr_edit, 1, 3)

        address_label = QLabel("簇地址列表（00=未编制簇）", panel)
        address_label.setObjectName("fieldCaption")
        grid.addWidget(address_label, 2, 2)
        self.config_address_list_edit = QLineEdit(panel)
        self.config_address_list_edit.setPlaceholderText("00, A0, A1")
        grid.addWidget(self.config_address_list_edit, 2, 3, 1, 2)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.config_apply_button = QPushButton("应用配置", panel)
        self.config_apply_button.setObjectName("primaryButton")
        self.config_apply_button.setProperty("role", "primary")
        button_row.addWidget(self.config_apply_button)
        self.config_save_button = QPushButton("保存到 conf.yaml", panel)
        button_row.addWidget(self.config_save_button)
        self.config_reload_button = QPushButton("恢复当前值", panel)
        button_row.addWidget(self.config_reload_button)
        button_row.addStretch(1)
        panel_layout.addLayout(button_row)

        self.config_status_label = QLabel(panel)
        self.config_status_label.setObjectName("sectionHint")
        self.config_status_label.setWordWrap(True)
        panel_layout.addWidget(self.config_status_label)

        layout.addWidget(panel)
        layout.addStretch(1)
        self.tabWidget.addTab(self.config_page, "CONFIG")

    def _create_cluster_dashboard_page(self):
        self.cluster_dashboard_page = ClusterDashboardPage()
        self.tabWidget.insertTab(
            self.CLUSTER_DASHBOARD_TAB_INDEX,
            self.cluster_dashboard_page,
            "全簇大屏",
        )
        self._load_config_controls()

    def _load_config_controls(self):
        for key, spinbox in self.config_spinboxes.items():
            default_value = self.runtime_config.get("CELL_NUM", 1)
            if key == "BALANCE_CELLS_PER_MODULE":
                default_value = self.runtime_config.get(key, default_value)
            elif key == "BALANCE_TEMP_PER_MODULE":
                default_value = self.runtime_config.get(key, 8)
            else:
                default_value = self.runtime_config.get(key, spinbox.minimum())
            spinbox.blockSignals(True)
            spinbox.setValue(int(default_value))
            spinbox.blockSignals(False)

        self.config_bau_addr_edit.setText(str(self.runtime_config.get("BAUaddr", "EF")))
        self.config_ipc_addr_edit.setText(str(self.runtime_config.get("IPCaddr", "F2")))
        self.config_address_list_edit.setText(
            ", ".join(str(address) for address in self.runtime_config.get("ADDRESLIST", []))
        )
        self._set_label_text(self.config_status_label, "CONFIG 基本参数已加载。")

    def _normalize_hex_byte_text(self, value, field_name):
        text = str(value).strip().upper()
        if text.startswith("0X"):
            text = text[2:]
        if not text:
            raise ValueError(f"{field_name} 不能为空。")
        try:
            number = int(text, 16)
        except ValueError as exc:
            raise ValueError(f"{field_name} 必须是 00-FF 的十六进制地址。") from exc
        if number < 0 or number > 0xFF:
            raise ValueError(f"{field_name} 必须在 00-FF 范围内。")
        return f"{number:02X}"

    def _parse_config_address_list(self):
        text = self.config_address_list_edit.text()
        normalized = text.replace("，", ",").replace(";", ",").replace("\n", ",")
        tokens = []
        for part in normalized.split(","):
            tokens.extend(part.split())
        addresses = [
            self._normalize_hex_byte_text(token, "簇地址列表")
            for token in tokens
        ]
        if not addresses:
            raise ValueError("簇地址列表不能为空。")
        return addresses

    def _read_basic_config_controls(self):
        values = {
            key: spinbox.value()
            for key, spinbox in self.config_spinboxes.items()
        }
        values["BAUaddr"] = self._normalize_hex_byte_text(
            self.config_bau_addr_edit.text(),
            "BAU 地址",
        )
        values["IPCaddr"] = self._normalize_hex_byte_text(
            self.config_ipc_addr_edit.text(),
            "IPC 地址",
        )
        addresses = self._parse_config_address_list()
        required_address_count = int(values["BCU_NUM"])
        numbered_addresses = [address for address in addresses if address != "00"]
        if len(numbered_addresses) < required_address_count:
            raise ValueError(
                f"簇地址列表至少需要 {required_address_count} 个编制地址，"
                f"当前只有 {len(numbered_addresses)} 个；00 为未编制簇，不计入簇数量。"
            )
        values["ADDRESLIST"] = addresses
        values["ADDRESLIST0x"] = [f"0x{address}" for address in addresses]
        return values

    def _apply_basic_config_values(self, values):
        previous_cluster_index = self.selected_cluster_index
        previous_bus_status = self.bus_status_text
        previous_bus_state = self.bus_status_state
        was_can_ready = self.can_ready

        self.runtime_config.update(values)
        update_runtime_config = getattr(self.service, "update_runtime_config", None)
        if callable(update_runtime_config):
            update_runtime_config(values)
        else:
            self.service.runtime_config.update(values)

        self._stop_index_control_auto_read()
        self._reload_cluster_options(previous_cluster_index)
        self._reset_window_runtime_state()
        self.bus_status_text = previous_bus_status
        self.bus_status_state = previous_bus_state
        self.can_ready = was_can_ready
        self._sync_service_active_cluster()
        self._rebuild_periodic_pages_from_config()
        self._update_factory_mode_status_label()
        self._refresh_factory_mode_status()
        self._refresh_selected_cluster_views(force_periodic=True)
        self._reset_query_cursors()
        self._update_query_timer_state()
        self._update_save_timer_state()
        self._update_alarm_parameter_controls()
        self._update_balance_control_controls()

    def _reload_cluster_options(self, preferred_cluster_index=None):
        self.cluster_indices = list(
            getattr(self.service, "cluster_indices", range(1, len(self.service.cluster_addresses) + 1))
        )
        self.cluster_addresses = list(self.service.cluster_addresses)
        self.cluster_options = list(zip(self.cluster_indices, self.cluster_addresses))
        self.cluster_count = len(self.cluster_options)

        selected_option_index = -1
        for option_index, (cluster_index, _) in enumerate(self.cluster_options):
            if cluster_index == preferred_cluster_index:
                selected_option_index = option_index
                break
        if selected_option_index < 0 and self.cluster_count:
            selected_option_index = self._default_cluster_option_index()

        self.cluster_selector.blockSignals(True)
        self.cluster_selector.clear()
        for cluster_index, address in self.cluster_options:
            self.cluster_selector.addItem(
                format_cluster_name(cluster_index, address),
                cluster_index,
            )
        self.cluster_selector.setEnabled(bool(self.cluster_count))
        if selected_option_index >= 0:
            self.cluster_selector.setCurrentIndex(selected_option_index)
            self.selected_cluster_index, self.selected_address = self.cluster_options[
                selected_option_index
            ]
        else:
            self.selected_cluster_index = None
            self.selected_address = None
        self.cluster_selector.blockSignals(False)

        has_cluster = bool(self.cluster_count)
        self.factory_mode_on_button.setEnabled(has_cluster)
        self.factory_mode_off_button.setEnabled(has_cluster)

    def _rebuild_periodic_pages_from_config(self):
        current_widget = self.tabWidget.currentWidget()
        periodic_widgets = [
            getattr(self, "voltage_page", None),
            getattr(self, "temperature_page", None),
            getattr(self, "balance_page", None),
            getattr(self, "balance_temperature_page", None),
            getattr(self, "balance_control_page", None),
            getattr(self, "alarm_page", None),
            getattr(self, "terminal_temperature_page", None),
        ]
        removed_current_widget = current_widget in periodic_widgets
        for widget in periodic_widgets:
            if widget is None:
                continue
            tab_index = self.tabWidget.indexOf(widget)
            if tab_index >= 0:
                self.tabWidget.removeTab(tab_index)
            widget.deleteLater()

        self._create_periodic_pages(insert_index=self.VOLTAGE_TAB_INDEX)
        self.balance_control_page.cellToggleRequested.connect(
            self.on_balance_control_cell_toggled
        )
        if removed_current_widget:
            self.tabWidget.setCurrentIndex(self.VOLTAGE_TAB_INDEX)
        elif self.tabWidget.indexOf(current_widget) >= 0:
            self.tabWidget.setCurrentWidget(current_widget)

    def on_apply_basic_config(self):
        try:
            values = self._read_basic_config_controls()
            self._apply_basic_config_values(values)
        except Exception as exc:
            self._set_label_text(self.config_status_label, f"CONFIG 应用失败: {exc}")
            QMessageBox.warning(self, "CONFIG 应用失败", str(exc))
            return False

        self._set_label_text(self.config_status_label, "CONFIG 基本参数已应用到当前运行态。")
        return True

    def on_save_basic_config(self):
        try:
            values = self._read_basic_config_controls()
            self._apply_basic_config_values(values)
            if self.runtime_paths is None:
                raise RuntimeError("当前没有可写入的运行配置路径。")
            profile = str(self.runtime_config.get("_CONFIG_PROFILE", self.runtime_paths.profile))
            saved_config = save_runtime_config_fields(
                self.runtime_paths.config_path,
                profile,
                values,
            )
            self.runtime_config.update(saved_config)
        except Exception as exc:
            self._set_label_text(self.config_status_label, f"CONFIG 保存失败: {exc}")
            QMessageBox.warning(self, "CONFIG 保存失败", str(exc))
            return False

        self._set_label_text(
            self.config_status_label,
            f"CONFIG 基本参数已保存: {self.runtime_paths.config_path}",
        )
        return True

    def _connect_ui(self):
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.cluster_selector.currentIndexChanged.connect(self.on_cluster_changed)
        self.apply_bus_button.clicked.connect(self.on_apply_bus_settings)
        self.config_apply_button.clicked.connect(self.on_apply_basic_config)
        self.config_save_button.clicked.connect(self.on_save_basic_config)
        self.config_reload_button.clicked.connect(self._load_config_controls)
        self.request_group_tabs.currentChanged.connect(self.on_request_group_tab_changed)
        self.request_config_toggle_button.clicked.connect(self.on_request_config_toggle)
        self.request_config_add_button.clicked.connect(self.on_request_config_add)
        self.request_config_remove_button.clicked.connect(self.on_request_config_remove)
        self.request_config_browse_button.clicked.connect(self.on_request_config_browse)
        self.request_config_apply_button.clicked.connect(self.on_request_config_apply)
        self.request_config_save_button.clicked.connect(self.on_request_config_save)
        self.request_config_default_button.clicked.connect(
            self.on_request_config_restore_default
        )
        self.request_config_table.itemChanged.connect(self.on_request_config_item_changed)
        self.factory_mode_on_button.clicked.connect(self.on_factory_mode_enable)
        self.factory_mode_off_button.clicked.connect(self.on_factory_mode_disable)
        self.save_log_checkbox.toggled.connect(self.on_save_log_toggled)
        self.save_scope_selector.currentIndexChanged.connect(self.on_save_scope_changed)
        self.save_interval_spinbox.valueChanged.connect(self.on_save_interval_changed)
        self.alarm_parameter_page.read_summary_button.clicked.connect(
            self.on_alarm_parameter_read_summary
        )
        self.alarm_parameter_page.write_current_button.clicked.connect(
            self.on_alarm_parameter_write_current
        )
        self.alarm_parameter_page.restore_button.clicked.connect(
            self.on_alarm_parameter_restore
        )
        self.alarm_parameter_page.save_flash_button.clicked.connect(
            self.on_alarm_parameter_save_flash
        )
        self.alarm_parameter_page.alarm_table.itemSelectionChanged.connect(
            self.on_alarm_parameter_selection_changed
        )
        self.power_diagnostic_page.refreshRequested.connect(
            self.on_power_diagnostic_refresh
        )
        self.history_log_page.read_button.clicked.connect(
            self.on_history_log_read
        )
        self.history_log_page.stop_button.clicked.connect(
            self.on_history_log_stop
        )
        self.history_log_page.save_button.clicked.connect(
            self.on_history_log_save
        )
        self.history_log_page.clear_table_button.clicked.connect(
            self.on_history_log_clear_table
        )
        self.history_log_page.clear_device_button.clicked.connect(
            self.on_history_log_clear_device
        )
        self.index_control_page.read_indexes_button.clicked.connect(
            self.on_index_control_read_indexes
        )
        self.index_control_page.write_indexes_button.clicked.connect(
            self.on_index_control_write_indexes
        )
        self.index_control_page.write_hvil_button.clicked.connect(
            self.on_index_control_write_hvil
        )
        self.index_control_page.write_soc_button.clicked.connect(
            self.on_index_control_write_soc
        )
        self.index_control_page.restore_factory_button.clicked.connect(
            self.on_index_control_restore_factory
        )
        self.index_control_page.restore_run_button.clicked.connect(
            self.on_index_control_restore_run
        )
        self.index_control_page.restore_product_info_button.clicked.connect(
            self.on_index_control_restore_product_info
        )
        self.index_control_page.save_flash_button.clicked.connect(
            self.on_index_control_save_flash
        )
        self.index_control_page.sync_time_button.clicked.connect(
            self.on_index_control_sync_time
        )
        self.balance_control_page.cellToggleRequested.connect(
            self.on_balance_control_cell_toggled
        )
        self.dbc_load_button.clicked.connect(self.on_load_dbc_file)
        for channel_id, checkbox in self.index_control_page.channel_checks.items():
            checkbox.toggled.connect(
                lambda checked, channel_id=channel_id: self.on_index_control_channel_toggled(
                    channel_id,
                    checked,
                )
            )

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.on_poll_timer)
        self.query_timer = QTimer(self)
        self.query_timer.timeout.connect(self.on_query_timer)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.on_save_timer)
        self.index_read_timer = QTimer(self)
        self.index_read_timer.setInterval(self.INDEX_READ_INTERVAL_MS)
        self.index_read_timer.timeout.connect(self.on_index_control_read_timer)
        self._update_alarm_parameter_controls()

    def _load_bus_config_controls(self):
        bus_config = getattr(self.service, "bus_config", None)
        device_index = int(
            getattr(bus_config, "device_index", self.runtime_config.get("DEVICE_INDEX", 0))
        )
        channel_index = int(
            getattr(bus_config, "channel_index", self.runtime_config.get("CHANNEL_INDEX", 0))
        )
        self.device_index_spinbox.setValue(device_index)
        self.channel_index_spinbox.setValue(channel_index)
        self.save_log_checkbox.blockSignals(True)
        self.save_log_checkbox.setChecked(self.snapshot_logging_enabled)
        self.save_log_checkbox.blockSignals(False)
        self.save_scope_selector.blockSignals(True)
        save_scope_index = self.save_scope_selector.findData(self.snapshot_logging_scope)
        if save_scope_index >= 0:
            self.save_scope_selector.setCurrentIndex(save_scope_index)
        self.save_scope_selector.blockSignals(False)
        self.save_interval_spinbox.blockSignals(True)
        self.save_interval_spinbox.setValue(self.save_interval_ms)
        self.save_interval_spinbox.blockSignals(False)
        self._set_bus_status(False, device_index, channel_index)
        self._update_log_status_label()

    def _open_bus(self, show_dialog):
        device_index = self.device_index_spinbox.value()
        channel_index = self.channel_index_spinbox.value()

        try:
            self.service.open()
        except Exception as exc:
            self.can_ready = False
            self._stop_bus_timers()
            self._set_factory_mode_status(None)
            self._set_bus_status(False, device_index, channel_index, failed=True)
            self._update_alarm_parameter_controls()
            if show_dialog:
                self._show_bus_error(
                    "\u6253\u5f00",
                    device_index,
                    channel_index,
                    exc,
                )
            return False

        self.can_ready = True
        self._update_poll_timer_state()
        self._update_save_timer_state()
        self._update_query_timer_state()
        self._set_bus_status(True, device_index, channel_index)
        self._refresh_factory_mode_status()
        self._update_alarm_parameter_controls()
        return True

    def on_apply_bus_settings(self):
        device_index = self.device_index_spinbox.value()
        channel_index = self.channel_index_spinbox.value()

        self.runtime_config["DEVICE_INDEX"] = device_index
        self.runtime_config["CHANNEL_INDEX"] = channel_index
        self._stop_bus_timers()
        self.can_ready = False

        self._reset_window_runtime_state()
        self._update_factory_mode_status_label()
        self._refresh_selected_cluster_views(force_periodic=True)
        self._update_alarm_parameter_controls()

        self.service.update_bus_config(
            device_index=device_index,
            channel_index=channel_index,
        )

        try:
            self.service.reopen()
        except Exception as exc:
            self._set_factory_mode_status(None)
            self._set_bus_status(False, device_index, channel_index, failed=True)
            self._update_alarm_parameter_controls()
            self._show_bus_error(
                "\u91cd\u8fde",
                device_index,
                channel_index,
                exc,
            )
            return

        self.can_ready = True
        self._update_poll_timer_state()
        self._update_save_timer_state()
        self._update_query_timer_state()
        self._set_bus_status(True, device_index, channel_index)
        self._refresh_factory_mode_status()
        self._refresh_selected_cluster_views(force_periodic=True)
        self._update_alarm_parameter_controls()

    def on_save_log_toggled(self, checked):
        enabled = bool(checked)
        self.snapshot_logging_enabled = enabled
        self.runtime_config["SAVE_LOG"] = 1 if enabled else 0
        if hasattr(self.service, "set_snapshot_logging_enabled"):
            self.service.set_snapshot_logging_enabled(enabled)
        else:
            self.service.snapshot_logging_enabled = enabled
        self._sync_service_active_cluster()
        self._reset_query_cursors()
        self._update_query_timer_state()
        self._update_save_timer_state()
        self._update_log_status_label()
        self._refresh_overview()

    def on_save_scope_changed(self, combo_index):
        if combo_index < 0:
            return
        scope = self.save_scope_selector.itemData(combo_index)
        self.snapshot_logging_scope = self._normalize_snapshot_logging_scope(scope)
        self.runtime_config["SAVE_LOG_SCOPE"] = self.snapshot_logging_scope
        self._sync_service_active_cluster()
        self._reset_query_cursors()
        self._update_query_timer_state()
        self._update_log_status_label()
        self._refresh_overview()

    def on_save_interval_changed(self, value):
        self.save_interval_ms = int(value)
        self.runtime_config["SAVE_INTERVAL_MS"] = self.save_interval_ms
        self._update_save_timer_state()
        self._update_log_status_label()
        self._refresh_overview()

    def on_factory_mode_enable(self):
        self._change_factory_mode(True)

    def on_factory_mode_disable(self):
        self._change_factory_mode(False)

    def _change_factory_mode(self, enabled, show_dialog=True):
        if not self.can_ready:
            if show_dialog:
                QMessageBox.warning(self, "CANFD \u672a\u8fde\u63a5", "CANFD \u672a\u8fde\u63a5\uff0c\u65e0\u6cd5\u5207\u6362\u5de5\u88c5\u6a21\u5f0f\u3002")
            return False
        if self.selected_cluster_index is None:
            if show_dialog:
                QMessageBox.warning(self, "\u672a\u9009\u62e9\u7c07", "\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u7684\u7c07\u3002")
            return False

        try:
            with self._bus_command_busy_state():
                work_mode = self.service.set_factory_test_mode(
                    self.selected_cluster_index,
                    enabled,
                )
        except Exception as exc:
            self._set_factory_mode_status(None)
            if show_dialog:
                QMessageBox.critical(
                    self,
                    "\u5de5\u88c5\u6a21\u5f0f\u5207\u6362\u5931\u8d25",
                    (
                        f"{self.selected_cluster_display_name} "
                        f"\u5de5\u88c5\u6a21\u5f0f\u5207\u6362\u5931\u8d25\u3002\n\n{exc}"
                    ),
                )
            return False

        self._set_factory_mode_status(work_mode)
        if show_dialog:
            action_text = (
                "\u5f00\u542f"
                if work_mode == 1
                else "\u5173\u95ed"
            )
            QMessageBox.information(
                self,
                "\u5de5\u88c5\u6a21\u5f0f",
                (
                    f"{self.selected_cluster_display_name} "
                    f"\u5de5\u88c5\u6a21\u5f0f\u5df2{action_text}\u3002"
                ),
            )
        return True

    def _refresh_factory_mode_status(self, show_error=False):
        if not self.can_ready or self.selected_cluster_index is None:
            self._set_factory_mode_status(None)
            return None

        try:
            with self._bus_command_busy_state():
                try:
                    work_mode = self.service.read_factory_test_mode(
                        self.selected_cluster_index,
                        timeout_s=self.FACTORY_STATUS_READ_TIMEOUT_S,
                    )
                except TypeError:
                    work_mode = self.service.read_factory_test_mode(
                        self.selected_cluster_index
                    )
        except Exception as exc:
            self._set_factory_mode_status(None)
            if show_error:
                QMessageBox.warning(
                    self,
                    "\u5de5\u88c5\u72b6\u6001",
                    (
                        f"{self.selected_cluster_display_name} "
                        f"\u5de5\u88c5\u72b6\u6001\u8bfb\u53d6\u5931\u8d25\u3002\n\n{exc}"
                    ),
                )
            return None

        self._set_factory_mode_status(work_mode)
        return work_mode

    def _set_factory_mode_status(self, work_mode):
        self.factory_mode_status_value = work_mode
        if work_mode == 1:
            self.factory_mode_status_text = "\u5f00"
        elif work_mode == 0:
            self.factory_mode_status_text = "\u5173"
        else:
            self.factory_mode_status_text = "\u672a\u77e5"
        self._update_factory_mode_status_label()
        self._refresh_overview()
        self._update_alarm_parameter_controls()
        self._update_balance_control_controls()

    def _update_factory_mode_status_label(self):
        if not hasattr(self, "factory_mode_status_label"):
            return

        if self.factory_mode_status_value == 1:
            text = "\u5de5\u88c5\u72b6\u6001: \u5f00"
            status = "warning"
        elif self.factory_mode_status_value == 0:
            text = "\u5de5\u88c5\u72b6\u6001: \u5173"
            status = "neutral"
        else:
            text = "\u5de5\u88c5\u72b6\u6001: \u672a\u77e5"
            status = "warning"

        self._set_status_pill(self.factory_mode_status_label, text, status)

    def _update_log_status_label(self):
        if not hasattr(self, "log_status_label"):
            return
        if self.snapshot_logging_enabled:
            text = f"\u65e5\u5fd7: \u5f00 / {self._snapshot_logging_scope_text()}"
            status = "success"
        else:
            text = "\u65e5\u5fd7: \u5173"
            status = "neutral"
        self._set_status_pill(self.log_status_label, text, status)

    def _show_bus_error(self, action, device_index, channel_index, exc):
        QMessageBox.critical(
            self,
            f"CANFD {action}\u5931\u8d25",
            (
                f"CANFD {action}\u5931\u8d25\u3002\n\n"
                f"device_index={device_index}\n"
                f"channel_index={channel_index}\n\n"
                f"{exc}\n\n"
                "\u8bf7\u786e\u8ba4\uff1a\n"
                "1. \u9002\u914d\u5668\u5df2\u8fde\u63a5\u4e14\u9a71\u52a8\u6b63\u5e38\n"
                "2. \u6ca1\u6709\u5176\u4ed6\u7a0b\u5e8f\u5360\u7528\u8be5\u8bbe\u5907\n"
                "3. \u6240\u9009\u7684\u8bbe\u5907\u53f7\u548c\u901a\u9053\u53f7\u6b63\u786e"
            ),
        )

    def _set_bus_status(self, connected, device_index, channel_index, failed=False):
        if connected:
            text = (
                f"\u5df2\u8fde\u63a5: "
                f"dev {device_index} / ch {channel_index}"
            )
            status = "success"
        elif failed:
            text = (
                f"\u8fde\u63a5\u5931\u8d25: "
                f"dev {device_index} / ch {channel_index}"
            )
            status = "danger"
        else:
            text = (
                f"\u672a\u8fde\u63a5: "
                f"dev {device_index} / ch {channel_index}"
            )
            status = "neutral"

        self.bus_status_text = text
        self.bus_status_state = status
        self._set_status_pill(self.bus_status_label, text, status)
        self._set_overview_tile("bus", text, status)
        if hasattr(self, "last_communication_tile_refresh_at"):
            self._refresh_communication_tile_if_due(force=True)

    def _stop_bus_timers(self):
        self.poll_timer.stop()
        self.query_timer.stop()
        self.save_timer.stop()
        self._stop_index_control_auto_read()

    @contextmanager
    def _bus_command_busy_state(self, disable_alarm_controls=False):
        poll_was_active = self.poll_timer.isActive()
        save_was_active = self.save_timer.isActive()
        index_read_was_active = (
            hasattr(self, "index_read_timer") and self.index_read_timer.isActive()
        )
        poll_interval = self.poll_timer.interval() or self.poll_interval_ms
        save_interval = self.save_timer.interval() or self.save_interval_ms
        self.poll_timer.stop()
        self.query_timer.stop()
        self.save_timer.stop()
        if index_read_was_active:
            self.index_read_timer.stop()
        if disable_alarm_controls:
            self._set_alarm_parameter_buttons_enabled(False)
            self.alarm_parameter_page.alarm_table.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        flush_rx_backlog = getattr(self.service, "flush_rx_backlog", None)
        if callable(flush_rx_backlog):
            flush_rx_backlog()
        poll_once = getattr(self.service, "poll", None)
        if callable(poll_once):
            for _ in range(3):
                poll_result = poll_once()
                if not getattr(poll_result, "had_rx_frame", False):
                    break
        try:
            yield
        finally:
            if disable_alarm_controls:
                self.alarm_parameter_page.alarm_table.setEnabled(True)
            if poll_was_active and self.can_ready:
                self.poll_timer.start(poll_interval)
            if save_was_active and self.can_ready and self.snapshot_logging_enabled:
                self.save_timer.start(save_interval)
            if index_read_was_active and self.can_ready:
                self.index_read_timer.start(self.INDEX_READ_INTERVAL_MS)
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._update_poll_timer_state()
            self._update_query_timer_state()
            self._update_alarm_parameter_controls()

    @contextmanager
    def _alarm_parameter_busy_state(self):
        with self._bus_command_busy_state(disable_alarm_controls=True):
            yield

    def _set_alarm_parameter_buttons_enabled(self, enabled):
        self.alarm_parameter_page.read_summary_button.setEnabled(bool(enabled))
        self.alarm_parameter_page.write_current_button.setEnabled(bool(enabled))
        self.alarm_parameter_page.restore_button.setEnabled(bool(enabled))
        self.alarm_parameter_page.save_flash_button.setEnabled(bool(enabled))

    def _update_alarm_parameter_controls(self):
        has_cluster = self.selected_cluster_index is not None
        has_alarm_selection = self.alarm_parameter_page.current_alarm_id() is not None
        factory_mode_enabled = self.factory_mode_status_value == 1
        can_read = self.can_ready and has_cluster
        can_write = (
            can_read
            and has_alarm_selection
            and self.alarm_parameter_page.has_complete_current_record()
        )
        can_save = can_write

        self.alarm_parameter_page.read_summary_button.setEnabled(can_read)
        self.alarm_parameter_page.write_current_button.setEnabled(can_write)
        self.alarm_parameter_page.restore_button.setEnabled(can_read)
        self.alarm_parameter_page.save_flash_button.setEnabled(can_save)
        if can_write and not factory_mode_enabled:
            self.alarm_parameter_page.write_current_button.setToolTip(
                "当前工装模式未开启，点击后可自动开启并继续写入。"
            )
            self.alarm_parameter_page.save_flash_button.setToolTip(
                "当前工装模式未开启，点击后可自动开启并继续保存到 FLASH。"
            )
        else:
            self.alarm_parameter_page.write_current_button.setToolTip("")
            self.alarm_parameter_page.save_flash_button.setToolTip("")
        if can_read and not factory_mode_enabled:
            self.alarm_parameter_page.restore_button.setToolTip(
                "当前工装模式未开启，点击后可自动开启并继续恢复。"
            )
        else:
            self.alarm_parameter_page.restore_button.setToolTip("")

    def _update_balance_control_controls(self):
        if not hasattr(self, "balance_control_page"):
            return
        can_manual_control = (
            self.can_ready
            and self.selected_cluster_index is not None
            and self.factory_mode_status_value == 1
        )
        self.balance_control_page.set_manual_enabled(can_manual_control)

    def _reset_alarm_parameter_page(self):
        self.alarm_parameter_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.history_log_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self.alarm_parameter_page.clear_cached_values()
        self.alarm_parameter_page.set_status_text(
            self.alarm_parameter_page.default_status_text()
        )
        self._update_alarm_parameter_controls()

    def _current_alarm_parameter_alarm_id(self):
        alarm_id = self.alarm_parameter_page.current_alarm_id()
        if alarm_id is not None:
            return alarm_id
        QMessageBox.warning(
            self,
            "\u672a\u9009\u62e9\u544a\u8b66",
            "\u8bf7\u5148\u5728\u8868\u683c\u4e2d\u9009\u62e9\u4e00\u6761\u544a\u8b66\u3002",
        )
        return None

    def _ensure_alarm_parameter_write_ready(self):
        if not self.can_ready:
            QMessageBox.warning(
                self,
                "CANFD \u672a\u8fde\u63a5",
                "CANFD \u672a\u8fde\u63a5\uff0c\u65e0\u6cd5\u4fee\u6539\u544a\u8b66\u53c2\u6570\u3002",
            )
            return False
        if self.selected_cluster_index is None:
            QMessageBox.warning(
                self,
                "\u672a\u9009\u62e9\u7c07",
                "\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u7684\u7c07\u3002",
            )
            return False
        if not self.alarm_parameter_page.has_complete_current_record():
            QMessageBox.warning(
                self,
                "\u544a\u8b66\u53c2\u6570\u672a\u8bfb\u53d6\u5b8c\u6574",
                "\u8bf7\u5148\u9009\u4e2d\u4e00\u6761\u544a\u8b66\uff0c\u7b49\u5f85\u81ea\u52a8\u8bfb\u53d6\u5b8c\u6574\u53c2\u6570\u540e\u518d\u5199\u5165\u3002",
            )
            return False
        if self.factory_mode_status_value != 1:
            reply = QMessageBox.question(
                self,
                "\u5de5\u88c5\u6a21\u5f0f\u672a\u5f00\u542f",
                (
                    f"{self.selected_cluster_display_name} "
                    "\u5f53\u524d\u5de5\u88c5\u6a21\u5f0f\u672a\u5f00\u542f\u3002\n\n"
                    "\u662f\u5426\u73b0\u5728\u5f00\u542f\u5de5\u88c5\u6a21\u5f0f\u5e76\u7ee7\u7eed\uff1f"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            if not self._change_factory_mode(True, show_dialog=False):
                return False
            if self.factory_mode_status_value != 1:
                QMessageBox.warning(
                    self,
                    "\u5de5\u88c5\u6a21\u5f0f\u672a\u5f00\u542f",
                    "\u5de5\u88c5\u6a21\u5f0f\u5f00\u542f\u5931\u8d25\uff0c\u65e0\u6cd5\u7ee7\u7eed\u5199\u5165\u6216\u4fdd\u5b58\u544a\u8b66\u53c2\u6570\u3002",
                )
                return False
        return True

    def _ensure_bcu_factory_restore_ready(self):
        if not self.can_ready:
            QMessageBox.warning(
                self,
                "CANFD 未连接",
                "CANFD 未连接，无法恢复BCU出厂默认参数。",
            )
            return False
        if self.selected_cluster_index is None:
            QMessageBox.warning(
                self,
                "未选择簇",
                "当前没有可用的簇。",
            )
            return False
        if self.factory_mode_status_value != 1:
            reply = QMessageBox.question(
                self,
                "工装模式未开启",
                (
                    f"{self.selected_cluster_display_name} "
                    "当前工装模式未开启。\n\n"
                    "是否现在开启工装模式并继续恢复BCU出厂默认参数？"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            if not self._change_factory_mode(True, show_dialog=False):
                return False
            if self.factory_mode_status_value != 1:
                QMessageBox.warning(
                    self,
                    "工装模式未开启",
                    "工装模式开启失败，无法继续恢复BCU出厂默认参数。",
                )
                return False
        return True

    def on_alarm_parameter_read_summary(self):
        if not self.can_ready or self.selected_cluster_index is None:
            QMessageBox.warning(
                self,
                "CANFD \u672a\u5c31\u7eea",
                "\u8bf7\u5148\u8fde\u63a5 CANFD \u5e76\u9009\u62e9\u76ee\u6807\u7c07\u3002",
            )
            return
        try:
            with self._alarm_parameter_busy_state():
                records = self.service.read_alarm_parameter_summary(
                    self.selected_cluster_index
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "\u8bfb\u53d6\u544a\u8b66\u53c2\u6570\u5931\u8d25",
                str(exc),
            )
            return
        self.alarm_parameter_page.set_summary_records(records)
        self.alarm_parameter_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                "\u544a\u8b66\u8868\u683c\u53c2\u6570\u5df2\u8bfb\u53d6\u3002"
            )
        )

    def _load_alarm_parameter_record(self, alarm_id, auto_trigger=False):
        if not self.can_ready or self.selected_cluster_index is None:
            if not auto_trigger:
                QMessageBox.warning(
                    self,
                    "CANFD \u672a\u5c31\u7eea",
                    "\u8bf7\u5148\u8fde\u63a5 CANFD \u5e76\u9009\u62e9\u76ee\u6807\u7c07\u3002",
                )
            return None
        if alarm_id is None:
            return None
        message_title = (
            "\u81ea\u52a8\u8bfb\u53d6\u544a\u8b66\u5931\u8d25"
            if auto_trigger
            else "\u8bfb\u53d6\u5f53\u524d\u544a\u8b66\u5931\u8d25"
        )
        status_prefix = (
            "\u81ea\u52a8\u8bfb\u53d6\u5931\u8d25"
            if auto_trigger
            else "\u8bfb\u53d6\u5931\u8d25"
        )
        try:
            with self._alarm_parameter_busy_state():
                record = self.service.read_alarm_parameter_record(
                    self.selected_cluster_index,
                    alarm_id,
                    timeout_s=(
                        self.AUTO_ALARM_READ_TIMEOUT_S
                        if auto_trigger
                        else 1.0
                    ),
                )
        except Exception as exc:
            if auto_trigger:
                self.alarm_parameter_page.set_status_text(
                    (
                        f"{self.selected_cluster_display_name} "
                        f"{status_prefix}: {exc}"
                    )
                )
            else:
                QMessageBox.critical(
                    self,
                    message_title,
                    str(exc),
                )
            return None
        self.alarm_parameter_page.set_detail_record(record)
        self.alarm_parameter_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"{record.code} {record.name} \u53c2\u6570\u5df2\u8bfb\u53d6\u3002"
            )
        )
        return record

    def on_alarm_parameter_selection_changed(self):
        self.alarm_parameter_page.on_table_selection_changed()
        self._update_alarm_parameter_controls()
        if getattr(self.alarm_parameter_page, "_ignore_table_selection", False):
            return
        alarm_id = self.alarm_parameter_page.current_alarm_id()
        if alarm_id is None:
            return
        record = self._load_alarm_parameter_record(alarm_id, auto_trigger=True)
        if record is not None:
            self._update_alarm_parameter_controls()

    def on_alarm_parameter_write_current(self):
        if not self._ensure_alarm_parameter_write_ready():
            return
        record = self.alarm_parameter_page.build_current_record()
        if record is None:
            QMessageBox.warning(
                self,
                "\u672a\u9009\u62e9\u544a\u8b66",
                "\u8bf7\u5148\u5728\u8868\u683c\u4e2d\u9009\u62e9\u4e00\u6761\u544a\u8b66\u3002",
            )
            return
        validation_errors = self.alarm_parameter_page.validate_record(record)
        if validation_errors:
            QMessageBox.warning(
                self,
                "\u544a\u8b66\u53c2\u6570\u4e0d\u5408\u6cd5",
                "\n".join(validation_errors),
            )
            return
        try:
            with self._alarm_parameter_busy_state():
                self.service.write_alarm_parameter_record(
                    self.selected_cluster_index,
                    record,
                )
                record = self.service.read_alarm_parameter_record(
                    self.selected_cluster_index,
                    record.alarm_id,
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "\u5199\u5165\u544a\u8b66\u53c2\u6570\u5931\u8d25",
                str(exc),
            )
            return
        self.alarm_parameter_page.set_detail_record(record)
        self.alarm_parameter_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"{record.code} {record.name} \u53c2\u6570\u5df2\u5199\u5165\u3002"
            )
        )

    def on_alarm_parameter_restore(self):
        if not self._ensure_bcu_factory_restore_ready():
            return
        reply = QMessageBox.question(
            self,
            "恢复BCU出厂默认参数",
            (
                f"确认将{self.selected_cluster_display_name} "
                "的BCU参数恢复为出厂默认值？\n\n"
                "该操作会恢复系统参数、LECU参数和告警参数，并立即写入FLASH。\n"
                "操作不可撤销，恢复后请重新读取并核对设备参数。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with self._alarm_parameter_busy_state():
                self.service.restore_factory_parameters(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "恢复BCU出厂默认参数失败",
                str(exc),
            )
            return

        self.alarm_parameter_page.clear_cached_values()
        self.alarm_parameter_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                "BCU出厂默认参数已恢复，请重新读取并核对设备参数。"
            )
        )
        self._update_alarm_parameter_controls()

    def on_alarm_parameter_save_flash(self):
        if not self._ensure_alarm_parameter_write_ready():
            return
        try:
            with self._alarm_parameter_busy_state():
                self.service.save_alarm_parameters_to_flash(
                    self.selected_cluster_index
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "\u4fdd\u5b58\u53c2\u6570\u5230 FLASH \u5931\u8d25",
                str(exc),
            )
            return
        self.alarm_parameter_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                "\u544a\u8b66\u53c2\u6570\u5df2\u4fdd\u5b58\u5230 FLASH\u3002"
            )
        )

    def _ensure_history_log_ready(self):
        if not self.can_ready:
            QMessageBox.warning(
                self,
                "CANFD 未连接",
                "CANFD 未连接，无法读取历史日志。",
            )
            return False
        if self.selected_cluster_index is None:
            QMessageBox.warning(
                self,
                "未选择簇",
                "当前没有可用的簇。",
            )
            return False
        return True

    def on_history_log_read(self):
        if not self._ensure_history_log_ready():
            return

        log_type = self.history_log_page.selected_log_type()
        self.history_log_stop_requested = False
        self.history_log_page.clear_records()
        self.history_log_page.set_reading(True)
        self.history_log_page.set_status("正在读取日志总数...")

        read_count = 0
        error_count = 0
        total_count = 0
        try:
            with self._bus_command_busy_state():
                total_count = self.service.read_history_log_count(
                    self.selected_cluster_index,
                    log_type=log_type,
                )
                self.history_log_page.set_counts(total_count, 0)
                if total_count <= 0:
                    self.history_log_page.set_status("设备暂无历史日志")
                    return

                for log_index in range(total_count, 0, -1):
                    if self.history_log_stop_requested:
                        self.history_log_page.set_status(
                            f"已停止，成功读取 {read_count} 条，失败 {error_count} 条"
                        )
                        break
                    self.history_log_page.set_status(
                        f"正在读取第 {log_index} 条..."
                    )
                    QApplication.processEvents()
                    try:
                        record = self.service.read_history_log_entry(
                            self.selected_cluster_index,
                            log_index,
                            log_type=log_type,
                        )
                    except Exception:
                        error_count += 1
                        self.history_log_page.set_counts(total_count, read_count)
                        QApplication.processEvents()
                        continue

                    read_count += 1
                    self.history_log_page.append_record(record)
                    self.history_log_page.set_counts(total_count, read_count)
                    QApplication.processEvents()

                if not self.history_log_stop_requested:
                    self.history_log_page.set_status(
                        f"日志读取正常，成功 {read_count} 条，失败 {error_count} 条"
                    )
        except Exception as exc:
            self.history_log_page.set_status(f"读取失败: {exc}", failed=True)
            QMessageBox.critical(
                self,
                "读取历史日志失败",
                str(exc),
            )
        finally:
            self.history_log_page.set_reading(False)
            self.history_log_stop_requested = False

    def on_history_log_stop(self):
        self.history_log_stop_requested = True
        self.history_log_page.set_status("正在停止读取...")

    def on_history_log_save(self):
        if not self.history_log_page.records:
            QMessageBox.information(
                self,
                "没有可保存的日志",
                "当前表格没有历史日志数据。",
            )
            return
        path = self.history_log_page.choose_save_path()
        if not path:
            return
        try:
            self.history_log_page.save_records_to_csv(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "保存历史日志失败",
                str(exc),
            )
            return
        self.history_log_page.set_status(f"日志已保存: {path}")

    def on_history_log_clear_table(self):
        self.history_log_page.clear_records()

    def on_history_log_clear_device(self):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        reply = QMessageBox.question(
            self,
            "清空历史日志",
            (
                f"确认清空{self.selected_cluster_display_name} "
                "设备中的历史日志？"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            with self._bus_command_busy_state():
                self.service.clear_history_logs(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "清空历史日志失败",
                str(exc),
            )
            return
        self.history_log_page.clear_records()
        self.history_log_page.set_status("设备历史日志已清空")

    def _ensure_index_action_ready(self, require_factory_mode=False):
        if not self.can_ready:
            QMessageBox.warning(
                self,
                "CANFD \u672a\u8fde\u63a5",
                "CANFD \u672a\u8fde\u63a5\uff0c\u8bf7\u5148\u8fde\u63a5\u603b\u7ebf\u3002",
            )
            return False
        if self.selected_cluster_index is None:
            QMessageBox.warning(
                self,
                "\u672a\u9009\u62e9\u7c07",
                "\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u7684\u7c07\u3002",
            )
            return False
        if require_factory_mode and self.factory_mode_status_value != 1:
            QMessageBox.warning(
                self,
                "\u5de5\u88c5\u6a21\u5f0f\u672a\u5f00\u542f",
                "\u8be5\u64cd\u4f5c\u9700\u8981\u5148\u5f00\u542f\u5de5\u88c5\u6a21\u5f0f\u3002",
            )
            return False
        return True

    def on_index_control_read_indexes(self):
        if self.index_read_timer.isActive():
            self._stop_index_control_auto_read("\u7d22\u5f15\u6301\u7eed\u8bfb\u53d6\u5df2\u505c\u6b62\u3002")
            return

        if self._read_index_control_once(show_dialog=True, continuous=True):
            self.index_read_timer.start(self.INDEX_READ_INTERVAL_MS)
            self.index_control_page.read_indexes_button.setText("\u505c\u6b62\u8bfb\u53d6")

    def on_index_control_read_timer(self):
        self._read_index_control_once(show_dialog=False, continuous=True)

    def _stop_index_control_auto_read(self, status_text=None):
        if hasattr(self, "index_read_timer"):
            self.index_read_timer.stop()
        self.index_read_in_progress = False
        if hasattr(self, "index_control_page"):
            self.index_control_page.read_indexes_button.setText("\u8bfb\u53d6\u7d22\u5f15")
            if status_text is not None:
                self.index_control_page.set_status_text(status_text)

    def _ensure_index_read_ready(self, show_dialog):
        if show_dialog:
            return self._ensure_index_action_ready(require_factory_mode=False)
        if self.can_ready and self.selected_cluster_index is not None:
            return True
        self._stop_index_control_auto_read(
            "\u7d22\u5f15\u6301\u7eed\u8bfb\u53d6\u5df2\u505c\u6b62\uff1aCANFD \u672a\u5c31\u7eea\u6216\u672a\u9009\u62e9\u7c07\u3002"
        )
        return False

    def _read_index_control_once(self, show_dialog=True, continuous=False):
        if self.index_read_in_progress:
            return False
        if not self._ensure_index_read_ready(show_dialog):
            return False
        try:
            request_indexes = self.index_control_page.get_request_indexes()
        except ValueError as exc:
            if show_dialog:
                QMessageBox.warning(self, "\u7d22\u5f15\u8f93\u5165\u9519\u8bef", str(exc))
            else:
                self._stop_index_control_auto_read(
                    f"\u7d22\u5f15\u6301\u7eed\u8bfb\u53d6\u5df2\u505c\u6b62\uff1a{exc}"
                )
            return False

        request_count = sum(1 for data_id in request_indexes if data_id is not None)
        if request_count <= 0:
            self.index_control_page.set_status_text(
                "\u8bf7\u5148\u586b\u5199\u81f3\u5c11\u4e00\u9879\u7d22\u5f15\u540e\u518d\u8bfb\u53d6\u3002"
            )
            return False

        read_count = 0
        error_count = 0
        self.index_read_in_progress = True
        try:
            for row_index, data_id in enumerate(request_indexes):
                if data_id is None:
                    self.index_control_page.set_request_value(row_index, None, "")
                    continue
                try:
                    value = self.service.read_data_u16(
                        self.selected_cluster_index,
                        data_id,
                        timeout_s=self.INDEX_READ_TIMEOUT_S,
                    )
                except Exception:
                    error_count += 1
                    self.index_control_page.set_request_value(row_index, data_id, "ERR")
                    continue

                read_count += 1
                self.index_control_page.set_request_value(row_index, data_id, str(value))
        finally:
            self.index_read_in_progress = False

        if continuous and read_count <= 0 and error_count > 0:
            self._stop_index_control_auto_read(
                (
                    f"{self.selected_cluster_display_name} "
                    "\u7d22\u5f15\u6301\u7eed\u8bfb\u53d6\u5df2\u6682\u505c\uff1a"
                    "\u672a\u6536\u5230\u4e0b\u4f4d\u673a\u54cd\u5e94\u3002"
                )
            )
            return False

        prefix = "\u7d22\u5f15\u6301\u7eed\u8bfb\u53d6\u4e2d\uff0c\u6bcf 1 \u79d2\u8bf7\u6c42\u4e00\u6b21" if continuous else "\u7d22\u5f15\u8bfb\u53d6\u5b8c\u6210"
        self.index_control_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"{prefix}\uff0c\u6210\u529f {read_count} \u9879\uff0c"
                f"\u5931\u8d25 {error_count} \u9879\u3002"
            )
        )
        return True

    def on_index_control_write_indexes(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            write_entries = self.index_control_page.get_request_write_entries()
        except ValueError as exc:
            QMessageBox.warning(self, "\u7d22\u5f15\u8f93\u5165\u9519\u8bef", str(exc))
            return

        if not write_entries:
            QMessageBox.warning(
                self,
                "\u6ca1\u6709\u53ef\u5199\u5165\u7684\u7d22\u5f15\u503c",
                "\u8bf7\u5148\u586b\u5199\u81f3\u5c11\u4e00\u9879\u7d22\u5f15\u503c\u540e\u518d\u5199\u5165\u3002",
            )
            return

        write_count = 0
        error_count = 0
        for row_index, data_id, value in write_entries:
            try:
                self.service.write_data_u16(
                    self.selected_cluster_index,
                    data_id,
                    value,
                )
            except Exception:
                error_count += 1
                continue

            write_count += 1
            self.index_control_page.set_request_value(
                row_index,
                data_id,
                self.index_control_page.index_value_edits[row_index].text().strip(),
            )

        self.index_control_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"\u7d22\u5f15\u5199\u5165\u5b8c\u6210\uff0c\u6210\u529f {write_count} \u9879\uff0c"
                f"\u5931\u8d25 {error_count} \u9879\u3002"
            )
        )

    def on_index_control_channel_toggled(self, channel_id, checked):
        self._stop_index_control_auto_read()
        checkbox = self.index_control_page.channel_checks[channel_id]
        if not self._ensure_index_action_ready(require_factory_mode=True):
            checkbox.blockSignals(True)
            checkbox.setChecked(not checked)
            checkbox.blockSignals(False)
            return

        try:
            self.service.control_channel(
                self.selected_cluster_index,
                channel_id,
                checked,
            )
        except Exception as exc:
            checkbox.blockSignals(True)
            checkbox.setChecked(not checked)
            checkbox.blockSignals(False)
            QMessageBox.critical(self, "\u8f93\u51fa\u63a7\u5236\u5931\u8d25", str(exc))
            return

        output_name = checkbox.text()
        state_text = "\u5408" if checked else "\u65ad"
        self.index_control_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"{output_name} \u5df2\u5207\u6362\u4e3a {state_text}\u3002"
            )
        )

    def on_index_control_write_hvil(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        freq = self.index_control_page.hvil_freq_target.value()
        duty = self.index_control_page.hvil_duty_target.value()
        try:
            self.service.write_hvil_pwm_config(
                self.selected_cluster_index,
                freq,
                duty,
            )
        except Exception as exc:
            QMessageBox.critical(self, "HVIL PWM \u5199\u5165\u5931\u8d25", str(exc))
            return

        self._refresh_index_pages()
        self.index_control_page.hvil_freq_current.setText(f"{freq / 10:.1f} Hz")
        self.index_control_page.hvil_duty_current.setText(f"{duty / 10:.1f} %")
        self.index_control_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"HVIL PWM \u5df2\u5199\u5165\uff0c\u9891\u7387 {freq}\uff0c\u5360\u7a7a\u6bd4 {duty}\u3002"
            )
        )

    def on_index_control_write_soc(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        soc_value = self.index_control_page.soc_target.value()
        try:
            self.service.write_user_set_soc(
                self.selected_cluster_index,
                soc_value,
            )
        except Exception as exc:
            QMessageBox.critical(self, "SOC \u5199\u5165\u5931\u8d25", str(exc))
            return

        self._refresh_index_pages()
        self.index_control_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                f"SOC \u5df2\u5199\u5165 {soc_value}\u3002"
            )
        )

    def on_index_control_restore_factory(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_factory_parameters(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u51fa\u5382\u53c2\u6570\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"{self.selected_cluster_display_name} \u5df2\u6062\u590d\u51fa\u5382\u53c2\u6570\u3002"
        )

    def on_index_control_restore_run(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_run_parameters(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u8fd0\u884c\u53c2\u6570\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"{self.selected_cluster_display_name} \u5df2\u6062\u590d\u8fd0\u884c\u53c2\u6570\u3002"
        )

    def on_index_control_restore_product_info(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_product_info(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u4ea7\u54c1\u4fe1\u606f\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"{self.selected_cluster_display_name} \u5df2\u6062\u590d\u4ea7\u54c1\u4fe1\u606f\u3002"
        )

    def on_index_control_save_flash(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.save_all_parameters_to_flash(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u4fdd\u5b58\u53c2\u6570\u5230 FLASH \u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"{self.selected_cluster_display_name} \u53c2\u6570\u5df2\u4fdd\u5b58\u5230 FLASH\u3002"
        )

    def on_index_control_sync_time(self):
        self._stop_index_control_auto_read()
        if not self._ensure_index_action_ready(require_factory_mode=False):
            return
        try:
            self.service.sync_system_time(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u540c\u6b65\u7cfb\u7edf\u65f6\u95f4\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"{self.selected_cluster_display_name} \u7cfb\u7edf\u65f6\u95f4\u5df2\u540c\u6b65\u3002"
        )

    def on_balance_control_cell_toggled(self, group_index, cell_index, checked):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return

        try:
            with self._bus_command_busy_state():
                word_value = self.service.set_balance_cell_state(
                    self.selected_cluster_index,
                    group_index,
                    cell_index,
                    checked,
                )
        except Exception as exc:
            QMessageBox.critical(self, "均衡控制失败", str(exc))
            return

        state_text = "开启" if checked else "关闭"
        self.balance_control_page.setStatusText(
            (
                f"{self.selected_cluster_display_name} "
                f"模组{group_index + 1} 单体{cell_index + 1} 均衡{state_text}命令已发送，"
                f"写入配置字=0x{int(word_value) & 0xFFFF:04X}。"
            )
        )

    def _refresh_index_monitor_page(self):
        self.index_monitor_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        if self.selected_cluster_index is None:
            self.index_monitor_page.clear_values()
            self.index_monitor_page.set_status_text("\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u7684\u7c07\u3002")
            return

        snapshot = self.service.get_index_monitor_snapshot(self.selected_cluster_index)
        self.index_monitor_page.update_snapshot(snapshot)
        self.index_monitor_page.set_status_text(
            (
                f"{self.selected_cluster_display_name} "
                "\u76d1\u63a7\u6570\u636e\u7531\u8bf7\u6c42\u7d22\u5f15\u540e\u53f0\u5237\u65b0\u3002"
            )
        )

    def _refresh_index_monitor_device_time(self):
        if self.selected_cluster_index is None:
            return
        snapshot = self.service.get_index_monitor_snapshot(
            self.selected_cluster_index
        )
        self.index_monitor_page.update_device_time(snapshot.get("device_time"))

    def _refresh_index_control_page(self):
        self.index_control_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        if self.selected_cluster_index is None:
            self.index_control_page.update_snapshot({})
            self.index_control_page.set_status_text("\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u7684\u7c07\u3002")
            return

        snapshot = self.service.get_index_monitor_snapshot(self.selected_cluster_index)
        self.index_control_page.update_snapshot(snapshot)
        if not self.index_control_page.status_label.text():
            self.index_control_page.set_status_text(
                (
                    f"{self.selected_cluster_display_name} "
                    "\u4e3b\u673a\u63a7\u5236\u9875\u5df2\u5c31\u7eea\u3002"
                )
            )

    def _refresh_index_pages(self):
        self._refresh_index_monitor_page()
        self._refresh_index_control_page()

    def _refresh_power_diagnostic_page(self):
        page = self.power_diagnostic_page
        page.set_cluster_context(self.selected_cluster_index, self.selected_address)
        if self.selected_cluster_index is None:
            page.clear_values()
            page.set_status_text("当前没有可用的目标簇。", failed=True)
            return

        snapshot = self.service.get_power_diagnostic_snapshot(
            self.selected_cluster_index
        )
        report = self.power_diagnostic_analyzer.analyze(snapshot)
        events = self.power_diagnostic_events.get(self.selected_cluster_index, [])
        page.update_report(report, events)
        if not self.can_ready:
            page.set_status_text("CANFD未连接，当前显示最后一次诊断快照。", failed=True)
        elif snapshot:
            page.set_status_text(
                f"{self.selected_cluster_display_name} "
                f"已采集 {len(snapshot)} / {len(self.service.power_diagnostic_signal_ids)} 项诊断证据。"
            )
        else:
            page.set_status_text("正在请求上下电诊断索引...")

    def _record_power_diagnostic_updates(self, updates):
        for update in updates:
            if update.signal_id != 12:
                continue
            cluster_index = int(update.cluster_index)
            current_state = int(update.value)
            previous_state = self.power_diagnostic_previous_states.get(cluster_index)
            self.power_diagnostic_previous_states[cluster_index] = current_state
            snapshot = self.service.get_power_diagnostic_snapshot(cluster_index)
            event = self.power_diagnostic_analyzer.build_transition_event(
                previous_state,
                current_state,
                snapshot,
            )
            if event is None:
                continue
            events = self.power_diagnostic_events.setdefault(cluster_index, [])
            events.append(event)
            del events[:-100]

    def _refresh_power_diagnostic_page_if_due(self):
        if self.tabWidget.currentIndex() != self.POWER_DIAGNOSTIC_TAB_INDEX:
            return
        if not self.power_diagnostic_page.auto_refresh_enabled():
            return
        now = time.monotonic()
        if now < self.power_diagnostic_next_refresh_at:
            return
        self._refresh_power_diagnostic_page()
        self.power_diagnostic_next_refresh_at = (
            now + self.power_diagnostic_page.refresh_interval_ms() / 1000.0
        )

    def on_power_diagnostic_refresh(self):
        if self.selected_cluster_index is None:
            self._refresh_power_diagnostic_page()
            return
        self.service.reset_power_diagnostic_query(self.selected_cluster_index)
        self.power_diagnostic_next_refresh_at = 0.0
        self._refresh_power_diagnostic_page()
        if self.can_ready:
            for _ in range(4):
                self.service.send_next_power_diagnostic_query(
                    self.selected_cluster_index
                )

    def _refresh_selected_cluster_views(self, force_periodic=False):
        self._refresh_overview()
        self._refresh_request_page()
        self._refresh_index_pages()
        self._reset_alarm_parameter_page()
        self._refresh_power_diagnostic_page()
        self._refresh_cluster_dashboard_page()
        self._rebuild_dbc_page()
        self.kline_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self._mark_periodic_pages_dirty()
        if force_periodic:
            for tab_index in self.PERIODIC_TAB_INDEXES:
                self._refresh_periodic_tab(tab_index)
            return
        self._refresh_visible_periodic_page()

    def _refresh_cluster_dashboard_page(self):
        get_dashboard = getattr(self.service, "get_dashboard", None)
        if not callable(get_dashboard):
            return
        self.cluster_dashboard_page.update_dashboard(get_dashboard())

    def _bus_activity_snapshot(self):
        get_snapshot = getattr(self.service, "get_bus_activity_snapshot", None)
        if callable(get_snapshot):
            return get_snapshot(self.selected_cluster_index)
        return {
            "is_open": bool(self.can_ready),
            "cluster_index": self.selected_cluster_index,
            "tx_count": 0,
            "tx_attempt_count": 0,
            "tx_failure_count": 0,
            "rx_count": 0,
            "rx_handled_count": 0,
            "last_tx_time": "",
            "last_rx_time": "",
            "last_tx_age_s": None,
            "last_rx_age_s": None,
            "last_rx_frame_id": None,
        }

    def _communication_tile_content(self, snapshot):
        tx_count = int(snapshot.get("tx_count", 0))
        rx_count = int(snapshot.get("rx_count", 0))
        tx_failure_count = int(snapshot.get("tx_failure_count", 0))
        connected = bool(self.can_ready and snapshot.get("is_open", self.can_ready))
        if not connected:
            return (
                f"\u63a5\u53e3\u672a\u8fde\u63a5\nTX {tx_count}  |  RX {rx_count}",
                "neutral",
                "\u63a5\u53e3\u672a\u8fde\u63a5",
            )

        if tx_failure_count > 0 and tx_count <= 0:
            return (
                (
                    "\u62a5\u6587\u53d1\u9001\u5931\u8d25\n"
                    f"TX {tx_count}  |  RX {rx_count}  |  ERR {tx_failure_count}"
                ),
                "danger",
                "\u62a5\u6587\u53d1\u9001\u5931\u8d25",
            )

        last_rx_age_s = snapshot.get("last_rx_age_s")
        if rx_count <= 0 or last_rx_age_s is None:
            wait_text = (
                "\u5df2\u53d1\u9001\uff0c\u7b49\u5f85 BCU \u54cd\u5e94"
                if tx_count > 0
                else "\u63a5\u53e3\u5df2\u8fde\u63a5\uff0c\u7b49\u5f85 BCU \u62a5\u6587"
            )
            return (
                f"{wait_text}\nTX {tx_count}  |  RX {rx_count}",
                "warning",
                wait_text,
            )

        last_rx_frame_id = snapshot.get("last_rx_frame_id")
        frame_text = (
            f"0x{int(last_rx_frame_id):08X}"
            if last_rx_frame_id is not None
            else "--"
        )
        last_rx_time = str(snapshot.get("last_rx_time") or "--")
        last_rx_age_s = max(float(last_rx_age_s), 0.0)
        if last_rx_age_s <= self.communication_active_timeout_s:
            return (
                (
                    "\u6536\u53d1\u6b63\u5e38\n"
                    f"TX {tx_count}  |  RX {rx_count}\n"
                    f"{last_rx_time}  {frame_text}"
                ),
                "success",
                "\u6536\u53d1\u6b63\u5e38",
            )

        status = (
            "danger"
            if last_rx_age_s >= max(self.communication_active_timeout_s * 3.0, 5.0)
            else "warning"
        )
        return (
            (
                f"\u63a5\u6536\u8d85\u65f6 {last_rx_age_s:.1f}s\n"
                f"TX {tx_count}  |  RX {rx_count}\n"
                f"\u6700\u8fd1 RX {last_rx_time}"
            ),
            status,
            f"\u63a5\u6536\u8d85\u65f6 {last_rx_age_s:.1f}s",
        )

    def _refresh_communication_tile_if_due(self, force=False):
        now = time.monotonic()
        if (
            not force
            and now - self.last_communication_tile_refresh_at
            < self.communication_tile_refresh_s
        ):
            return False
        self.last_communication_tile_refresh_at = now
        tile_text, status, summary = self._communication_tile_content(
            self._bus_activity_snapshot()
        )
        self.communication_status_text = summary
        self._set_overview_tile("communication", tile_text, status)
        return True

    def _refresh_overview(self):
        self._refresh_communication_tile_if_due(force=True)
        if not self.selected_address:
            self._set_overview_tile(
                "cluster",
                "\u65e0\u53ef\u7528\u7c07",
                "warning",
            )
            self._set_overview_tile("bus", getattr(self, "bus_status_text", "--"))
            self._set_overview_tile("factory", "\u672a\u77e5", "warning")
            self._set_overview_tile("log", "\u5173", "neutral")
            self._set_overview_tile("periodic", "\u65e0\u6570\u636e", "warning")
            self._set_label_text(
                self.overview_label,
                "\u5f53\u524d\u6ca1\u6709\u53ef\u67e5\u770b\u7684\u7c07\u3002",
            )
            return

        bus_status = getattr(self, "bus_status_state", "neutral")
        status_text = self.periodic_status_cache.get(
            self.selected_address,
            (
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85\u5468\u671f\u6570\u636e"
            ),
        )
        save_log_text = "\u5f00" if self.snapshot_logging_enabled else "\u5173"
        save_scope_text = self._snapshot_logging_scope_text()
        factory_tile_status = (
            "warning"
            if self.factory_mode_status_value == 1
            else "neutral"
            if self.factory_mode_status_value == 0
            else "warning"
        )
        log_tile_status = "success" if self.snapshot_logging_enabled else "neutral"
        periodic_tile_status = (
            "info"
            if self.selected_address in self.periodic_status_cache
            else "warning"
        )
        self._set_overview_tile(
            "cluster",
            self.selected_cluster_display_name,
            "info",
        )
        self._set_overview_tile(
            "bus",
            getattr(self, "bus_status_text", "--"),
            bus_status,
        )
        self._set_overview_tile(
            "factory",
            self.factory_mode_status_text,
            factory_tile_status,
        )
        self._set_overview_tile(
            "log",
            f"{save_log_text} / {save_scope_text}",
            log_tile_status,
        )
        self._set_overview_tile(
            "periodic",
            status_text,
            periodic_tile_status,
        )
        save_scope_note = (
            "\u8bf7\u6c42\u6570\u636e\u4e0e\u5747\u8861\u72b6\u6001\u53ea\u9488\u5bf9\u5f53\u524d\u9009\u4e2d\u7c07\u8fdb\u884c\u540e\u53f0\u8f6e\u8be2\u3002\n"
        )
        if self._uses_all_cluster_snapshot_mode():
            save_scope_note = (
                "\u8bf7\u6c42\u6570\u636e\u4e0e\u5747\u8861\u72b6\u6001\u4f1a\u8f6e\u8be2\u6240\u6709\u7c07\uff0c\u5e76\u4fdd\u5b58\u6240\u6709\u7c07\u65e5\u5fd7\u3002\n"
            )
        overview_text = (
            f"\u5f53\u524d\u9009\u62e9: "
            f"{self.selected_cluster_display_name}\n"
            f"\u603b\u7ebf\u914d\u7f6e: "
            f"device_index={self.device_index_spinbox.value()}, "
            f"channel_index={self.channel_index_spinbox.value()}\n"
            f"\u5de5\u88c5\u72b6\u6001: {self.factory_mode_status_text}\n"
            f"\u62a5\u6587\u6536\u53d1: {self.communication_status_text}\n"
            f"\u65e5\u5fd7\u4fdd\u5b58: "
            f"{save_log_text}\n"
            f"\u65e5\u5fd7\u8303\u56f4: {save_scope_text}\n"
            f"\u4fdd\u5b58\u95f4\u9694: {self.save_interval_ms} ms\n"
            "\u9876\u90e8\u63a7\u4ef6\u53ef\u5207\u6362\u7c07\uff0c"
            "\u4e5f\u53ef\u4fee\u6539\u8bbe\u5907\u53f7\u548c\u901a\u9053\u53f7\uff0c"
            "\u70b9\u51fb\u201c\u5e94\u7528\u5e76\u91cd\u8fde\u201d\u540e\u751f\u6548\u3002\n"
            f"{save_scope_note}"
            "\u201c\u8bf7\u6c42\u6570\u636e\u201d\u9875\u663e\u793a 0x1881F2xx "
            "\u8bf7\u6c42\u5e94\u7b54\u53d8\u91cf\u3002\n"
            "\u201cDBC\u5468\u671f / \u5355\u4f53\u7535\u538b / "
            "\u5355\u4f53\u6e29\u5ea6 / \u5747\u8861\u72b6\u6001 / "
            "\u5747\u8861\u6e29\u5ea6 / \u544a\u8b66\u72b6\u6001 / "
            "\u6781\u67f1\u6e29\u5ea6\u201d"
            "\u9875\u663e\u793a DBC \u5468\u671f CANFD \u6570\u636e\u3002\n"
            f"\u5468\u671f\u72b6\u6001: {status_text}"
        )
        self._set_label_text(self.overview_label, overview_text)

    def _refresh_request_page(self):
        self._rebuild_request_group_tables()

        if self.selected_cluster_index is None:
            return

        cache = self.legacy_cache[self.selected_cluster_index]
        for table_index, row_index in sorted(cache):
            signal_name, value, unit = cache[(table_index, row_index)]
            self._set_legacy_row(table_index, row_index, signal_name, value, unit)

    def _set_legacy_row(self, table_index, row_index, signal_name, value, unit):
        table_widget = self.TW[self.LEGACY_REQUEST_PAGE_INDEX][table_index]
        self._set_table_item_text(table_widget, row_index, 0, signal_name)
        self._set_table_item_text(table_widget, row_index, 1, value)
        self._set_table_item_text(table_widget, row_index, 2, unit)

    def _rebuild_dbc_page(self):
        self.dbc_value_items = {}
        self.dbc_table.clearContents()

        if not self.selected_address:
            self.dbc_table.setRowCount(0)
            self._set_label_text(
                self.dbc_status_label,
                "\u5f53\u524d\u6ca1\u6709\u53ef\u663e\u793a\u7684 DBC \u7c07\u3002",
            )
            return

        catalog = self.service.get_dbc_catalog(self.selected_address)
        self.dbc_table.setRowCount(len(catalog))
        for row_index, item in enumerate(catalog):
            self._set_table_item_text(self.dbc_table, row_index, 0, item["message_name"])
            self._set_table_item_text(self.dbc_table, row_index, 1, item["signal_name"])
            value_item = QTableWidgetItem("")
            self.dbc_table.setItem(row_index, 2, value_item)
            self._set_table_item_text(self.dbc_table, row_index, 3, item["unit"])
            self.dbc_value_items[item["row_key"]] = value_item

        if catalog:
            default_text = (
                f"\u5730\u5740 {self.selected_address} "
                f"\u5df2\u5339\u914d {len(catalog)} \u4e2a\u5468\u671f\u4fe1\u53f7\uff0c"
                "\u7b49\u5f85\u6570\u636e"
            )
        else:
            default_text = (
                f"DBC \u4e2d\u672a\u627e\u5230\u5730\u5740 "
                f"{self.selected_address} \u7684\u5468\u671f\u62a5\u6587\u5b9a\u4e49"
            )
        self._set_label_text(
            self.dbc_status_label,
            self.periodic_status_cache.get(self.selected_address, default_text),
        )

    def _current_dbc_path(self):
        dbc_runtime = getattr(self.service, "dbc_runtime", None)
        dbc_path = getattr(dbc_runtime, "dbc_path", None)
        if not dbc_path:
            return None
        return Path(dbc_path)

    def _update_dbc_source_label(self):
        dbc_path = self._current_dbc_path()
        if dbc_path is None:
            self.dbc_source_label.setText("当前DBC: 未加载")
            self.dbc_source_label.setToolTip("")
            return

        path_text = str(dbc_path)
        self.dbc_source_label.setText(f"当前DBC: {path_text}")
        self.dbc_source_label.setToolTip(path_text)

    def on_load_dbc_file(self):
        current_dbc_path = self._current_dbc_path()
        start_dir = ""
        if current_dbc_path is not None:
            start_dir = str(current_dbc_path.parent)

        dbc_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载DBC文件",
            start_dir,
            "DBC Files (*.dbc);;All Files (*)",
        )
        if not dbc_path:
            return

        try:
            dbc_runtime = DbcRuntime(dbc_path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "加载DBC失败",
                f"DBC文件加载失败。\n\n{dbc_path}\n\n{exc}",
            )
            return

        set_dbc_runtime = getattr(self.service, "set_dbc_runtime", None)
        if callable(set_dbc_runtime):
            set_dbc_runtime(dbc_runtime)
        else:
            self.service.dbc_runtime = dbc_runtime

        self.runtime_config["DBC_PATH"] = dbc_path
        self.periodic_status_cache = {}
        self._update_dbc_source_label()
        self._rebuild_dbc_page()
        if self.selected_address:
            self._refresh_voltage_page()
            self._refresh_temperature_page()
            self._refresh_balance_temperature_page()
            self._refresh_alarm_page()
            self._refresh_terminal_temperature_page()
        self._refresh_overview()

    def _refresh_voltage_page(self):
        voltage_values = self.service.get_periodic_voltage_values(self.selected_address)
        if voltage_values:
            self.voltage_page.setVoltageValues(voltage_values)
        else:
            self.voltage_page.clearValues()

    def _refresh_temperature_page(self):
        temperature_values = self.service.get_periodic_temperature_values(self.selected_address)
        if temperature_values:
            self.temperature_page.setVoltageValues(temperature_values)
        else:
            self.temperature_page.clearValues()

    def _refresh_balance_page(self):
        balance_values = self.service.get_legacy_balance_state_values(self.selected_address)
        if balance_values:
            self.balance_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                f"\u5747\u8861\u8bf7\u6c42\u72b6\u6001 {len(balance_values)} \u9879"
            )
            self.balance_page.setSignalValues(balance_values)
        else:
            self.balance_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85\u5747\u8861\u72b6\u6001\u8bf7\u6c42\u6570\u636e"
            )
            self.balance_page.clearValues()

    def _refresh_balance_temperature_page(self):
        balance_temperature_values = self.service.get_periodic_balance_temperature_values(
            self.selected_address
        )
        if balance_temperature_values:
            value_count = sum(
                1
                for value in balance_temperature_values
                if value is not None and value != ""
            )
            self.balance_temperature_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                f"\u5747\u8861\u6e29\u5ea6 {value_count} \u9879\uff0c\u5355\u4f4d \u2103"
            )
            self.balance_temperature_page.setTemperatureValues(balance_temperature_values)
        else:
            self.balance_temperature_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85 0x12C9EFxx \u5747\u8861\u6e29\u5ea6\u6570\u636e"
            )
            self.balance_temperature_page.clearValues()

    def _refresh_balance_control_page(self):
        self.balance_control_page.set_cluster_context(
            self.selected_cluster_index,
            self.selected_address,
        )
        self._update_balance_control_controls()
        balance_values = self.service.get_legacy_balance_state_values(self.selected_address)
        if balance_values:
            self.balance_control_page.setSignalValues(balance_values)
        else:
            self.balance_control_page.clearValues()
        if self.factory_mode_status_value == 1:
            self.balance_control_page.setStatusText(
                (
                    f"地址 {self.selected_address} 可发送均衡控制命令。"
                    f"当前显示 {len(balance_values)} 项设备回读均衡状态。"
                )
            )
        else:
            self.balance_control_page.setStatusText(
                (
                    f"地址 {self.selected_address} 需先开启工装模式。"
                    f"当前显示 {len(balance_values)} 项设备回读均衡状态。"
                )
            )

    def _refresh_alarm_page(self):
        alarm_values = self.service.get_periodic_alarm_state_values(self.selected_address)
        if alarm_values:
            self.alarm_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                f"\u544a\u8b66\u72b6\u6001 {len(alarm_values)} \u9879"
            )
            self.alarm_page.setSignalValues(alarm_values)
        else:
            self.alarm_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85 0x1204EFA0 \u544a\u8b66\u6570\u636e"
            )
            self.alarm_page.clearValues()

    def _refresh_terminal_temperature_page(self):
        terminal_temperature_values = self.service.get_periodic_terminal_temperature_values(
            self.selected_address
        )
        if terminal_temperature_values:
            self.terminal_temperature_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                f"\u6781\u67f1\u6e29\u5ea6 {len(terminal_temperature_values)} \u9879"
            )
            self.terminal_temperature_page.setSignalValues(terminal_temperature_values)
        else:
            self.terminal_temperature_page.setStatusText(
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85\u6781\u67f1\u6e29\u5ea6\u6570\u636e"
            )
            self.terminal_temperature_page.clearValues()

    def _mark_periodic_pages_dirty(self):
        self.dirty_periodic_tabs.update(self.PERIODIC_TAB_INDEXES)

    def _refresh_visible_periodic_page(self):
        self._refresh_periodic_tab(self.tabWidget.currentIndex())

    def _refresh_periodic_tab(self, tab_index):
        if tab_index not in self.periodic_tab_refreshers:
            return
        if tab_index not in self.dirty_periodic_tabs:
            return
        if not self.selected_address:
            return
        self.periodic_tab_refreshers[tab_index]()
        self.dirty_periodic_tabs.discard(tab_index)

    def on_poll_timer(self):
        if not self.can_ready:
            return

        poll_result = self.service.poll()
        self._record_power_diagnostic_updates(poll_result.legacy_updates)
        self._update_query_activity(poll_result)
        selected_cluster_legacy_updated = self._apply_legacy_updates(
            poll_result.legacy_updates
        )
        selected_address_updated = self._apply_periodic_updates(poll_result.periodic_updates)
        selected_balance_updated = self.selected_address in poll_result.balance_updates

        overview_dirty = False
        for address, status_text in poll_result.periodic_status.items():
            if self.periodic_status_cache.get(address) == status_text:
                continue
            self.periodic_status_cache[address] = status_text
            overview_dirty = overview_dirty or address == self.selected_address
            if address == self.selected_address:
                self._set_label_text(self.dbc_status_label, status_text)

        if selected_address_updated:
            self._mark_periodic_pages_dirty()
            overview_dirty = True
        elif selected_balance_updated:
            self.dirty_periodic_tabs.update(
                {self.BALANCE_TAB_INDEX, self.BALANCE_CONTROL_TAB_INDEX}
            )

        if selected_cluster_legacy_updated and self.tabWidget.currentIndex() in (
            self.REALTIME_MONITOR_TAB_INDEX,
            self.HOST_CONTROL_TAB_INDEX,
        ):
            self.pending_index_pages_refresh = True
            overview_dirty = True

        if overview_dirty:
            self.pending_overview_refresh = True
        self._flush_visual_updates_if_due()
        self._refresh_communication_tile_if_due()
        self._refresh_power_diagnostic_page_if_due()

    def _apply_legacy_updates(self, updates):
        selected_cluster_updated = False
        trend_samples = set()
        sample_timestamp = time.time()
        for update in updates:
            if update.cluster_index == self.selected_cluster_index:
                selected_cluster_updated = True
            trend_key = (update.cluster_index, update.signal_id)
            metric = self.TREND_SIGNAL_METRICS.get(update.signal_id)
            if metric is not None and trend_key not in trend_samples:
                trend_samples.add(trend_key)
                try:
                    trend_value = float(update.value) / 10.0
                except (TypeError, ValueError):
                    trend_value = None
                if (
                    trend_value is not None
                    and self.trend_store.add_sample(
                        update.cluster_index,
                        metric,
                        trend_value,
                        sample_timestamp,
                    )
                ):
                    self.kline_page.notify_sample_added(update.cluster_index, metric)
            if update.table_index < 0 or update.row_index < 0:
                continue
            self.legacy_cache[update.cluster_index][(update.table_index, update.row_index)] = (
                update.signal_name,
                update.value,
                update.unit,
            )
            if update.cluster_index == self.selected_cluster_index:
                if self.tabWidget.currentIndex() == self.REQUEST_TAB_INDEX:
                    self._set_legacy_row(
                        update.table_index,
                        update.row_index,
                        update.signal_name,
                        update.value,
                        update.unit,
                    )
        return selected_cluster_updated

    def _apply_periodic_updates(self, updates):
        selected_address_updated = False
        for update in updates:
            if update.address != self.selected_address:
                continue
            self.pending_dbc_value_updates[update.row_key] = update.value
            selected_address_updated = True
        return selected_address_updated

    def _flush_visual_updates_if_due(self, force=False):
        now = time.monotonic()
        if (
            not force
            and now - self.last_visual_refresh_at < self.ui_refresh_interval_s
        ):
            return False
        self.last_visual_refresh_at = now

        for row_key, value in self.pending_dbc_value_updates.items():
            value_item = self.dbc_value_items.get(row_key)
            if value_item is not None and value_item.text() != value:
                value_item.setText(value)
        self.pending_dbc_value_updates.clear()

        self._refresh_visible_periodic_page()
        if self.pending_index_pages_refresh and self.tabWidget.currentIndex() in (
            self.REALTIME_MONITOR_TAB_INDEX,
            self.HOST_CONTROL_TAB_INDEX,
        ):
            self._refresh_index_pages()
            self.pending_index_pages_refresh = False
        if self.tabWidget.currentIndex() == self.REALTIME_MONITOR_TAB_INDEX:
            # The displayed clock is extrapolated between lower-controller
            # samples, so repaint it even when this poll received no CAN frame.
            self._refresh_index_monitor_device_time()
        if self.tabWidget.currentIndex() == self.CLUSTER_DASHBOARD_TAB_INDEX:
            self._refresh_cluster_dashboard_page()
        if self.pending_overview_refresh:
            self._refresh_overview()
            self.pending_overview_refresh = False
        return True

    def on_query_timer(self):
        if not self.can_ready or not self.cluster_indices:
            return
        tab_index = self.tabWidget.currentIndex()
        if tab_index == self.CLUSTER_DASHBOARD_TAB_INDEX:
            send_next_dashboard_query = getattr(
                self.service,
                "send_next_dashboard_query",
                None,
            )
            if callable(send_next_dashboard_query):
                for _ in range(self.active_query_burst_size):
                    send_next_dashboard_query()
            self._send_snapshot_request_query()
            return
        if tab_index in self.PRIORITY_QUERY_TAB_INDEXES:
            if self._uses_all_cluster_snapshot_mode():
                self._send_active_page_query(self.selected_cluster_index)
                self._send_background_all_cluster_query()
            else:
                for _ in range(self.active_query_burst_size):
                    self._send_active_page_query(self.selected_cluster_index)
                self._send_snapshot_request_query()
            return

        active_cluster_index = self._next_request_query_cluster_index()
        balance_cluster_index = self._next_balance_query_cluster_index()
        if active_cluster_index is not None:
            self.service.send_next_query(active_cluster_index)
        if balance_cluster_index is not None:
            self.service.send_next_balance_query(balance_cluster_index)

    def _send_active_page_query(self, cluster_index):
        if cluster_index is None:
            return 0
        tab_index = self.tabWidget.currentIndex()
        if tab_index in (
            self.REALTIME_MONITOR_TAB_INDEX,
            self.HOST_CONTROL_TAB_INDEX,
        ):
            return self.service.send_next_monitor_query(cluster_index)
        if tab_index in (
            self.BALANCE_TAB_INDEX,
            self.BALANCE_CONTROL_TAB_INDEX,
        ):
            return self.service.send_next_balance_query(cluster_index)
        if tab_index == self.KLINE_TAB_INDEX:
            signal_ids = tuple(self.TREND_SIGNAL_METRICS)
            data_id = signal_ids[self.kline_query_cursor % len(signal_ids)]
            self.kline_query_cursor = (self.kline_query_cursor + 1) % len(signal_ids)
            return self.service.send_signal_query(cluster_index, data_id)
        if tab_index == self.POWER_DIAGNOSTIC_TAB_INDEX:
            return self.service.send_next_power_diagnostic_query(cluster_index)
        return self.service.send_next_query(cluster_index)

    def _send_background_all_cluster_query(self):
        if self.background_query_kind_cursor % 2 == 0:
            cluster_index = self._next_request_query_cluster_index()
            if cluster_index is not None:
                self.service.send_next_query(cluster_index)
        else:
            cluster_index = self._next_balance_query_cluster_index()
            if cluster_index is not None:
                self.service.send_next_balance_query(cluster_index)
        self.background_query_kind_cursor = (self.background_query_kind_cursor + 1) % 2

    def _send_snapshot_request_query(self):
        """Refresh request-group values used by snapshot logging in the background."""
        if (
            not self.snapshot_logging_enabled
            or self.tabWidget.currentIndex() == self.REQUEST_TAB_INDEX
        ):
            return 0
        cluster_index = self._next_request_query_cluster_index()
        if cluster_index is None:
            return 0
        return self.service.send_next_query(cluster_index)

    def on_save_timer(self):
        if not self.can_ready or not self.snapshot_logging_enabled:
            return
        target_cluster_index = (
            None if self._uses_all_cluster_snapshot_mode() else self.selected_cluster_index
        )
        self.service.write_legacy_snapshots(target_cluster_index)

    def on_cluster_changed(self, combo_index):
        if combo_index < 0 or combo_index >= self.cluster_count:
            return
        self._stop_index_control_auto_read()
        self.selected_cluster_index, self.selected_address = self.cluster_options[combo_index]
        self.pending_dbc_value_updates.clear()
        self.last_visual_refresh_at = 0.0
        self._sync_service_active_cluster()
        self._debug_print(
            (
                f"\u5f53\u524d\u7c07\u5207\u6362\u4e3a: "
                f"{self.selected_cluster_display_name}"
            )
        )
        self._refresh_factory_mode_status()
        self._refresh_selected_cluster_views(force_periodic=False)
        self._update_query_timer_state()
        self._update_alarm_parameter_controls()

    def on_cluster_dashboard_activated(self, cluster_index, address):
        normalized_address = str(address).strip().upper()
        selected_option_index = None

        # The protocol address is the stable cluster identity. Dashboard data
        # can be rebuilt independently from the selector, so use the internal
        # index only as a compatibility fallback.
        for option_index, (_, candidate_address) in enumerate(self.cluster_options):
            if str(candidate_address).strip().upper() == normalized_address:
                selected_option_index = option_index
                break
        if selected_option_index is None:
            for option_index, (candidate_index, _) in enumerate(self.cluster_options):
                if int(candidate_index) == int(cluster_index):
                    selected_option_index = option_index
                    break
        if selected_option_index is None:
            self._debug_print(
                f"大屏跳转失败：未找到簇地址 {normalized_address}"
            )
            return

        if self.isFullScreen():
            self.on_cluster_dashboard_fullscreen_requested(False)
        self.cluster_selector.setCurrentIndex(selected_option_index)
        self.tabWidget.setCurrentIndex(self.REALTIME_MONITOR_TAB_INDEX)

    def on_cluster_dashboard_fullscreen_requested(self, enabled):
        enabled = bool(enabled)
        if enabled and not self.isFullScreen():
            self._dashboard_restore_maximized = self.isMaximized()
            self.showFullScreen()
        elif not enabled and self.isFullScreen():
            if self._dashboard_restore_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        is_fullscreen = self.isFullScreen()
        self._set_dashboard_chrome_visible(not is_fullscreen)
        self.cluster_dashboard_page.set_fullscreen_state(is_fullscreen)

    def _set_dashboard_chrome_visible(self, visible):
        """Show or remove the application chrome around the dashboard content."""
        visible = bool(visible)
        self.product_header.setVisible(visible)
        self.tabWidget.tabBar().setVisible(visible)

        root_layout = self.layout()
        if root_layout is not None:
            root_layout.invalidate()
            root_layout.activate()

    def on_tab_changed(self, index):
        self._debug_print(f"\u5f53\u524d\u9009\u4e2d\u6807\u7b7e\u9875\u7d22\u5f15: {index}")
        self._sync_service_active_cluster()
        if index != self.HOST_CONTROL_TAB_INDEX:
            self._stop_index_control_auto_read()
        if index in (self.REALTIME_MONITOR_TAB_INDEX, self.HOST_CONTROL_TAB_INDEX):
            self._refresh_index_pages()
        if index == self.REQUEST_TAB_INDEX:
            # The dashboard can enter idle backoff before this page is opened.
            # A request page must start its own acquisition immediately instead
            # of depending on values previously collected by another page.
            self.idle_poll_count = 0
            self._refresh_request_page()
            if self.can_ready and self.selected_cluster_index is not None:
                for _ in range(self.active_query_burst_size):
                    self.service.send_next_query(self.selected_cluster_index)
        if index == self.KLINE_TAB_INDEX:
            self.kline_page.refresh_active_chart(force=True)
        if index == self.POWER_DIAGNOSTIC_TAB_INDEX:
            self.on_power_diagnostic_refresh()
        if index == self.CLUSTER_DASHBOARD_TAB_INDEX:
            refresh_dashboard = getattr(self.service, "refresh_dashboard", None)
            if callable(refresh_dashboard):
                self.cluster_dashboard_page.update_dashboard(refresh_dashboard())
        self._refresh_periodic_tab(index)
        self._flush_visual_updates_if_due(force=True)
        self._update_poll_timer_state()
        self._update_query_timer_state()

    def _update_poll_timer_state(self):
        if not self.can_ready:
            self.poll_timer.stop()
            return
        interval_ms = (
            self.active_poll_interval_ms
            if self.tabWidget.currentIndex() in self.ACTIVE_POLL_TAB_INDEXES
            else self.poll_interval_ms
        )
        if (not self.poll_timer.isActive()) or self.poll_timer.interval() != interval_ms:
            self.poll_timer.start(interval_ms)

    def _update_query_timer_state(self):
        should_run = (
            self.can_ready
            and bool(self.cluster_indices)
            and self.tabWidget.currentIndex() != self.ALARM_PARAMETER_TAB_INDEX
        )
        if should_run:
            interval_ms = self._current_query_interval_ms()
            if (
                (not self.query_timer.isActive())
                or self.query_timer.interval() != interval_ms
            ):
                self.query_timer.start(interval_ms)
            return
        self.query_timer.stop()

    def _update_query_activity(self, poll_result):
        if poll_result.had_rx_frame:
            self.idle_poll_count = 0
        else:
            self.idle_poll_count += 1
        self._update_query_timer_state()

    def _current_query_interval_ms(self):
        # Keep the request-data scan moving even when several configured
        # indexes do not answer. Otherwise idle backoff stretches a full group
        # refresh from seconds to minutes and makes the page appear inactive.
        if self.tabWidget.currentIndex() == self.REQUEST_TAB_INDEX:
            return self.query_interval_ms
        if self.idle_poll_count >= self.IDLE_QUERY_BACKOFF_POLLS:
            return self.IDLE_QUERY_INTERVAL_MS
        if self.tabWidget.currentIndex() in self.PRIORITY_QUERY_TAB_INDEXES:
            return self.query_interval_ms
        return self.background_query_interval_ms

    def _update_save_timer_state(self):
        should_run = self.can_ready and self.snapshot_logging_enabled
        if should_run:
            self.save_timer.start(self.save_interval_ms)
            return
        self.save_timer.stop()

    def _sync_service_active_cluster(self):
        set_active_cluster = getattr(self.service, "set_active_cluster", None)
        if callable(set_active_cluster):
            if self.tabWidget.currentIndex() == self.CLUSTER_DASHBOARD_TAB_INDEX:
                set_active_cluster(None)
            elif self._uses_all_cluster_snapshot_mode():
                set_active_cluster(None)
            else:
                set_active_cluster(self.selected_cluster_index)

    def _next_request_query_cluster_index(self):
        if not self.cluster_indices:
            return None
        if not self._uses_all_cluster_snapshot_mode():
            return self.selected_cluster_index
        cluster_index = self.cluster_indices[
            self.request_query_cluster_cursor % len(self.cluster_indices)
        ]
        self.request_query_cluster_cursor = (
            self.request_query_cluster_cursor + 1
        ) % len(self.cluster_indices)
        return cluster_index

    def _next_balance_query_cluster_index(self):
        if not self.cluster_indices:
            return None
        if not self._uses_all_cluster_snapshot_mode():
            return self.selected_cluster_index
        cluster_index = self.cluster_indices[
            self.balance_query_cluster_cursor % len(self.cluster_indices)
        ]
        self.balance_query_cluster_cursor = (
            self.balance_query_cluster_cursor + 1
        ) % len(self.cluster_indices)
        return cluster_index

    def _reset_query_cursors(self):
        self.request_query_cluster_cursor = 0
        self.balance_query_cluster_cursor = 0
        self.background_query_kind_cursor = 0
        self.kline_query_cursor = 0

    def closeEvent(self, event):
        self._stop_bus_timers()
        self.service.close()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.on_cluster_dashboard_fullscreen_requested(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_label_text(self, label_widget, text):
        if label_widget.text() != text:
            label_widget.setText(text)

    def _set_table_item_text(self, table_widget, row_index, column_index, value):
        if row_index >= table_widget.rowCount():
            table_widget.setRowCount(row_index + 1)
        if column_index >= table_widget.columnCount():
            table_widget.setColumnCount(column_index + 1)
        value = "" if value is None else str(value)
        item = table_widget.item(row_index, column_index)
        if item is None:
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if column_index == 1:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            table_widget.setItem(row_index, column_index, item)
            return
        if item.text() != value:
            item.setText(value)
        if item.toolTip() != value:
            item.setToolTip(value)

    def _reset_window_runtime_state(self):
        self.legacy_cache = {cluster_index: {} for cluster_index in self.cluster_indices}
        self.periodic_status_cache = {}
        self.dbc_value_items = {}
        self.dirty_periodic_tabs = set(self.PERIODIC_TAB_INDEXES)
        self.pending_dbc_value_updates = {}
        self.pending_index_pages_refresh = False
        self.pending_overview_refresh = False
        self.last_visual_refresh_at = 0.0
        self.last_communication_tile_refresh_at = 0.0
        self.communication_status_text = "\u63a5\u53e3\u672a\u8fde\u63a5"
        self.idle_poll_count = 0
        self.request_query_cluster_cursor = 0
        self.balance_query_cluster_cursor = 0
        self.background_query_kind_cursor = 0
        self.kline_query_cursor = 0
        self.power_diagnostic_previous_states = {}
        self.power_diagnostic_events = {
            cluster_index: [] for cluster_index in self.cluster_indices
        }
        self.power_diagnostic_next_refresh_at = 0.0
        self.history_log_stop_requested = False
        self.factory_mode_status_value = None
        self.factory_mode_status_text = "\u672a\u77e5"
        self.bus_status_text = "\u672a\u8fde\u63a5"
        self.bus_status_state = "neutral"
        self.index_read_in_progress = False

    def _debug_print(self, message):
        if self.debug_ui:
            print(message, flush=True)
