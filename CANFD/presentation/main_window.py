from contextlib import contextmanager
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from UI.Q14 import Ui_Form
from UI.T25 import BatteryMonitor
from UI.T26 import BatteryMonitorBAL
from UI.T27 import BatteryMonitorTem
from domain.dbc_runtime import DbcRuntime
from presentation.alarm_parameter_page import AlarmParameterPage
from presentation.history_log_page import HistoryLogPage
from presentation.index_control_page import IndexControlPage
from presentation.index_monitor_page import IndexMonitorPage
from presentation.signal_grid_page import SignalGridPage


class MainWindow(Ui_Form, QWidget):
    THEME_PATH = Path(__file__).resolve().parents[1] / "UI" / "release_theme.qss"
    POLL_INTERVAL_MS = 100
    QUERY_INTERVAL_MS = 30
    IDLE_QUERY_INTERVAL_MS = 200
    IDLE_QUERY_BACKOFF_POLLS = 10
    DEFAULT_SAVE_INTERVAL_MS = 500
    AUTO_ALARM_READ_TIMEOUT_S = 0.5
    DEFAULT_CLUSTER_ADDRESS = "A0"
    SAVE_SCOPE_CURRENT = "current"
    SAVE_SCOPE_ALL = "all"

    OVERVIEW_TAB_INDEX = 0
    REQUEST_TAB_INDEX = 1
    REALTIME_MONITOR_TAB_INDEX = 2
    HOST_CONTROL_TAB_INDEX = 3
    ALARM_PARAMETER_TAB_INDEX = 4
    HISTORY_LOG_TAB_INDEX = 5
    DBC_TAB_INDEX = 6
    VOLTAGE_TAB_INDEX = 7
    TEMPERATURE_TAB_INDEX = 8
    BALANCE_TAB_INDEX = 9
    ALARM_TAB_INDEX = 10
    TERMINAL_TEMPERATURE_TAB_INDEX = 11

    PERIODIC_TAB_INDEXES = (
        VOLTAGE_TAB_INDEX,
        TEMPERATURE_TAB_INDEX,
        BALANCE_TAB_INDEX,
        ALARM_TAB_INDEX,
        TERMINAL_TEMPERATURE_TAB_INDEX,
    )

    def __init__(self, service, runtime_config):
        super().__init__()
        self.service = service
        self.runtime_config = runtime_config
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

        self._reset_window_runtime_state()
        self.can_ready = False

        self.setupUi(self)
        self._sync_service_active_cluster()
        self._apply_release_window_defaults()
        self._configure_pages()
        self._connect_ui()
        self._load_bus_config_controls()
        self._refresh_selected_cluster_views(force_periodic=True)
        self._open_bus(show_dialog=True)

    def _apply_release_window_defaults(self):
        self.setMinimumSize(1360, 860)
        self.resize(1680, 980)

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

    def _default_cluster_option_index(self):
        for option_index, (_, address) in enumerate(self.cluster_options):
            if str(address).upper() == self.DEFAULT_CLUSTER_ADDRESS:
                return option_index
        return 0

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

    def _load_release_stylesheet(self):
        try:
            return self.THEME_PATH.read_text(encoding="utf-8")
        except OSError:
            return ""

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
        self.periodic_tab_refreshers = {
            self.VOLTAGE_TAB_INDEX: self._refresh_voltage_page,
            self.TEMPERATURE_TAB_INDEX: self._refresh_temperature_page,
            self.BALANCE_TAB_INDEX: self._refresh_balance_page,
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
        for table in self.TW[self.OVERVIEW_TAB_INDEX]:
            table.hide()
        for label in self.label[self.OVERVIEW_TAB_INDEX]:
            label.hide()

        page = self.tab[self.OVERVIEW_TAB_INDEX]
        layout = page.layout()
        if layout is None:
            layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        overview_panel = QFrame(page)
        overview_panel.setObjectName("overviewPanel")
        panel_layout = QVBoxLayout(overview_panel)
        panel_layout.setContentsMargins(28, 24, 28, 24)
        panel_layout.setSpacing(12)

        overview_title = QLabel("系统概览", overview_panel)
        overview_title.setObjectName("pageTitle")
        panel_layout.addWidget(overview_title)

        self.overview_label = QLabel(overview_panel)
        self.overview_label.setObjectName("overviewCard")
        self.overview_label.setWordWrap(True)
        panel_layout.addWidget(self.overview_label)

        layout.addWidget(overview_panel)
        layout.addStretch(1)

    def _configure_request_page(self):
        section_titles = [
            "\u8bf7\u6c42\u5206\u7ec4 1",
            "\u8bf7\u6c42\u5206\u7ec4 2",
            "\u8bf7\u6c42\u5206\u7ec4 3",
        ]
        page = self.tab[self.REQUEST_TAB_INDEX]
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

        self.request_group_tabs = QTabWidget(request_panel)
        self.request_group_tabs.setObjectName("requestGroupTabs")
        panel_layout.addWidget(self.request_group_tabs, stretch=1)
        layout.addWidget(request_panel)

        for table_index, title in enumerate(section_titles):
            label = self.label[self.REQUEST_TAB_INDEX][table_index]
            table = self.TW[self.REQUEST_TAB_INDEX][table_index]

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

    def _configure_compact_tabs(self):
        while self.tabWidget.count():
            self.tabWidget.removeTab(0)

        self.tabWidget.addTab(self.tab[self.OVERVIEW_TAB_INDEX], "\u603b\u89c8")
        self.tabWidget.addTab(self.tab[self.REQUEST_TAB_INDEX], "\u8bf7\u6c42\u6570\u636e")

    def _setup_top_controls(self):
        corner_widget = QWidget(self.tabWidget)
        corner_widget.setObjectName("topControlBar")
        layout = QHBoxLayout(corner_widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        layout.addWidget(QLabel("\u7c07", corner_widget))
        self.cluster_selector = QComboBox(corner_widget)
        self.cluster_selector.setMinimumWidth(130)
        for cluster_index, address in self.cluster_options:
            self.cluster_selector.addItem(
                f"\u7c07{cluster_index} ({address})",
                cluster_index,
            )
        if self.cluster_count:
            self.cluster_selector.setCurrentIndex(self._default_cluster_option_index())
        else:
            self.cluster_selector.setEnabled(False)
        layout.addWidget(self.cluster_selector)

        layout.addSpacing(12)
        layout.addWidget(QLabel("\u8bbe\u5907", corner_widget))
        self.device_index_spinbox = QSpinBox(corner_widget)
        self.device_index_spinbox.setRange(0, 31)
        self.device_index_spinbox.setMinimumWidth(64)
        layout.addWidget(self.device_index_spinbox)

        layout.addWidget(QLabel("\u901a\u9053", corner_widget))
        self.channel_index_spinbox = QSpinBox(corner_widget)
        self.channel_index_spinbox.setRange(0, 31)
        self.channel_index_spinbox.setMinimumWidth(64)
        layout.addWidget(self.channel_index_spinbox)

        self.save_log_checkbox = QCheckBox("\u4fdd\u5b58\u65e5\u5fd7", corner_widget)
        layout.addWidget(self.save_log_checkbox)

        layout.addWidget(QLabel("\u65e5\u5fd7\u8303\u56f4", corner_widget))
        self.save_scope_selector = QComboBox(corner_widget)
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

        layout.addWidget(QLabel("\u4fdd\u5b58\u95f4\u9694", corner_widget))
        self.save_interval_spinbox = QSpinBox(corner_widget)
        self.save_interval_spinbox.setRange(100, 60000)
        self.save_interval_spinbox.setSingleStep(100)
        self.save_interval_spinbox.setSuffix(" ms")
        self.save_interval_spinbox.setMinimumWidth(92)
        layout.addWidget(self.save_interval_spinbox)

        self.apply_bus_button = QPushButton(
            "\u5e94\u7528\u5e76\u91cd\u8fde",
            corner_widget,
        )
        layout.addWidget(self.apply_bus_button)

        self.factory_mode_on_button = QPushButton("\u5de5\u88c5\u5f00", corner_widget)
        self.factory_mode_on_button.setEnabled(bool(self.cluster_count))
        layout.addWidget(self.factory_mode_on_button)

        self.factory_mode_off_button = QPushButton("\u5de5\u88c5\u5173", corner_widget)
        self.factory_mode_off_button.setEnabled(bool(self.cluster_count))
        layout.addWidget(self.factory_mode_off_button)

        self.factory_mode_status_label = QLabel(corner_widget)
        self.factory_mode_status_label.setObjectName("statusPill")
        self.factory_mode_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.factory_mode_status_label.setMinimumWidth(120)
        layout.addWidget(self.factory_mode_status_label)

        self.bus_status_label = QLabel(corner_widget)
        self.bus_status_label.setObjectName("statusPill")
        self.bus_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bus_status_label.setMinimumWidth(220)
        layout.addWidget(self.bus_status_label)

        self.tabWidget.setCornerWidget(corner_widget)
        self._update_factory_mode_status_label()

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
        self.index_control_page = IndexControlPage()
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

    def _create_periodic_pages(self):
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

        self.tabWidget.addTab(self.voltage_page, "\u5355\u4f53\u7535\u538b")
        self.tabWidget.addTab(self.temperature_page, "\u5355\u4f53\u6e29\u5ea6")
        self.tabWidget.addTab(self.balance_page, "\u5747\u8861\u72b6\u6001")
        self.tabWidget.addTab(self.alarm_page, "\u544a\u8b66\u72b6\u6001")
        self.tabWidget.addTab(self.terminal_temperature_page, "\u6781\u67f1\u6e29\u5ea6")

    def _connect_ui(self):
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.cluster_selector.currentIndexChanged.connect(self.on_cluster_changed)
        self.apply_bus_button.clicked.connect(self.on_apply_bus_settings)
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
        self.alarm_parameter_page.save_flash_button.clicked.connect(
            self.on_alarm_parameter_save_flash
        )
        self.alarm_parameter_page.alarm_table.itemSelectionChanged.connect(
            self.on_alarm_parameter_selection_changed
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
        self.poll_timer.start(self.POLL_INTERVAL_MS)
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
        self.poll_timer.start(self.POLL_INTERVAL_MS)
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
        self._refresh_overview()

    def on_save_interval_changed(self, value):
        self.save_interval_ms = int(value)
        self.runtime_config["SAVE_INTERVAL_MS"] = self.save_interval_ms
        self._update_save_timer_state()
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
                        f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                    f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                        f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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

    def _update_factory_mode_status_label(self):
        if not hasattr(self, "factory_mode_status_label"):
            return

        if self.factory_mode_status_value == 1:
            text = "\u5de5\u88c5\u72b6\u6001: \u5f00"
            style = "color: #2e7d32; font-weight: bold;"
        elif self.factory_mode_status_value == 0:
            text = "\u5de5\u88c5\u72b6\u6001: \u5173"
            style = "color: #666666; font-weight: bold;"
        else:
            text = "\u5de5\u88c5\u72b6\u6001: \u672a\u77e5"
            style = "color: #b26a00; font-weight: bold;"

        if self.factory_mode_status_label.text() != text:
            self.factory_mode_status_label.setText(text)
        if self.factory_mode_status_label.styleSheet() != style:
            self.factory_mode_status_label.setStyleSheet(style)

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
            style = "color: #2e7d32; font-weight: bold;"
        elif failed:
            text = (
                f"\u8fde\u63a5\u5931\u8d25: "
                f"dev {device_index} / ch {channel_index}"
            )
            style = "color: #c62828; font-weight: bold;"
        else:
            text = (
                f"\u672a\u8fde\u63a5: "
                f"dev {device_index} / ch {channel_index}"
            )
            style = "color: #666666;"

        if self.bus_status_label.text() != text:
            self.bus_status_label.setText(text)
        if self.bus_status_label.styleSheet() != style:
            self.bus_status_label.setStyleSheet(style)

    def _stop_bus_timers(self):
        self.poll_timer.stop()
        self.query_timer.stop()
        self.save_timer.stop()

    @contextmanager
    def _bus_command_busy_state(self, disable_alarm_controls=False):
        poll_was_active = self.poll_timer.isActive()
        save_was_active = self.save_timer.isActive()
        poll_interval = self.poll_timer.interval() or self.POLL_INTERVAL_MS
        save_interval = self.save_timer.interval() or self.save_interval_ms
        self.poll_timer.stop()
        self.query_timer.stop()
        self.save_timer.stop()
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
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._update_query_timer_state()
            self._update_alarm_parameter_controls()

    @contextmanager
    def _alarm_parameter_busy_state(self):
        with self._bus_command_busy_state(disable_alarm_controls=True):
            yield

    def _set_alarm_parameter_buttons_enabled(self, enabled):
        self.alarm_parameter_page.read_summary_button.setEnabled(bool(enabled))
        self.alarm_parameter_page.write_current_button.setEnabled(bool(enabled))
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
                    f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                        f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"{record.code} {record.name} \u53c2\u6570\u5df2\u5199\u5165\u3002"
            )
        )

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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
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
                f"确认清空簇{self.selected_cluster_index} ({self.selected_address}) "
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
        if not self._ensure_index_action_ready(require_factory_mode=False):
            return
        try:
            request_indexes = self.index_control_page.get_request_indexes()
        except ValueError as exc:
            QMessageBox.warning(self, "\u7d22\u5f15\u8f93\u5165\u9519\u8bef", str(exc))
            return

        read_count = 0
        error_count = 0
        for row_index, data_id in enumerate(request_indexes):
            if data_id is None:
                self.index_control_page.set_request_value(row_index, None, "")
                continue
            try:
                value = self.service.read_data_u16(
                    self.selected_cluster_index,
                    data_id,
                    timeout_s=0.2,
                )
            except Exception:
                error_count += 1
                self.index_control_page.set_request_value(row_index, data_id, "ERR")
                continue

            read_count += 1
            self.index_control_page.set_request_value(row_index, data_id, str(value))

        self.index_control_page.set_status_text(
            (
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"\u7d22\u5f15\u8bfb\u53d6\u5b8c\u6210\uff0c\u6210\u529f {read_count} \u9879\uff0c"
                f"\u5931\u8d25 {error_count} \u9879\u3002"
            )
        )

    def on_index_control_write_indexes(self):
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"\u7d22\u5f15\u5199\u5165\u5b8c\u6210\uff0c\u6210\u529f {write_count} \u9879\uff0c"
                f"\u5931\u8d25 {error_count} \u9879\u3002"
            )
        )

    def on_index_control_channel_toggled(self, channel_id, checked):
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"{output_name} \u5df2\u5207\u6362\u4e3a {state_text}\u3002"
            )
        )

    def on_index_control_write_hvil(self):
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"HVIL PWM \u5df2\u5199\u5165\uff0c\u9891\u7387 {freq}\uff0c\u5360\u7a7a\u6bd4 {duty}\u3002"
            )
        )

    def on_index_control_write_soc(self):
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                f"SOC \u5df2\u5199\u5165 {soc_value}\u3002"
            )
        )

    def on_index_control_restore_factory(self):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_factory_parameters(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u51fa\u5382\u53c2\u6570\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"\u7c07{self.selected_cluster_index} ({self.selected_address}) \u5df2\u6062\u590d\u51fa\u5382\u53c2\u6570\u3002"
        )

    def on_index_control_restore_run(self):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_run_parameters(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u8fd0\u884c\u53c2\u6570\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"\u7c07{self.selected_cluster_index} ({self.selected_address}) \u5df2\u6062\u590d\u8fd0\u884c\u53c2\u6570\u3002"
        )

    def on_index_control_restore_product_info(self):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.restore_product_info(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u6062\u590d\u4ea7\u54c1\u4fe1\u606f\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"\u7c07{self.selected_cluster_index} ({self.selected_address}) \u5df2\u6062\u590d\u4ea7\u54c1\u4fe1\u606f\u3002"
        )

    def on_index_control_save_flash(self):
        if not self._ensure_index_action_ready(require_factory_mode=True):
            return
        try:
            self.service.save_all_parameters_to_flash(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u4fdd\u5b58\u53c2\u6570\u5230 FLASH \u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"\u7c07{self.selected_cluster_index} ({self.selected_address}) \u53c2\u6570\u5df2\u4fdd\u5b58\u5230 FLASH\u3002"
        )

    def on_index_control_sync_time(self):
        if not self._ensure_index_action_ready(require_factory_mode=False):
            return
        try:
            self.service.sync_system_time(self.selected_cluster_index)
        except Exception as exc:
            QMessageBox.critical(self, "\u540c\u6b65\u7cfb\u7edf\u65f6\u95f4\u5931\u8d25", str(exc))
            return
        self.index_control_page.set_status_text(
            f"\u7c07{self.selected_cluster_index} ({self.selected_address}) \u7cfb\u7edf\u65f6\u95f4\u5df2\u540c\u6b65\u3002"
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
                f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                "\u76d1\u63a7\u6570\u636e\u7531\u8bf7\u6c42\u7d22\u5f15\u540e\u53f0\u5237\u65b0\u3002"
            )
        )

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
                    f"\u7c07{self.selected_cluster_index} ({self.selected_address}) "
                    "\u4e3b\u673a\u63a7\u5236\u9875\u5df2\u5c31\u7eea\u3002"
                )
            )

    def _refresh_index_pages(self):
        self._refresh_index_monitor_page()
        self._refresh_index_control_page()

    def _refresh_selected_cluster_views(self, force_periodic=False):
        self._refresh_overview()
        self._refresh_request_page()
        self._refresh_index_pages()
        self._reset_alarm_parameter_page()
        self._rebuild_dbc_page()
        self._mark_periodic_pages_dirty()
        if force_periodic:
            for tab_index in self.PERIODIC_TAB_INDEXES:
                self._refresh_periodic_tab(tab_index)
            return
        self._refresh_visible_periodic_page()

    def _refresh_overview(self):
        if not self.selected_address:
            self._set_label_text(
                self.overview_label,
                "\u5f53\u524d\u6ca1\u6709\u53ef\u67e5\u770b\u7684\u7c07\u3002",
            )
            return

        status_text = self.periodic_status_cache.get(
            self.selected_address,
            (
                f"\u5730\u5740 {self.selected_address} "
                "\u7b49\u5f85\u5468\u671f\u6570\u636e"
            ),
        )
        save_log_text = "\u5f00" if self.snapshot_logging_enabled else "\u5173"
        save_scope_text = self._snapshot_logging_scope_text()
        save_scope_note = (
            "\u8bf7\u6c42\u6570\u636e\u4e0e\u5747\u8861\u72b6\u6001\u53ea\u9488\u5bf9\u5f53\u524d\u9009\u4e2d\u7c07\u8fdb\u884c\u540e\u53f0\u8f6e\u8be2\u3002\n"
        )
        if self._uses_all_cluster_snapshot_mode():
            save_scope_note = (
                "\u8bf7\u6c42\u6570\u636e\u4e0e\u5747\u8861\u72b6\u6001\u4f1a\u8f6e\u8be2\u6240\u6709\u7c07\uff0c\u5e76\u4fdd\u5b58\u6240\u6709\u7c07\u65e5\u5fd7\u3002\n"
            )
        overview_text = (
            f"\u5f53\u524d\u9009\u62e9: "
            f"\u7c07{self.selected_cluster_index}\uff0c"
            f"\u5730\u5740 {self.selected_address}\n"
            f"\u603b\u7ebf\u914d\u7f6e: "
            f"device_index={self.device_index_spinbox.value()}, "
            f"channel_index={self.channel_index_spinbox.value()}\n"
            f"\u5de5\u88c5\u72b6\u6001: {self.factory_mode_status_text}\n"
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
            "\u544a\u8b66\u72b6\u6001 / \u6781\u67f1\u6e29\u5ea6\u201d"
            "\u9875\u663e\u793a DBC \u5468\u671f CANFD \u6570\u636e\u3002\n"
            f"\u5468\u671f\u72b6\u6001: {status_text}"
        )
        self._set_label_text(self.overview_label, overview_text)

    def _refresh_request_page(self):
        for table in self.TW[self.REQUEST_TAB_INDEX]:
            table.clearContents()

        if self.selected_cluster_index is None:
            return

        cache = self.legacy_cache[self.selected_cluster_index]
        for table_index, row_index in sorted(cache):
            signal_name, value, unit = cache[(table_index, row_index)]
            self._set_legacy_row(table_index, row_index, signal_name, value, unit)

    def _set_legacy_row(self, table_index, row_index, signal_name, value, unit):
        table_widget = self.TW[self.REQUEST_TAB_INDEX][table_index]
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
            self._refresh_visible_periodic_page()
            overview_dirty = True
        elif selected_balance_updated:
            self.dirty_periodic_tabs.add(self.BALANCE_TAB_INDEX)
            self._refresh_visible_periodic_page()

        if selected_cluster_legacy_updated and self.tabWidget.currentIndex() in (
            self.REALTIME_MONITOR_TAB_INDEX,
            self.HOST_CONTROL_TAB_INDEX,
        ):
            self._refresh_index_pages()
            overview_dirty = True

        if overview_dirty:
            self._refresh_overview()

    def _apply_legacy_updates(self, updates):
        selected_cluster_updated = False
        for update in updates:
            if update.cluster_index == self.selected_cluster_index:
                selected_cluster_updated = True
            if update.table_index < 0 or update.row_index < 0:
                continue
            self.legacy_cache[update.cluster_index][(update.table_index, update.row_index)] = (
                update.signal_name,
                update.value,
                update.unit,
            )
            if update.cluster_index == self.selected_cluster_index:
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
            value_item = self.dbc_value_items.get(update.row_key)
            if value_item is not None and value_item.text() != update.value:
                value_item.setText(update.value)
            selected_address_updated = True
        return selected_address_updated

    def on_query_timer(self):
        if not self.can_ready or not self.cluster_indices:
            return
        active_cluster_index = self._next_request_query_cluster_index()
        if active_cluster_index is not None:
            self.service.send_next_query(active_cluster_index)
            self.service.send_next_balance_query(active_cluster_index)
        if (
            self.selected_cluster_index is not None
            and self.tabWidget.currentIndex() in (
                self.REALTIME_MONITOR_TAB_INDEX,
                self.HOST_CONTROL_TAB_INDEX,
            )
        ):
            self.service.send_next_monitor_query(self.selected_cluster_index)

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
        self.selected_cluster_index, self.selected_address = self.cluster_options[combo_index]
        self._sync_service_active_cluster()
        self._debug_print(
            (
                f"\u5f53\u524d\u7c07\u5207\u6362\u4e3a: "
                f"\u7c07{self.selected_cluster_index} ({self.selected_address})"
            )
        )
        self._refresh_factory_mode_status()
        self._refresh_selected_cluster_views(force_periodic=False)
        self._update_query_timer_state()
        self._update_alarm_parameter_controls()

    def on_tab_changed(self, index):
        self._debug_print(f"\u5f53\u524d\u9009\u4e2d\u6807\u7b7e\u9875\u7d22\u5f15: {index}")
        if index in (self.REALTIME_MONITOR_TAB_INDEX, self.HOST_CONTROL_TAB_INDEX):
            self._refresh_index_pages()
        self._refresh_periodic_tab(index)
        self._update_query_timer_state()

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
        if self.idle_poll_count >= self.IDLE_QUERY_BACKOFF_POLLS:
            return self.IDLE_QUERY_INTERVAL_MS
        return self.QUERY_INTERVAL_MS

    def _update_save_timer_state(self):
        should_run = self.can_ready and self.snapshot_logging_enabled
        if should_run:
            self.save_timer.start(self.save_interval_ms)
            return
        self.save_timer.stop()

    def _sync_service_active_cluster(self):
        set_active_cluster = getattr(self.service, "set_active_cluster", None)
        if callable(set_active_cluster):
            if self._uses_all_cluster_snapshot_mode():
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

    def closeEvent(self, event):
        self._stop_bus_timers()
        self.service.close()
        super().closeEvent(event)

    def _set_label_text(self, label_widget, text):
        if label_widget.text() != text:
            label_widget.setText(text)

    def _set_table_item_text(self, table_widget, row_index, column_index, value):
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
        self.idle_poll_count = 0
        self.request_query_cluster_cursor = 0
        self.balance_query_cluster_cursor = 0
        self.history_log_stop_requested = False
        self.factory_mode_status_value = None
        self.factory_mode_status_text = "\u672a\u77e5"

    def _debug_print(self, message):
        if self.debug_ui:
            print(message, flush=True)
