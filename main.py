import time
from datetime import datetime
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QTimer, QDateTime
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget, QApplication,QTableWidgetItem,QMessageBox,QLabel,QSpinBox,QPushButton,QCheckBox,QComboBox
import sys
import time
import threading
from ZLGCanControl import Communication
from UI.Q14 import Ui_Form
from UI.T33 import HistoryLogRecord
from application.configuration import (
    build_cluster_addresses,
    build_cluster_indices,
    load_can_board_config,
    save_can_board_config,
)
from session_logger import SessionLogManager
from functools import partial
from PyQt6.QtGui import QColor
import yaml
from UI.conf import config
import os
import copy
from SIGNAL import *
from util import *

CMD_READ_VAR = 0x80
RESP_READ_VAR = 0x81
CMD_WRITE_VAR = 0x82
RESP_WRITE_VAR = 0x83
CMD_READ_ACTIVE_ALARM = 0x84
RESP_READ_ACTIVE_ALARM = 0x85
CMD_CTRL_HARDWARE = 0x88
RESP_CTRL_HARDWARE = 0x89
CMD_SET_TIME = 0x90
RESP_SET_TIME = 0x91
CMD_DECODE_SECU = 0xA0
RESP_DECODE_SECU = 0xA1

CTRL_WORK_MODE = 0x01
CTRL_CHNNEL = 0x02
CTRL_PARA_CONFIG = 0x04

WORK_MODE_NORMAL = 0
WORK_MODE_GZ_TEST = 1
VAR_SYS_WORK_MODE = 11
VAR_SYS_RUN_STATUS = 12
VAR_SYS_VOLT = 13
VAR_SYS_CURR = 14
VAR_SYS_SOC = 16
VAR_SYS_SOH = 17
VAR_SYS_DIS_SOC = 18
VAR_SYS_ANALOG_BAT_VOLT = 0x5B
VAR_SYS_ANALOG_PACK_VOLT = 0x5C
VAR_SYS_DIFF_VOLT = 321
VAR_SYS_DIFF_TEMP = 322
VAR_SYS_AVG_VOLT = 323
VAR_SYS_AVG_TEMP = 324
VAR_SYS_ONLINE_LECU_NUM = 325
VAR_SYS_CELL_VOLT_MAX = 328
VAR_SYS_MAXV_POSI = 329
VAR_SYS_CELL_VOLT_MIN = 331
VAR_SYS_MINV_POSI = 332
VAR_SYS_CELL_TEMP_MAX = 334
VAR_SYS_MAXT_POSI = 335
VAR_SYS_CELL_TEMP_MIN = 337
VAR_SYS_MINT_POSI = 338
VAR_SYS_USER_SET_SOC = 445
VAR_HALL_CURR = 818
VAR_SHUNT_CURR = 819
ID_PAR_SYS_START = 0x90400
PAR_SYS_MODULE_COUNT = ID_PAR_SYS_START + 1
PAR_SYS_AFE_COUNT = ID_PAR_SYS_START + 2
PAR_SYS_OUTPUT_HVIL_FREQ = ID_PAR_SYS_START + 197
PAR_SYS_OUTPUT_HVIL_DUTY_RATIO = ID_PAR_SYS_START + 198
CTRL_PARA_CONFIG_RESET_FACTORY = 2
CTRL_PARA_CONFIG_RESET_RUN = 3
CTRL_PARA_CONFIG_RESET_PRODUCT_INFO = 5
CTRL_PARA_CONFIG_SAVE_ALL_TO_FLASH = 8
Vres = [0 for i in range(0, int(config["LECU_NUM"]*int(config["CELL_NUM"])))]
VresBAL = [0 for i in range(0, int(config["LECU_NUM"]*int(config["CELL_NUM"])))]
VresTem = [0 for i in range(0, int(config["LECU_NUM"]*int(config["CELL_Tem_NUM"])))]
VresDXYC = [0 for i in range(0, int(config["LECU_NUM"]*int(config["CELL_NUM"])))]
Alarm_list = [[0 for _ in range(32)] for _ in range(64)]

BAL_JG_LEN = 20*10+64

RUNTIME_LOG_SIGNAL_NAMES = [name for name in ResDataRec.keys() if name != "时间"]

REALTIME_MONITOR_SIGNAL_DEFINITIONS = (
    {"key": "work_mode", "data_id": VAR_SYS_WORK_MODE, "signed": False},
    {"key": "module_count", "data_id": PAR_SYS_MODULE_COUNT, "signed": False},
    {"key": "afe_count", "data_id": PAR_SYS_AFE_COUNT, "signed": False},
    {"key": "di1", "data_id": 36, "signed": False},
    {"key": "di2", "data_id": 37, "signed": False},
    {"key": "di3", "data_id": 38, "signed": False},
    {"key": "di4", "data_id": 39, "signed": False},
    {"key": "di5", "data_id": 40, "signed": False},
    {"key": "di6", "data_id": 41, "signed": False},
    {"key": "di7", "data_id": 42, "signed": False},
    {"key": "di8", "data_id": 43, "signed": False},
    {"key": "di9", "data_id": 44, "signed": False},
    {"key": "di10", "data_id": 45, "signed": False},
    {"key": "di11", "data_id": 46, "signed": False},
    {"key": "di12", "data_id": 47, "signed": False},
    {"key": "relay1", "data_id": 48, "signed": False},
    {"key": "relay2", "data_id": 49, "signed": False},
    {"key": "relay3", "data_id": 50, "signed": False},
    {"key": "relay4", "data_id": 51, "signed": False},
    {"key": "relay5", "data_id": 52, "signed": False},
    {"key": "relay6", "data_id": 53, "signed": False},
    {"key": "relay7", "data_id": 54, "signed": False},
    {"key": "relay8", "data_id": 55, "signed": False},
    {"key": "relay9", "data_id": 56, "signed": False},
    {"key": "relay10", "data_id": 57, "signed": False},
    {"key": "rt1", "data_id": 112, "signed": True},
    {"key": "rt2", "data_id": 113, "signed": True},
    {"key": "rt3", "data_id": 114, "signed": True},
    {"key": "rt4", "data_id": 115, "signed": True},
    {"key": "rt5", "data_id": 116, "signed": True},
    {"key": "rt6", "data_id": 117, "signed": True},
    {"key": "rt7", "data_id": 118, "signed": True},
    {"key": "rt8", "data_id": 119, "signed": True},
    {"key": "rt9", "data_id": 120, "signed": True},
    {"key": "rt10", "data_id": 121, "signed": True},
    {"key": "board_temp1", "data_id": 122, "signed": True},
    {"key": "board_temp2", "data_id": 123, "signed": True},
    {"key": "avg_voltage", "data_id": VAR_SYS_AVG_VOLT, "signed": False},
    {"key": "avg_temp", "data_id": VAR_SYS_AVG_TEMP, "signed": True},
    {"key": "online_lecu_num", "data_id": VAR_SYS_ONLINE_LECU_NUM, "signed": False},
    {"key": "user_set_soc", "data_id": VAR_SYS_USER_SET_SOC, "signed": False},
    {"key": "hvil_pwm_freq", "data_id": PAR_SYS_OUTPUT_HVIL_FREQ, "signed": False},
    {"key": "hvil_pwm_duty", "data_id": PAR_SYS_OUTPUT_HVIL_DUTY_RATIO, "signed": False},
)

REALTIME_MONITOR_SIGNAL_IDS = tuple(dict.fromkeys(
    [definition["data_id"] for definition in REALTIME_MONITOR_SIGNAL_DEFINITIONS]
    + [
        VAR_SYS_RUN_STATUS,
        VAR_SYS_VOLT,
        VAR_SYS_CURR,
        VAR_SYS_SOC,
        VAR_SYS_SOH,
        VAR_SYS_DIS_SOC,
        VAR_SYS_ANALOG_BAT_VOLT,
        VAR_SYS_ANALOG_PACK_VOLT,
        VAR_SYS_DIFF_VOLT,
        VAR_SYS_DIFF_TEMP,
        VAR_SYS_CELL_VOLT_MAX,
        VAR_SYS_MAXV_POSI,
        VAR_SYS_CELL_VOLT_MIN,
        VAR_SYS_MINV_POSI,
        VAR_SYS_CELL_TEMP_MAX,
        VAR_SYS_MAXT_POSI,
        VAR_SYS_CELL_TEMP_MIN,
        VAR_SYS_MINT_POSI,
        0x252,
        0x253,
        0x1FD,
        0x1FE,
        0x90801,
        0x90802,
        0x1AD,
        0x1AF,
        VAR_HALL_CURR,
        VAR_SHUNT_CURR,
        0x1C0,
        0x1C1,
        0x1C2,
        0x1C3,
        0x1C4,
        0x1C5,
        0x1C6,
        0x1C7,
        0x346,
        0x347,
        0x348,
        0x349,
        0x34A,
        0x34B,
        0x34C,
        0x34D,
        0x34E,
        0x34F,
        0x354,
        0x355,
        0x356,
        0x357,
        0x358,
        0x359,
    ]
))

#ABNORM_ADDR = 0x9098D-2
ABNORM_ADDR = 0x90901
for i in range(0,6):
    data  = 0x3019 +i
    BAUSignalQ.append(data)

#预充错误上半簇
for i in range(0,6):
    data = 706 + i*100
    BAUSignalQ.append(data)
#预充错误下半簇
for i in range(0,6):
    data = 707 + i*100
    BAUSignalQ.append(data)
#并网失败上半簇
for i in range(0,6):
    data = 708 + i*100
    BAUSignalQ.append(data)
#并网失败下半簇
for i in range(0,6):
    data = 709 + i*100
    BAUSignalQ.append(data)

#P端电压上半簇
for i in range(0,6):
    data = 698 + i*100
    BAUSignalQ.append(data)

#P端电压下半簇
for i in range(0,6):
    data = 699 + i*100
    BAUSignalQ.append(data)

#P端电压下整簇
for i in range(0,6):
    data = 641 + i*100
    BAUSignalQ.append(data)

#B端电压上半簇
for i in range(0,6):
    data = 0x1244 + i*1359
    BAUSignalQ.append(data)

#B端电压下半簇
for i in range(0,6):
    data = 0x1245 + i*1359
    BAUSignalQ.append(data)


#B端电压整簇
for i in range(0,6):
    data = 0x1001 + i*1359
    BAUSignalQ.append(data)

#霍尔电流
for i in range(0, 6):
    data = 0x1246 + i * 1359
    BAUSignalQ.append(data)

#分流器电流
for i in range(0, 6):
    data = 0x1247 + i * 1359
    BAUSignalQ.append(data)


#支路运行状态上半簇
for i in range(0,6):
    data = 0x2B8 + i * 100
    BAUSignalQ.append(data)

#支路运行状态下半簇
for i in range(0,6):
    data = 0x2B9 + i * 100
    BAUSignalQ.append(data)

#电芯异常监测
BCUSignalQ_DXYC = [
    ABNORM_ADDR + module_index * 320 + cell_index
    for module_index in range(0, int(config["LECU_NUM"]))
    for cell_index in range(0, int(config["CELL_NUM"]))
]

AlarmClassDict = {}
for i in config["ADDRESLIST"]:
    AlarmClassDict[i] = {}
g_index = 0


class Edit(Ui_Form, QWidget):
    DEFAULT_CLUSTER_ADDRESS = "A0"
    ZERO_TAB_INDEX = 0
    CLUSTER_TAB_INDEX = 1

    # 定义初始化进程
    def __init__(self):
        # 继承
        super().__init__()
        # 往空QWidget中放置UI内容
        self.setupUi(self)
        self._apply_release_theme()
        #初始化各种功能
        self.init()


    def _apply_release_theme(self):
        if hasattr(self, "tabWidget"):
            self.tabWidget.setStyleSheet("")
        theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "UI", "release_theme.qss")
        try:
            with open(theme_path, "r", encoding="utf-8") as theme_file:
                self.setStyleSheet(theme_file.read())
        except OSError as exc:
            print(f"load release theme failed: {exc}")


    def _add_command_caption(self, text):
        label = QLabel(text, self.product_command_bar)
        label.setObjectName("fieldCaption")
        self.product_command_layout.addWidget(label)
        return label


    def _setup_product_controls(self):
        if getattr(self, "_product_controls_ready", False):
            return
        if not hasattr(self, "product_command_layout"):
            return

        self.cluster_options = self._build_cluster_options()
        self._add_command_caption("当前簇")
        self.cluster_selector = QComboBox(self.product_command_bar)
        self.cluster_selector.setMinimumWidth(130)
        for cluster_index, address in self.cluster_options:
            self.cluster_selector.addItem(
                self._cluster_display_name(cluster_index, address),
                cluster_index,
            )
        if self.cluster_options:
            default_option_index = self._default_cluster_option_index()
            self.cluster_selector.setCurrentIndex(default_option_index)
            self.selected_cluster_index, self.selected_cluster_address = self.cluster_options[
                default_option_index
            ]
        else:
            self.selected_cluster_index = 0
            self.selected_cluster_address = ""
            self.cluster_selector.setEnabled(False)
        self.cluster_selector.currentIndexChanged.connect(self.on_cluster_selector_changed)
        self.product_command_layout.addWidget(self.cluster_selector)
        self.product_command_layout.addSpacing(8)

        self._add_command_caption("设备")
        self.device_index_spinbox = QSpinBox(self.product_command_bar)
        self.device_index_spinbox.setRange(0, 31)
        self.device_index_spinbox.setFixedWidth(64)
        self.product_command_layout.addWidget(self.device_index_spinbox)

        self._add_command_caption("通道")
        self.channel_index_spinbox = QSpinBox(self.product_command_bar)
        self.channel_index_spinbox.setRange(0, 7)
        self.channel_index_spinbox.setFixedWidth(64)
        self.product_command_layout.addWidget(self.channel_index_spinbox)

        self._add_command_caption("波特率")
        self.baud_rate_spinbox = QSpinBox(self.product_command_bar)
        self.baud_rate_spinbox.setRange(5, 1000)
        self.baud_rate_spinbox.setSingleStep(5)
        self.baud_rate_spinbox.setSuffix(" k")
        self.baud_rate_spinbox.setFixedWidth(92)
        self.product_command_layout.addWidget(self.baud_rate_spinbox)

        self.save_log_checkbox = QCheckBox("日志", self.product_command_bar)
        self.save_log_checkbox.toggled.connect(self.on_save_log_toggled)
        self.product_command_layout.addWidget(self.save_log_checkbox)

        self._add_command_caption("范围")
        self.log_scope_selector = QComboBox(self.product_command_bar)
        self.log_scope_selector.setFixedWidth(96)
        self.log_scope_selector.addItem("当前簇", "current")
        self.log_scope_selector.addItem("所有簇", "all")
        self.log_scope_selector.currentIndexChanged.connect(self.on_log_scope_changed)
        self.product_command_layout.addWidget(self.log_scope_selector)

        self.log_status_label = QLabel("日志: 关 / 当前簇", self.product_command_bar)
        self.log_status_label.setObjectName("statusPill")
        self.log_status_label.setProperty("status", "warning")
        self.product_command_layout.addWidget(self.log_status_label)

        self.apply_bus_button = QPushButton("应用并重连", self.product_command_bar)
        self.apply_bus_button.setObjectName("primaryButton")
        self.apply_bus_button.clicked.connect(self.on_apply_bus_settings)
        self.product_command_layout.addWidget(self.apply_bus_button)

        self.factory_on_button = QPushButton("工装开", self.product_command_bar)
        self.factory_on_button.clicked.connect(lambda: self.on_factory_mode_change(True))
        self.product_command_layout.addWidget(self.factory_on_button)

        self.factory_off_button = QPushButton("工装关", self.product_command_bar)
        self.factory_off_button.clicked.connect(lambda: self.on_factory_mode_change(False))
        self.product_command_layout.addWidget(self.factory_off_button)

        self.factory_status_label = QLabel("工装状态: 未知", self.product_command_bar)
        self.factory_status_label.setObjectName("statusPill")
        self.factory_status_label.setProperty("status", "warning")
        self.product_command_layout.addWidget(self.factory_status_label)

        self.bus_status_label = QLabel("CAN: 未连接", self.product_command_bar)
        self.bus_status_label.setObjectName("statusPill")
        self.product_command_layout.addWidget(self.bus_status_label)

        self.frame_status_label = QLabel("RX: 0", self.product_command_bar)
        self.frame_status_label.setObjectName("statusPill")
        self.product_command_layout.addWidget(self.frame_status_label)

        self._product_controls_ready = True


    def _build_cluster_options(self):
        addresses = list(config.get("ADDRESLIST", []))
        max_cluster_index = min(len(addresses) - 1, int(config.get("BCU_NUM", 0)))
        options = []
        for cluster_index in range(1, max_cluster_index + 1):
            address = str(addresses[cluster_index]).upper()
            if self._is_compiled_cluster_address(address):
                options.append((cluster_index, address))
        return options


    def _is_compiled_cluster_address(self, address):
        text = str(address or "").strip().upper()
        if text.startswith("0X"):
            text = text[2:]
        text = text.lstrip("0")
        return bool(text)


    def _default_cluster_option_index(self):
        for option_index, (_cluster_index, address) in enumerate(getattr(self, "cluster_options", [])):
            if str(address).upper() == self.DEFAULT_CLUSTER_ADDRESS:
                return option_index
        return 0


    def _cluster_address(self, cluster_index):
        addresses = config.get("ADDRESLIST", [])
        if 0 <= cluster_index < len(addresses):
            return str(addresses[cluster_index]).upper()
        return ""


    def _cluster_display_name(self, cluster_index, address=None):
        address = self._cluster_address(cluster_index) if address is None else str(address).upper()
        if cluster_index == 0:
            return f"00 ({address})" if address else "00"
        return f"簇{cluster_index} ({address})" if address else f"簇{cluster_index}"


    def _active_cluster_index(self):
        return int(getattr(self, "selected_cluster_index", 0))


    def _current_bau_tab_index(self):
        return config["BCU_NUM"] + 1


    def _realtime_monitor_tab_index(self):
        return config["BCU_NUM"] + 7


    def _control_tab_index(self):
        return config["BCU_NUM"] + 8


    def _voltage_tab_index(self):
        return config["BCU_NUM"] + 2


    def _balance_tab_index(self):
        return config["BCU_NUM"] + 3


    def _temperature_tab_index(self):
        return config["BCU_NUM"] + 4


    def _alarm_tab_index(self):
        return config["BCU_NUM"] + 5


    def _active_alarm_tab_index(self):
        return config["BCU_NUM"] + 6


    def _di_tab_index(self):
        return -1


    def _parameter_tab_index(self):
        return -1


    def _abnormal_cell_tab_index(self):
        return config["BCU_NUM"] + 9


    def _balance_control_tab_index(self):
        return config["BCU_NUM"] + 10


    def _history_log_tab_index(self):
        return config["BCU_NUM"] + 11


    def _valid_cluster_indices(self):
        return {cluster_index for cluster_index, _address in getattr(self, "cluster_options", [])}


    def _is_hidden_cluster_tab_index(self, tab_index):
        return self.CLUSTER_TAB_INDEX < tab_index <= config["BCU_NUM"]


    def _set_combo_index_safely(self, combo, index):
        if combo is None or index < 0 or index >= combo.count():
            return False
        previous_block = combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(previous_block)
        return True


    def _sync_cluster_selector_from_index(self, cluster_index):
        selector = getattr(self, "cluster_selector", None)
        if selector is None:
            return
        for option_index in range(selector.count()):
            if selector.itemData(option_index) == cluster_index:
                self._set_combo_index_safely(selector, option_index)
                return


    def _cluster_page_combo_boxes(self):
        combo_specs = (
            ("S18", "comboBox"),
            ("S19", "comboBox"),
            ("S20", "comboBox"),
            ("S21", "comboBox"),
            ("S22", "comboBox"),
            ("S23", "comboBox"),
            ("S24", "comboBox"),
            ("S17", "comboBox_13"),
        )
        combos = []
        for page_name, combo_name in combo_specs:
            page = getattr(self, page_name, None)
            combo = getattr(page, combo_name, None)
            if combo is not None:
                combos.append(combo)
        return combos


    def _sync_page_cluster_combo_boxes(self, cluster_index):
        for combo in self._cluster_page_combo_boxes():
            self._set_combo_index_safely(combo, cluster_index)


    def _connect_cluster_page_selectors(self):
        combo_specs = (
            ("S18", "comboBox"),
            ("S19", "comboBox"),
            ("S20", "comboBox"),
            ("S22", "comboBox"),
            ("S23", "comboBox"),
            ("S24", "comboBox"),
            ("S17", "comboBox_13"),
        )
        for page_name, combo_name in combo_specs:
            page = getattr(self, page_name, None)
            combo = getattr(page, combo_name, None)
            if combo is not None:
                combo.currentIndexChanged.connect(self.on_embedded_cluster_changed)


    def _hide_widget(self, widget):
        if widget is not None:
            widget.hide()


    def _hide_embedded_cluster_controls(self):
        self._hide_widget(getattr(self.S17, "label_11", None))
        self._hide_widget(getattr(self.S17, "frame_5", None))
        self._hide_widget(getattr(self.S17, "comboBox_13", None))
        self._hide_widget(getattr(self.S21, "cluster_caption", None))
        self._hide_widget(getattr(self.S21, "comboBox", None))
        self._hide_widget(getattr(self.S21, "cluster_label", None))
        self._hide_widget(getattr(self.S22, "comboBox", None))
        self._hide_widget(getattr(self.S23, "frame_6", None))
        self._hide_widget(getattr(self.S23, "comboBox", None))
        self._hide_widget(getattr(self.S18, "comboBox", None))
        self._hide_widget(getattr(self.S19, "comboBox", None))
        self._hide_widget(getattr(self.S20, "comboBox", None))
        self._hide_widget(getattr(self.S24, "comboBox", None))


    def _configure_single_cluster_tab(self):
        if not hasattr(self, "tabWidget"):
            return
        if self.tabWidget.count() > self.CLUSTER_TAB_INDEX:
            self.tabWidget.setTabText(self.CLUSTER_TAB_INDEX, "簇")
        tab_bar = self.tabWidget.tabBar()
        if hasattr(tab_bar, "setTabVisible"):
            if self.ZERO_TAB_INDEX < self.tabWidget.count():
                tab_bar.setTabVisible(self.ZERO_TAB_INDEX, False)
            for tab_index in range(self.CLUSTER_TAB_INDEX + 1, config["BCU_NUM"] + 1):
                if tab_index < self.tabWidget.count():
                    tab_bar.setTabVisible(tab_index, False)


    def _reset_cluster_query_cursors(self):
        for attr_name in (
            "BAL_index",
            "DXYC_index",
            "BCUSignalQ_index",
            "BCUSignalQ_DXYC_index",
            "realtime_monitor_query_index",
            "current_COUNT",
        ):
            if hasattr(self, attr_name):
                setattr(self, attr_name, 0)


    def _clear_cluster_buffers(self):
        global Vres, VresBAL, VresTem, VresDXYC, Alarm_list
        Vres = [0 for _ in range(0, int(config["LECU_NUM"] * int(config["CELL_NUM"])))]
        VresBAL = [0 for _ in range(0, int(config["LECU_NUM"] * int(config["CELL_NUM"])))]
        VresTem = [0 for _ in range(0, int(config["LECU_NUM"] * int(config["CELL_Tem_NUM"])))]
        VresDXYC = [0 for _ in range(0, int(config["LECU_NUM"] * int(config["CELL_NUM"])))]
        Alarm_list = [[0 for _ in range(32)] for _ in range(64)]
        self.voltage_snapshot_dirty = False
        self.temperature_snapshot_dirty = False
        self.balance_snapshot_dirty = False
        self.abnormal_snapshot_dirty = False


    def _clear_current_cluster_tables(self):
        if not hasattr(self, "TW") or self.CLUSTER_TAB_INDEX >= len(self.TW):
            return
        for table in self.TW[self.CLUSTER_TAB_INDEX]:
            table.clearContents()


    def _refresh_cluster_views(self, source=None):
        self._clear_cluster_buffers()
        self._clear_current_cluster_tables()
        self.S18currentIndexChanged()
        self.S18currentIndexChangedBAL()
        self.S20currentIndexChangedTem()
        if hasattr(self, "S25"):
            self.S25.set_values([])
        if hasattr(self, "S27"):
            self.S27.clear_values()
        if hasattr(self, "S28"):
            self.S28.clear_active_alarm_records()
            self.S28.set_status_text(f"已切换到 {self._cluster_display_name(self.selected_cluster_index, self.selected_cluster_address)}。")
        if getattr(self, "table_index", None) == self._alarm_tab_index() and source != "alarm_page":
            self.S21.clear_cached_values()
            self.S21.set_status_text(f"已切换到 {self._cluster_display_name(self.selected_cluster_index, self.selected_cluster_address)}。")
            if getattr(self, "can_ready", False):
                self.on_alarm_parameter_read()


    def _set_active_cluster(self, cluster_index, refresh=True, source=None):
        if getattr(self, "_cluster_syncing", False):
            return
        try:
            cluster_index = int(cluster_index)
        except (TypeError, ValueError):
            return
        if cluster_index not in self._valid_cluster_indices():
            return

        self._cluster_syncing = True
        try:
            previous_index = getattr(self, "selected_cluster_index", None)
            self.selected_cluster_index = cluster_index
            self.selected_cluster_address = self._cluster_address(cluster_index)
            self._sync_cluster_selector_from_index(cluster_index)
            self._sync_page_cluster_combo_boxes(cluster_index)
            if hasattr(self, "S27"):
                self.S27.set_cluster_context(cluster_index, self.selected_cluster_address)
            if hasattr(self, "S17"):
                self.S17.set_cluster_context(cluster_index, self.selected_cluster_address)
            if hasattr(self, "S21"):
                self.S21.set_cluster_context(cluster_index, self.selected_cluster_address)
            if hasattr(self, "S28"):
                self.S28.set_cluster_context(cluster_index, self.selected_cluster_address)
            if hasattr(self, "S25"):
                self.S25.set_cluster_context(cluster_index, self.selected_cluster_address)
            if hasattr(self, "S26"):
                self.S26.set_cluster_context(cluster_index, self.selected_cluster_address)

            if (
                source in ("top", "init")
                and hasattr(self, "tabWidget")
                and getattr(self, "table_index", 0) <= config["BCU_NUM"]
            ):
                self.tabWidget.setCurrentIndex(self.CLUSTER_TAB_INDEX)
                self.table_index = self.CLUSTER_TAB_INDEX

            if previous_index != cluster_index:
                self._reset_cluster_query_cursors()
                if refresh:
                    self._refresh_cluster_views(source=source)
        finally:
            self._cluster_syncing = False


    def on_cluster_selector_changed(self, option_index):
        selector = getattr(self, "cluster_selector", None)
        if selector is None or option_index < 0:
            return
        cluster_index = selector.itemData(option_index)
        if cluster_index is None:
            cluster_index = option_index
        self._set_active_cluster(cluster_index, refresh=True, source="top")


    def on_embedded_cluster_changed(self, cluster_index):
        self._set_active_cluster(cluster_index, refresh=True, source="embedded")


    def _load_bus_config_controls(self, can_config):
        if not getattr(self, "_product_controls_ready", False):
            return
        self.device_index_spinbox.setValue(int(can_config.get("can_idx", 0)))
        self.channel_index_spinbox.setValue(int(can_config.get("chn", 1)))
        self.baud_rate_spinbox.setValue(int(can_config.get("baud_rate", 500)))
        self._set_log_scope(config.get("SAVE_LOG_SCOPE", "current"))
        self.save_log_checkbox.setChecked(int(config.get("SAVE_LOG", 0)) == 1)
        self._update_log_status()


    def _current_bus_config(self):
        can_config = load_can_board_config()
        if getattr(self, "_product_controls_ready", False):
            can_config["can_idx"] = int(self.device_index_spinbox.value())
            can_config["chn"] = int(self.channel_index_spinbox.value())
            can_config["baud_rate"] = int(self.baud_rate_spinbox.value())
        return can_config


    def _save_bus_config(self, can_config):
        save_can_board_config(can_config)


    def _refresh_dynamic_style(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


    def _set_status_pill(self, label, text, status):
        if label is None:
            return
        label.setText(text)
        label.setProperty("status", status)
        self._refresh_dynamic_style(label)


    def _set_bus_status(self, connected, message=None, status=None):
        self.can_ready = bool(connected)
        if connected:
            status_text = message or "CAN: 已连接"
            status_name = status or "success"
        else:
            status_text = message or "CAN: 未连接"
            status_name = status or "danger"
        self._set_status_pill(getattr(self, "bus_status_label", None), status_text, status_name)


    def _update_rx_status(self):
        self._set_status_pill(
            getattr(self, "frame_status_label", None),
            f"RX: {getattr(self, 'rx_frame_count', 0)}",
            "info",
        )


    def _runtime_log_dir(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "hisData")


    def _log_cluster_indices(self):
        return build_cluster_indices(config)


    def _log_cluster_addresses(self):
        return build_cluster_addresses(config)


    def _normalize_log_scope(self, scope):
        text = str(scope or "").strip().lower()
        if text in ("all", "all_clusters", "所有簇", "全部"):
            return "all"
        return "current"


    def _log_scope(self):
        selector = getattr(self, "log_scope_selector", None)
        if selector is not None:
            scope = selector.currentData()
            if scope is not None:
                return self._normalize_log_scope(scope)
        return self._normalize_log_scope(config.get("SAVE_LOG_SCOPE", "current"))


    def _log_scope_text(self):
        return "所有簇" if self._log_scope() == "all" else "当前簇"


    def _set_log_scope(self, scope):
        normalized_scope = self._normalize_log_scope(scope)
        config["SAVE_LOG_SCOPE"] = normalized_scope
        selector = getattr(self, "log_scope_selector", None)
        if selector is not None and self._normalize_log_scope(selector.currentData()) != normalized_scope:
            target_index = selector.findData(normalized_scope)
            if target_index < 0:
                target_index = 0
            blocker = QtCore.QSignalBlocker(selector)
            selector.setCurrentIndex(target_index)
            del blocker
        self._update_log_status()


    def _log_target_cluster_indices(self):
        res_data = getattr(self, "ResDataRec", [])
        valid_indices = []
        for cluster_index in self._log_cluster_indices():
            try:
                cluster_index = int(cluster_index)
            except (TypeError, ValueError):
                continue
            if 0 < cluster_index < len(res_data) and cluster_index not in valid_indices:
                valid_indices.append(cluster_index)

        if self._log_scope() == "all":
            return valid_indices

        active_cluster_index = self._active_cluster_index()
        if active_cluster_index in valid_indices:
            return [active_cluster_index]
        if 0 < active_cluster_index < len(res_data):
            return [active_cluster_index]
        return []


    def _ensure_session_log_manager(self):
        manager = getattr(self, "session_log_manager", None)
        if manager is None:
            manager = SessionLogManager(
                self._runtime_log_dir(),
                cluster_indices=self._log_cluster_indices(),
                cluster_addresses=self._log_cluster_addresses(),
                runtime_signal_names=RUNTIME_LOG_SIGNAL_NAMES,
                voltage_count=int(config["LECU_NUM"]) * int(config["CELL_NUM"]),
                temperature_count=int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"]),
                balance_module_count=int(config["LECU_NUM"]),
                balance_cells_per_module=int(config["CELL_NUM"]),
                abnormal_count=int(config["LECU_NUM"]) * int(config["CELL_NUM"]),
                enabled=False,
            )
            self.session_log_manager = manager
        return manager


    def _logging_enabled(self):
        checkbox = getattr(self, "save_log_checkbox", None)
        return bool(checkbox is not None and checkbox.isChecked())


    def _attach_log_manager_to_can(self):
        can_device = getattr(self, "c", None)
        if can_device is not None:
            can_device.log_manager = self._ensure_session_log_manager()


    def _update_log_status(self):
        enabled = self._logging_enabled()
        manager = getattr(self, "session_log_manager", None)
        scope_text = self._log_scope_text()
        text = f"日志: {'开' if enabled else '关'} / {scope_text}"
        label = getattr(self, "log_status_label", None)
        self._set_status_pill(
            label,
            text,
            "success" if enabled else "warning",
        )
        if label is not None:
            if enabled and manager is not None and manager.enabled:
                label.setToolTip(
                    f"保存范围: {scope_text}\n当前日志会话: {manager.session_name}\n目录: {self._runtime_log_dir()}"
                )
            else:
                label.setToolTip(f"日志未开启\n保存范围: {scope_text}")


    def on_log_scope_changed(self, _index):
        selector = getattr(self, "log_scope_selector", None)
        self._set_log_scope(selector.currentData() if selector is not None else "current")


    def on_save_log_toggled(self, checked):
        config["SAVE_LOG"] = 1 if checked else 0
        manager = self._ensure_session_log_manager()
        manager.set_enabled(checked)
        self._attach_log_manager_to_can()
        timer = getattr(self, "timerResData", None)
        if timer is not None:
            if checked and getattr(self, "can_ready", False):
                timer.start(1000)
            else:
                timer.stop()
        self._update_log_status()


    def _close_session_log(self):
        manager = getattr(self, "session_log_manager", None)
        if manager is not None:
            manager.close()


    def _monitor_table_value(self, section_index, *signal_names):
        if not hasattr(self, "TW") or self.CLUSTER_TAB_INDEX >= len(self.TW):
            return None
        if section_index < 0 or section_index >= len(self.TW[self.CLUSTER_TAB_INDEX]):
            return None
        table = self.TW[self.CLUSTER_TAB_INDEX][section_index]
        expected = {str(name).strip() for name in signal_names}
        for row in range(table.rowCount()):
            signal_item = table.item(row, 0)
            if signal_item is None:
                continue
            if signal_item.text().strip() not in expected:
                continue
            value_item = table.item(row, 1)
            if value_item is None:
                return None
            return self._clean_monitor_value(value_item.text())
        return None


    def _clean_monitor_value(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in ("--", "None", "-1"):
            return None
        return text


    def _monitor_record_value(self, record, *keys):
        for key in keys:
            value = self._clean_monitor_value(record.get(key))
            if value is not None:
                return value
        return None


    def _monitor_number(self, value):
        value = self._clean_monitor_value(value)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


    def _nonzero_numeric_values(self, values):
        numbers = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number != 0:
                numbers.append(number)
        return numbers


    def _extreme_snapshot(self, values, cells_per_module, *, scale=1.0):
        numbers = self._nonzero_numeric_values(values)
        if not numbers:
            return {}
        max_value = max(numbers)
        min_value = min(numbers)
        max_index = next(index for index, value in enumerate(values) if float(value) == max_value)
        min_index = next(index for index, value in enumerate(values) if float(value) == min_value)

        def position(index):
            if cells_per_module <= 0:
                return None, index + 1
            return index // cells_per_module + 1, index % cells_per_module + 1

        max_module, max_cell = position(max_index)
        min_module, min_cell = position(min_index)
        return {
            "max_value": max_value / scale,
            "min_value": min_value / scale,
            "max_module": max_module,
            "max_cell": max_cell,
            "min_module": min_module,
            "min_cell": min_cell,
            "diff": (max_value - min_value) / scale,
            "avg": sum(numbers) / len(numbers) / scale,
        }


    def _derive_power_kw(self, voltage_value, current_value):
        voltage = self._monitor_number(voltage_value)
        current = self._monitor_number(current_value)
        if voltage is None or current is None:
            return None
        return abs(voltage * current) / 1000


    def _line_edit_number(self, widget):
        if widget is None:
            return None
        text = str(widget.text()).strip()
        if not text or text == "--":
            return None
        number_text = "".join(char for char in text if char.isdigit() or char in ".-")
        return self._monitor_number(number_text)


    def _state_from_value(self, value):
        number = self._monitor_number(value)
        if number is None:
            return None
        return bool(int(number))

    def _u16_from_response(self, low_byte, high_byte):
        return (int(low_byte) & 0xFF) | ((int(high_byte) & 0xFF) << 8)


    def _signed_u16(self, raw_word):
        return Unsignal_Change(int(raw_word) & 0xFFFF)


    def _cache_realtime_monitor_index_value(self, cluster_index, data_id, raw_word):
        try:
            cluster_index = int(cluster_index)
            data_id = int(data_id)
            raw_word = int(raw_word) & 0xFFFF
        except (TypeError, ValueError):
            return
        if cluster_index <= 0:
            return
        raw_values = getattr(self, "realtime_monitor_raw_words", None)
        if raw_values is None:
            self.realtime_monitor_raw_words = {}
            raw_values = self.realtime_monitor_raw_words
        decoded_values = getattr(self, "realtime_monitor_values", None)
        if decoded_values is None:
            self.realtime_monitor_values = {}
            decoded_values = self.realtime_monitor_values
        raw_values.setdefault(cluster_index, {})[data_id] = raw_word
        decoded = decoded_values.setdefault(cluster_index, {})
        for definition in getattr(self, "realtime_monitor_definitions_by_id", {}).get(data_id, []):
            value = self._signed_u16(raw_word) if definition.get("signed") else raw_word
            decoded[definition["key"]] = value


    def _realtime_raw_value(self, cluster_index, data_id, *, signed=False):
        raw_word = getattr(self, "realtime_monitor_raw_words", {}).get(cluster_index, {}).get(int(data_id))
        if raw_word is None:
            return None
        if signed:
            return self._signed_u16(raw_word)
        return int(raw_word) & 0xFFFF


    def _scaled_realtime_raw(self, cluster_index, data_id, *, signed=False, scale=1):
        value = self._realtime_raw_value(cluster_index, data_id, signed=signed)
        if value is None:
            return None
        if not scale or scale == 1:
            return value
        return value / scale


    def _realtime_raw_high_byte(self, cluster_index, data_id):
        value = self._realtime_raw_value(cluster_index, data_id)
        if value is None:
            return None
        return (value >> 8) & 0xFF


    def _realtime_raw_low_byte(self, cluster_index, data_id):
        value = self._realtime_raw_value(cluster_index, data_id)
        if value is None:
            return None
        return value & 0xFF


    def _first_monitor_value(self, *values):
        for value in values:
            if isinstance(value, (int, float, bool)):
                return value
            cleaned = self._clean_monitor_value(value)
            if cleaned is None:
                continue
            return cleaned
        return None


    def _to_input_state(self, value):
        if value is None:
            return None
        try:
            number = int(float(value)) & 0xFFFF
        except (TypeError, ValueError):
            return None
        if number == 0xFFFF:
            return True
        if number == 0:
            return False
        return None


    def _to_output_state(self, value):
        if value is None:
            return None
        try:
            return bool(int(float(value)))
        except (TypeError, ValueError):
            return None


    def _combine_realtime_words(self, high_word, low_word):
        if high_word is None or low_word is None:
            return None
        return ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)


    def _build_realtime_monitor_snapshot(self):
        cluster_index = self._active_cluster_index()
        if cluster_index <= 0 or cluster_index >= len(getattr(self, "ResDataRec", [])):
            return {}

        record = self.ResDataRec[cluster_index]
        cells_per_module = int(config.get("CELL_NUM", 0))
        voltage_extremes = self._extreme_snapshot(Vres, cells_per_module, scale=1.0)
        temp_extremes = self._extreme_snapshot(VresTem, int(config.get("CELL_Tem_NUM", 0)), scale=10.0)

        hall_current = self._monitor_record_value(record, "霍尔电流")
        shunt_current = self._monitor_record_value(record, "分流器电流")
        max_charge_current = self._monitor_table_value(0, "最大允许充电电流") or self._monitor_table_value(1, "最大允许充电电流")
        max_discharge_current = self._monitor_table_value(0, "最大允许放电电流") or self._monitor_table_value(1, "最大允许放电电流")
        pack_voltage = (
            self._monitor_record_value(record, "P端电压整簇")
            or self._monitor_table_value(2, "P总压")
            or self._monitor_record_value(record, "P端电压上半簇")
        )
        battery_voltage = (
            self._monitor_record_value(record, "B端电压整簇")
            or self._monitor_table_value(2, "B总压")
            or self._monitor_record_value(record, "B端电压上半簇")
        )
        soc = self._monitor_record_value(record, "SOC上半簇", "SOC下半簇")

        relay_states = [None] * 10
        relay_states[0] = self._state_from_value(self._monitor_record_value(record, "充电继电器上半簇"))
        relay_states[5] = self._state_from_value(self._monitor_record_value(record, "放电继电器上半簇"))

        snapshot = {
            "work_mode": self._monitor_table_value(2, "工装模式"),
            "run_status": self._monitor_record_value(record, "运行状态上半簇", "运行状态下半簇") or self._monitor_table_value(2, "系统运行状态"),
            "system_current": hall_current or shunt_current,
            "hall_current": hall_current,
            "shunt_current": shunt_current,
            "battery_voltage": battery_voltage,
            "system_voltage": battery_voltage,
            "pack_voltage": pack_voltage,
            "soc": soc,
            "display_soc": soc,
            "soh": self._monitor_record_value(record, "SOH"),
            "diff_voltage": voltage_extremes.get("diff"),
            "diff_temp": temp_extremes.get("diff") * 10 if temp_extremes.get("diff") is not None else None,
            "avg_voltage": voltage_extremes.get("avg"),
            "avg_temp": temp_extremes.get("avg") * 10 if temp_extremes.get("avg") is not None else None,
            "module_count": self._monitor_table_value(2, "模组数") or config.get("LECU_NUM"),
            "afe_count": self._monitor_table_value(2, "每个模组AFE数量"),
            "online_lecu_num": config.get("LECU_NUM"),
            "pure_soc": self._monitor_table_value(0, "PURE_SOC", "PURE_SOC_UP"),
            "revise_soc": self._monitor_table_value(0, "REVISE_SOC", "REVSE_SOC_UP"),
            "revise_soc_temp": self._monitor_table_value(0, "REVISESOC_TEMP", "REVISE_SOC_Temp_UP"),
            "fuzzy_soc": self._monitor_table_value(0, "PACK_FUZZY_SOC", "FUZZY_SOC_UP"),
            "cell_max_soc": self._monitor_table_value(0, "MAX_SOC", "MAX_SOC_UP"),
            "cell_min_soc": self._monitor_table_value(0, "MIN_SOC", "MIN_SOC_UP"),
            "cell_max_soc_temp": self._monitor_table_value(0, "CELL_MAX_SOC_TEMP", "MAX_SOC_Temp_UP"),
            "cell_min_soc_temp": self._monitor_table_value(0, "CELL_MIN_SOC_TEMP", "MIN_SOC_Temp_UP"),
            "max_cell_voltage": voltage_extremes.get("max_value") or self._monitor_record_value(record, "最大单体电压上半簇", "最大单体电压下半簇"),
            "max_cell_voltage_module": voltage_extremes.get("max_module"),
            "max_cell_voltage_index": voltage_extremes.get("max_cell"),
            "min_cell_voltage": voltage_extremes.get("min_value") or self._monitor_record_value(record, "最小单体电压上半簇", "最小单体电压下半簇"),
            "min_cell_voltage_module": voltage_extremes.get("min_module"),
            "min_cell_voltage_index": voltage_extremes.get("min_cell"),
            "max_cell_temp": temp_extremes.get("max_value") or self._monitor_record_value(record, "最高温度上半簇", "最高温度下半簇"),
            "max_cell_temp_module": temp_extremes.get("max_module"),
            "max_cell_temp_index": temp_extremes.get("max_cell"),
            "min_cell_temp": temp_extremes.get("min_value") or self._monitor_record_value(record, "最低温度上半簇", "最低温度下半簇"),
            "min_cell_temp_module": temp_extremes.get("min_module"),
            "min_cell_temp_index": temp_extremes.get("min_cell"),
            "remaining_discharge_kwh": self._monitor_table_value(0, "剩余可放电"),
            "remaining_charge_kwh": self._monitor_table_value(0, "剩余可充电"),
            "single_charge_kwh": self._monitor_table_value(0, "单次充电电量"),
            "single_discharge_kwh": self._monitor_table_value(0, "单次放电电量"),
            "total_charge_kwh": self._monitor_table_value(2, "累计充电电量") or self._monitor_table_value(0, "TOTAL_CHRG_AH"),
            "total_discharge_kwh": self._monitor_table_value(2, "累计放电电量") or self._monitor_table_value(0, "TOTAL_DSCH_AH"),
            "max_discharge_current": max_discharge_current,
            "max_charge_current": max_charge_current,
            "max_discharge_power": self._derive_power_kw(pack_voltage, max_discharge_current),
            "max_charge_power": self._derive_power_kw(pack_voltage, max_charge_current),
            "hvil_pwm_freq": self._line_edit_number(getattr(getattr(self, "S17", None), "hvil_freq_current", None)),
            "hvil_pwm_duty": self._line_edit_number(getattr(getattr(self, "S17", None), "hvil_duty_current", None)),
            "board_temp1": self._monitor_table_value(self._current_bau_tab_index(), "温度1(5A)"),
            "board_temp2": self._monitor_table_value(self._current_bau_tab_index(), "温度2(5B)"),
            "rt_values": [],
            "di_states": [None] * 12,
            "relay_states": relay_states,
        }
        index_values = getattr(self, "realtime_monitor_values", {}).get(cluster_index, {})

        def decoded(key):
            return index_values.get(key)

        def raw(data_id, *, signed=False):
            return self._realtime_raw_value(cluster_index, data_id, signed=signed)

        def scaled(data_id, *, signed=False, scale=1):
            return self._scaled_realtime_raw(cluster_index, data_id, signed=signed, scale=scale)

        max_voltage_pos = raw(VAR_SYS_MAXV_POSI)
        min_voltage_pos = raw(VAR_SYS_MINV_POSI)
        max_temp_pos = raw(VAR_SYS_MAXT_POSI)
        min_temp_pos = raw(VAR_SYS_MINT_POSI)
        indexed_pack_voltage = scaled(VAR_SYS_ANALOG_PACK_VOLT, scale=10)
        indexed_system_voltage = scaled(VAR_SYS_VOLT, scale=10)
        indexed_battery_voltage = scaled(VAR_SYS_ANALOG_BAT_VOLT, scale=10)
        indexed_max_discharge_current = scaled(0x1AD, scale=10)
        indexed_max_charge_current = scaled(0x1AF, scale=10)
        indexed_di_states = [
            self._to_input_state(decoded(f"di{state_index}"))
            for state_index in range(1, 13)
        ]
        indexed_relay_states = [
            self._to_output_state(decoded(f"relay{state_index}"))
            for state_index in range(1, 11)
        ]
        indexed_rt_values = [
            decoded(f"rt{state_index}")
            for state_index in range(1, 11)
        ]

        snapshot.update({
            "work_mode": self._first_monitor_value(decoded("work_mode"), snapshot.get("work_mode")),
            "run_status": self._first_monitor_value(raw(VAR_SYS_RUN_STATUS), snapshot.get("run_status")),
            "system_current": self._first_monitor_value(
                scaled(VAR_SYS_CURR, signed=True, scale=10),
                scaled(VAR_HALL_CURR, signed=True, scale=10),
                scaled(VAR_SHUNT_CURR, signed=True, scale=10),
                snapshot.get("system_current"),
            ),
            "hall_current": self._first_monitor_value(
                scaled(VAR_HALL_CURR, signed=True, scale=10),
                snapshot.get("hall_current"),
            ),
            "shunt_current": self._first_monitor_value(
                scaled(VAR_SHUNT_CURR, signed=True, scale=10),
                snapshot.get("shunt_current"),
            ),
            "battery_voltage": self._first_monitor_value(indexed_battery_voltage, snapshot.get("battery_voltage")),
            "system_voltage": self._first_monitor_value(
                indexed_system_voltage,
                indexed_battery_voltage,
                snapshot.get("system_voltage"),
            ),
            "pack_voltage": self._first_monitor_value(indexed_pack_voltage, snapshot.get("pack_voltage")),
            "soc": self._first_monitor_value(raw(VAR_SYS_SOC), snapshot.get("soc")),
            "display_soc": self._first_monitor_value(raw(VAR_SYS_DIS_SOC), snapshot.get("display_soc")),
            "soh": self._first_monitor_value(raw(VAR_SYS_SOH), snapshot.get("soh")),
            "diff_voltage": self._first_monitor_value(raw(VAR_SYS_DIFF_VOLT), snapshot.get("diff_voltage")),
            "diff_temp": self._first_monitor_value(raw(VAR_SYS_DIFF_TEMP, signed=True), snapshot.get("diff_temp")),
            "avg_voltage": self._first_monitor_value(raw(VAR_SYS_AVG_VOLT), decoded("avg_voltage"), snapshot.get("avg_voltage")),
            "avg_temp": self._first_monitor_value(raw(VAR_SYS_AVG_TEMP, signed=True), decoded("avg_temp"), snapshot.get("avg_temp")),
            "module_count": self._first_monitor_value(decoded("module_count"), snapshot.get("module_count")),
            "afe_count": self._first_monitor_value(decoded("afe_count"), snapshot.get("afe_count")),
            "online_lecu_num": self._first_monitor_value(decoded("online_lecu_num"), snapshot.get("online_lecu_num")),
            "pure_soc": self._first_monitor_value(raw(0x1C2), raw(0x358), raw(0x359), snapshot.get("pure_soc")),
            "revise_soc": self._first_monitor_value(raw(0x1C3), raw(0x346), raw(0x347), snapshot.get("revise_soc")),
            "revise_soc_temp": self._first_monitor_value(raw(0x1C4), raw(0x348), raw(0x349), snapshot.get("revise_soc_temp")),
            "fuzzy_soc": self._first_monitor_value(raw(0x1C7), raw(0x34E), raw(0x34F), snapshot.get("fuzzy_soc")),
            "cell_max_soc": self._first_monitor_value(raw(0x1C0), raw(0x354), raw(0x355), snapshot.get("cell_max_soc")),
            "cell_min_soc": self._first_monitor_value(raw(0x1C1), raw(0x356), raw(0x357), snapshot.get("cell_min_soc")),
            "cell_max_soc_temp": self._first_monitor_value(raw(0x1C6), raw(0x34C), raw(0x34D), snapshot.get("cell_max_soc_temp")),
            "cell_min_soc_temp": self._first_monitor_value(raw(0x1C5), raw(0x34A), raw(0x34B), snapshot.get("cell_min_soc_temp")),
            "max_cell_voltage": self._first_monitor_value(raw(VAR_SYS_CELL_VOLT_MAX), snapshot.get("max_cell_voltage")),
            "max_cell_voltage_module": self._first_monitor_value(
                None if max_voltage_pos is None else ((max_voltage_pos >> 8) & 0xFF),
                snapshot.get("max_cell_voltage_module"),
            ),
            "max_cell_voltage_index": self._first_monitor_value(
                None if max_voltage_pos is None else (max_voltage_pos & 0xFF),
                snapshot.get("max_cell_voltage_index"),
            ),
            "min_cell_voltage": self._first_monitor_value(raw(VAR_SYS_CELL_VOLT_MIN), snapshot.get("min_cell_voltage")),
            "min_cell_voltage_module": self._first_monitor_value(
                None if min_voltage_pos is None else ((min_voltage_pos >> 8) & 0xFF),
                snapshot.get("min_cell_voltage_module"),
            ),
            "min_cell_voltage_index": self._first_monitor_value(
                None if min_voltage_pos is None else (min_voltage_pos & 0xFF),
                snapshot.get("min_cell_voltage_index"),
            ),
            "max_cell_temp": self._first_monitor_value(
                scaled(VAR_SYS_CELL_TEMP_MAX, signed=True, scale=10),
                snapshot.get("max_cell_temp"),
            ),
            "max_cell_temp_module": self._first_monitor_value(
                None if max_temp_pos is None else ((max_temp_pos >> 8) & 0xFF),
                snapshot.get("max_cell_temp_module"),
            ),
            "max_cell_temp_index": self._first_monitor_value(
                None if max_temp_pos is None else (max_temp_pos & 0xFF),
                snapshot.get("max_cell_temp_index"),
            ),
            "min_cell_temp": self._first_monitor_value(
                scaled(VAR_SYS_CELL_TEMP_MIN, signed=True, scale=10),
                snapshot.get("min_cell_temp"),
            ),
            "min_cell_temp_module": self._first_monitor_value(
                None if min_temp_pos is None else ((min_temp_pos >> 8) & 0xFF),
                snapshot.get("min_cell_temp_module"),
            ),
            "min_cell_temp_index": self._first_monitor_value(
                None if min_temp_pos is None else (min_temp_pos & 0xFF),
                snapshot.get("min_cell_temp_index"),
            ),
            "remaining_discharge_kwh": self._first_monitor_value(raw(0x252), snapshot.get("remaining_discharge_kwh")),
            "remaining_charge_kwh": self._first_monitor_value(raw(0x253), snapshot.get("remaining_charge_kwh")),
            "single_charge_kwh": self._first_monitor_value(raw(0x1FD), snapshot.get("single_charge_kwh")),
            "single_discharge_kwh": self._first_monitor_value(raw(0x1FE), snapshot.get("single_discharge_kwh")),
            "max_discharge_current": self._first_monitor_value(indexed_max_discharge_current, snapshot.get("max_discharge_current")),
            "max_charge_current": self._first_monitor_value(indexed_max_charge_current, snapshot.get("max_charge_current")),
            "hvil_pwm_freq": self._first_monitor_value(decoded("hvil_pwm_freq"), raw(PAR_SYS_OUTPUT_HVIL_FREQ), snapshot.get("hvil_pwm_freq")),
            "hvil_pwm_duty": self._first_monitor_value(decoded("hvil_pwm_duty"), raw(PAR_SYS_OUTPUT_HVIL_DUTY_RATIO), snapshot.get("hvil_pwm_duty")),
            "board_temp1": self._first_monitor_value(decoded("board_temp1"), snapshot.get("board_temp1")),
            "board_temp2": self._first_monitor_value(decoded("board_temp2"), snapshot.get("board_temp2")),
        })
        snapshot["max_discharge_power"] = self._derive_power_kw(
            snapshot.get("pack_voltage"),
            snapshot.get("max_discharge_current"),
        )
        snapshot["max_charge_power"] = self._derive_power_kw(
            snapshot.get("pack_voltage"),
            snapshot.get("max_charge_current"),
        )
        if any(state is not None for state in indexed_di_states):
            snapshot["di_states"] = indexed_di_states
        if any(state is not None for state in indexed_relay_states):
            snapshot["relay_states"] = indexed_relay_states
        if any(value is not None for value in indexed_rt_values):
            snapshot["rt_values"] = indexed_rt_values
        return snapshot


    def _refresh_realtime_monitor_page(self):
        if not hasattr(self, "S27"):
            return
        cluster_index = self._active_cluster_index()
        address = getattr(self, "selected_cluster_address", "")
        self.S27.set_cluster_context(cluster_index, address)
        if cluster_index <= 0:
            self.S27.clear_values()
            self.S27.set_status_text("当前没有可用的簇。")
            return
        snapshot = self._build_realtime_monitor_snapshot()
        self.S27.update_snapshot(snapshot)
        self.S27.set_status_text(f"簇{cluster_index} ({address}) 监控数据由请求索引后台刷新。")


    def _refresh_realtime_monitor_page_if_visible(self):
        if getattr(self, "table_index", None) == self._realtime_monitor_tab_index():
            self._refresh_realtime_monitor_page()


    def _set_factory_status(self, mode_value=None, text=None, status=None):
        if text is None:
            if mode_value is None:
                text = "工装状态: 未知"
                status = status or "warning"
            elif int(mode_value) == WORK_MODE_GZ_TEST:
                text = "工装状态: 开"
                status = status or "success"
            else:
                text = "工装状态: 关"
                status = status or "warning"
        self._set_status_pill(getattr(self, "factory_status_label", None), text, status or "info")


    def _host_control_ready(self):
        if not getattr(self, "can_ready", False) or getattr(self, "c", None) is None:
            self.S17.set_status_text("CAN未连接，无法执行主机控制命令。", failed=True)
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再执行主机控制命令。")
            return False
        if self._active_cluster_index() <= 0:
            self.S17.set_status_text("未选择目标簇。", failed=True)
            QMessageBox.warning(self, "未选择簇", "请先选择目标簇。")
            return False
        return True


    def _diag_addr(self, cluster_index):
        return int(str(config["ADDRESLIST"][int(cluster_index)]), 16)


    def _diag_request_id(self, cluster_index, command_pf):
        target = self._diag_addr(cluster_index)
        source = int(str(config.get("IPCaddr", "F2")), 16)
        return 0x18000000 | (int(command_pf) << 16) | (target << 8) | source


    def _diag_response_id(self, cluster_index, response_pf):
        source = self._diag_addr(cluster_index)
        target = int(str(config.get("IPCaddr", "F2")), 16)
        return 0x18000000 | (int(response_pf) << 16) | (target << 8) | source


    def _flush_diag_rx(self):
        self._diag_frame_backlog = []
        flushed_count = 0
        for _ in range(4):
            frames = self.c.receive_frames(max_count=200, timeout_ms=0)
            if not frames:
                break
            flushed_count += len(frames)
        if flushed_count:
            self.rx_frame_count += flushed_count
            self._update_rx_status()


    def _pop_diag_backlog(self, expected_id, predicate):
        backlog = getattr(self, "_diag_frame_backlog", [])
        for index, frame in enumerate(backlog):
            if int(frame.frame_id) == int(expected_id) and predicate(frame):
                return backlog.pop(index)
        return None


    def _wait_diag_frame(self, expected_id, predicate, timeout_s, label):
        deadline = time.monotonic() + max(float(timeout_s), 0.0)
        while time.monotonic() <= deadline:
            frame = self._pop_diag_backlog(expected_id, predicate)
            if frame is not None:
                return frame

            remaining_ms = max(int((deadline - time.monotonic()) * 1000), 1)
            frames = self.c.receive_frames(max_count=200, timeout_ms=min(remaining_ms, 50))
            if frames:
                self.rx_frame_count += len(frames)
                self._update_rx_status()

            for frame_index, frame in enumerate(frames):
                if int(frame.frame_id) != int(expected_id):
                    continue
                if predicate(frame):
                    self._diag_frame_backlog.extend(
                        later_frame
                        for later_frame in frames[frame_index + 1:]
                        if int(later_frame.frame_id) == int(expected_id)
                    )
                    return frame
                self._diag_frame_backlog.append(frame)
            QApplication.processEvents()
        raise RuntimeError(f"{label}响应超时")


    def _send_diag_request(self, cluster_index, command_pf, payload, label):
        data = list(payload[:8]) if isinstance(payload, (list, tuple)) else list(bytes(payload)[:8])
        data = (data + [0] * 8)[:8]
        result = self.c.Transmit(
            self._diag_request_id(cluster_index, command_pf),
            data,
            extern_flag=True,
            data_len=8,
        )
        if result <= 0:
            raise RuntimeError(f"{label}发送失败")
        return result


    def _read_data_u16_sync(self, cluster_index, data_id, timeout_s=1.0, retries=0):
        data_id = int(data_id)
        payload = data_id.to_bytes(4, byteorder="little", signed=False) + b"\x00\x00\x00\x00"
        expected_id = self._diag_response_id(cluster_index, RESP_READ_VAR)
        last_error = None
        for attempt in range(max(int(retries), 0) + 1):
            try:
                self._send_diag_request(cluster_index, CMD_READ_VAR, payload, "读取索引")
                frame = self._wait_diag_frame(
                    expected_id,
                    lambda frame: (
                        len(frame.data) >= 7
                        and int.from_bytes(frame.data[:4], byteorder="little", signed=False) == data_id
                    ),
                    timeout_s,
                    "读取索引",
                )
                if not frame.data[6]:
                    raise RuntimeError(f"索引 0x{data_id:X} 读取被下位机拒绝")
                return int.from_bytes(frame.data[4:6], byteorder="little", signed=False)
            except Exception as exc:
                last_error = exc
                if attempt < max(int(retries), 0):
                    time.sleep(0.03)
                    continue
                raise
        raise last_error or RuntimeError("读取索引失败")


    def _write_data_u16_sync(self, cluster_index, data_id, value, timeout_s=1.0):
        data_id = int(data_id)
        value = int(value) & 0xFFFF
        payload = (
            data_id.to_bytes(4, byteorder="little", signed=False)
            + value.to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
        )
        expected_id = self._diag_response_id(cluster_index, RESP_WRITE_VAR)
        self._send_diag_request(cluster_index, CMD_WRITE_VAR, payload, "写入索引")
        frame = self._wait_diag_frame(
            expected_id,
            lambda frame: (
                len(frame.data) >= 6
                and int.from_bytes(frame.data[:4], byteorder="little", signed=False) == data_id
            ),
            timeout_s,
            "写入索引",
        )
        accepted = int.from_bytes(frame.data[4:6], byteorder="little", signed=False)
        if not accepted:
            raise RuntimeError(f"索引 0x{data_id:X} 写入被下位机拒绝")
        return True


    def _authorize_control_sync(self, cluster_index, timeout_s=1.0):
        seed_request = bytes((0x02, 0x27, 0x11, 0, 0, 0, 0, 0))
        expected_id = self._diag_response_id(cluster_index, RESP_DECODE_SECU)
        self._send_diag_request(cluster_index, CMD_DECODE_SECU, seed_request, "工装解锁种子请求")
        seed_frame = self._wait_diag_frame(
            expected_id,
            lambda frame: (
                len(frame.data) >= 7
                and (
                    frame.data[:3] == bytes((0x06, 0x67, 0x11))
                    or frame.data[:2] == bytes((0x03, 0x7F))
                )
            ),
            timeout_s,
            "工装解锁种子",
        )
        if seed_frame.data[:3] != bytes((0x06, 0x67, 0x11)):
            raise RuntimeError("工装解锁种子请求被下位机拒绝")

        seed = int.from_bytes(seed_frame.data[3:7], byteorder="big", signed=False)
        key = CanDiag_Seed_2_Key(seed)
        key_payload = bytes(
            (
                0x06,
                0x27,
                0x12,
                (key >> 24) & 0xFF,
                (key >> 16) & 0xFF,
                (key >> 8) & 0xFF,
                key & 0xFF,
                0,
            )
        )
        self._send_diag_request(cluster_index, CMD_DECODE_SECU, key_payload, "工装解锁密钥")
        key_frame = self._wait_diag_frame(
            expected_id,
            lambda frame: (
                len(frame.data) >= 3
                and (
                    frame.data[:3] == bytes((0x02, 0x67, 0x12))
                    or frame.data[:2] == bytes((0x03, 0x7F))
                )
            ),
            timeout_s,
            "工装解锁密钥",
        )
        if key_frame.data[:3] != bytes((0x02, 0x67, 0x12)):
            raise RuntimeError("工装解锁密钥被下位机拒绝")
        return True


    def _execute_control_command_sync(
        self,
        cluster_index,
        control_code,
        para1=0,
        para2=0,
        para3=0,
        timeout_s=1.0,
        label="控制命令",
        authorize=True,
    ):
        if authorize:
            self._authorize_control_sync(cluster_index, timeout_s=timeout_s)
        payload = (
            int(control_code).to_bytes(2, byteorder="little", signed=False)
            + (int(para1) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
            + (int(para2) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
            + (int(para3) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
        )
        expected_id = self._diag_response_id(cluster_index, RESP_CTRL_HARDWARE)
        self._send_diag_request(cluster_index, CMD_CTRL_HARDWARE, payload, label)
        frame = self._wait_diag_frame(
            expected_id,
            lambda frame: len(frame.data) >= 1,
            timeout_s,
            label,
        )
        if frame.data[0] != 1:
            raise RuntimeError(f"{label}被下位机拒绝")
        return True


    def _set_factory_mode_sync(self, cluster_index, enabled):
        mode = WORK_MODE_GZ_TEST if enabled else WORK_MODE_NORMAL
        self._execute_control_command_sync(
            cluster_index,
            CTRL_WORK_MODE,
            para1=0xFFFF,
            para2=mode,
            para3=0xFFFF,
            timeout_s=1.0,
            label="工装模式切换",
            authorize=True,
        )
        self._set_factory_status(mode)
        self.S17.update_snapshot({"work_mode": mode})
        return mode


    def _require_factory_mode_sync(self, cluster_index):
        mode = self._read_data_u16_sync(cluster_index, VAR_SYS_WORK_MODE, timeout_s=0.8, retries=1)
        self._set_factory_status(mode)
        if int(mode) != WORK_MODE_GZ_TEST:
            raise RuntimeError("当前工装模式未开启，请先点击顶部“工装开”。")
        return mode


    def _run_host_control_action(self, action, error_title="主机控制失败", revert=None):
        if not self._host_control_ready():
            if callable(revert):
                revert()
            return False
        active_timers = self._pause_history_log_timers()
        try:
            self._flush_diag_rx()
            action()
            return True
        except Exception as exc:
            if callable(revert):
                revert()
            self.S17.set_status_text(str(exc), failed=True)
            QMessageBox.critical(self, error_title, str(exc))
            return False
        finally:
            self._resume_history_log_timers(active_timers)


    def _refresh_host_control_snapshot(self, show_status=False):
        if not getattr(self, "can_ready", False) or getattr(self, "c", None) is None:
            self.S17.update_snapshot({})
            self._set_factory_status(None)
            return
        if self._active_cluster_index() <= 0:
            self.S17.update_snapshot({})
            self._set_factory_status(None)
            return

        cluster_index = self._active_cluster_index()

        def action():
            snapshot = {}
            reads = (
                ("work_mode", VAR_SYS_WORK_MODE),
                ("soc", VAR_SYS_SOC),
                ("hvil_pwm_freq", PAR_SYS_OUTPUT_HVIL_FREQ),
                ("hvil_pwm_duty", PAR_SYS_OUTPUT_HVIL_DUTY_RATIO),
            )
            for key, data_id in reads:
                try:
                    snapshot[key] = self._read_data_u16_sync(cluster_index, data_id, timeout_s=0.5, retries=0)
                except Exception:
                    snapshot[key] = None

            relay_states = []
            for data_id in range(48, 58):
                try:
                    relay_states.append(bool(self._read_data_u16_sync(cluster_index, data_id, timeout_s=0.25, retries=0)))
                except Exception:
                    relay_states.append(False)
            snapshot["relay_states"] = relay_states

            self.S17.update_snapshot(snapshot)
            self._set_factory_status(snapshot.get("work_mode"))
            if show_status:
                self.S17.set_status_text(f"簇{cluster_index} ({self.selected_cluster_address}) 主机控制状态已刷新。")

        self._run_host_control_action(action, "刷新主机控制状态失败")


    def on_factory_mode_change(self, enabled):
        def action():
            mode = self._set_factory_mode_sync(self._active_cluster_index(), enabled)
            state_text = "开" if int(mode) == WORK_MODE_GZ_TEST else "关"
            self.S17.set_status_text(f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) 工装模式已切换为 {state_text}。")

        self._run_host_control_action(action, "工装模式切换失败")


    def on_host_control_read_indexes(self):
        def action():
            request_indexes = self.S17.get_request_indexes()
            read_count = 0
            error_count = 0
            for row_index, data_id in enumerate(request_indexes):
                if data_id is None:
                    self.S17.set_request_value(row_index, None, "")
                    continue
                try:
                    value = self._read_data_u16_sync(self._active_cluster_index(), data_id, timeout_s=0.8, retries=1)
                    self.S17.set_request_value(row_index, data_id, str(value))
                    read_count += 1
                except Exception:
                    self.S17.set_request_value(row_index, data_id, "ERR")
                    error_count += 1
            self.S17.set_status_text(
                f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) 索引读取完成，成功 {read_count} 项，失败 {error_count} 项。"
            )

        try:
            self.S17.get_request_indexes()
        except ValueError as exc:
            QMessageBox.warning(self, "索引输入错误", str(exc))
            return
        self._run_host_control_action(action, "索引读取失败")


    def on_host_control_write_indexes(self):
        try:
            write_entries = self.S17.get_request_write_entries()
        except ValueError as exc:
            QMessageBox.warning(self, "索引输入错误", str(exc))
            return
        if not write_entries:
            QMessageBox.warning(self, "没有可写入的索引值", "请先填写至少一项索引值后再写入。")
            return

        def action():
            self._require_factory_mode_sync(self._active_cluster_index())
            write_count = 0
            error_count = 0
            for row_index, data_id, value in write_entries:
                try:
                    self._write_data_u16_sync(self._active_cluster_index(), data_id, value, timeout_s=1.0)
                    self.S17.set_request_value(row_index, data_id, self.S17.index_value_edits[row_index].text().strip())
                    write_count += 1
                except Exception:
                    error_count += 1
            self.S17.set_status_text(
                f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) 索引写入完成，成功 {write_count} 项，失败 {error_count} 项。"
            )

        self._run_host_control_action(action, "索引写入失败")


    def on_host_control_channel_toggled(self, channel_id, checked):
        checkbox = self.S17.channel_checks[channel_id]

        def revert():
            checkbox.blockSignals(True)
            checkbox.setChecked(not checked)
            checkbox.blockSignals(False)

        def action():
            self._require_factory_mode_sync(self._active_cluster_index())
            self._execute_control_command_sync(
                self._active_cluster_index(),
                CTRL_CHNNEL,
                para1=int(channel_id),
                para2=1 if checked else 0,
                timeout_s=1.0,
                label=f"{checkbox.text()} 输出控制",
                authorize=True,
            )
            state_text = "合" if checked else "断"
            self.S17.set_status_text(
                f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) {checkbox.text()} 已切换为 {state_text}。"
            )

        self._run_host_control_action(action, "输出控制失败", revert=revert)


    def on_host_control_write_hvil(self):
        freq = self.S17.hvil_freq_target.value()
        duty = self.S17.hvil_duty_target.value()

        def action():
            self._require_factory_mode_sync(self._active_cluster_index())
            self._write_data_u16_sync(self._active_cluster_index(), PAR_SYS_OUTPUT_HVIL_FREQ, freq, timeout_s=1.0)
            self._write_data_u16_sync(self._active_cluster_index(), PAR_SYS_OUTPUT_HVIL_DUTY_RATIO, duty, timeout_s=1.0)
            self.S17.hvil_freq_current.setText(f"{freq / 10:.1f} Hz")
            self.S17.hvil_duty_current.setText(f"{duty / 10:.1f} %")
            self.S17.set_status_text(
                f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) HVIL PWM 已写入，频率 {freq}，占空比 {duty}。"
            )

        self._run_host_control_action(action, "HVIL PWM写入失败")


    def on_host_control_write_soc(self):
        soc_value = self.S17.soc_target.value()

        def action():
            self._require_factory_mode_sync(self._active_cluster_index())
            self._write_data_u16_sync(self._active_cluster_index(), VAR_SYS_USER_SET_SOC, soc_value, timeout_s=1.0)
            self.S17.soc_current.setText(f"{soc_value / 10:.1f} %")
            self.S17.set_status_text(f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) SOC 已写入 {soc_value}。")

        self._run_host_control_action(action, "SOC写入失败")


    def on_host_control_restore_factory(self):
        self._run_host_para_command(
            CTRL_PARA_CONFIG_RESET_FACTORY,
            "恢复全站出厂参数",
            "已恢复全站出厂参数。",
        )


    def on_host_control_restore_run(self):
        self._run_host_para_command(
            CTRL_PARA_CONFIG_RESET_RUN,
            "恢复全局运行参数",
            "已恢复全局运行参数。",
        )


    def on_host_control_restore_product_info(self):
        self._run_host_para_command(
            CTRL_PARA_CONFIG_RESET_PRODUCT_INFO,
            "恢复产品信息",
            "已恢复产品信息。",
        )


    def on_host_control_save_flash(self):
        self._run_host_para_command(
            CTRL_PARA_CONFIG_SAVE_ALL_TO_FLASH,
            "保存参数到FLASH",
            "参数已保存到FLASH。",
        )


    def _run_host_para_command(self, para2, title, success_text):
        def action():
            self._require_factory_mode_sync(self._active_cluster_index())
            self._execute_control_command_sync(
                self._active_cluster_index(),
                CTRL_PARA_CONFIG,
                para2=int(para2),
                timeout_s=1.2,
                label=title,
                authorize=True,
            )
            self.S17.set_status_text(f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) {success_text}")

        self._run_host_control_action(action, f"{title}失败")


    def on_host_control_sync_time(self):
        def action():
            current_time = datetime.now()
            weekday = current_time.isoweekday() % 7
            payload = bytes(
                (
                    max(current_time.year - 2000, 0) & 0xFF,
                    current_time.month & 0xFF,
                    current_time.day & 0xFF,
                    current_time.hour & 0xFF,
                    current_time.minute & 0xFF,
                    current_time.second & 0xFF,
                    weekday & 0xFF,
                    0,
                )
            )
            expected_id = self._diag_response_id(self._active_cluster_index(), RESP_SET_TIME)
            self._send_diag_request(self._active_cluster_index(), CMD_SET_TIME, payload, "同步系统时间")
            frame = self._wait_diag_frame(
                expected_id,
                lambda frame: len(frame.data) >= 7 and frame.data[:6] == payload[:6],
                1.0,
                "同步系统时间",
            )
            if not frame.data[6]:
                raise RuntimeError("同步系统时间被下位机拒绝")
            self.S17.set_status_text(
                f"簇{self._active_cluster_index()} ({self.selected_cluster_address}) 系统时间已同步到 {current_time:%Y-%m-%d %H:%M:%S}。"
            )

        self._run_host_control_action(action, "同步系统时间失败")


    def _stop_can_timers(self):
        for timer_name in ("send_time", "send_time1", "timer1", "timerResData", "timerDI", "timer_Forcecharge"):
            timer = getattr(self, timer_name, None)
            if timer is not None and timer.isActive():
                timer.stop()


    def _start_can_timers(self):
        self.send_time.start(200)
        self.send_time1.start(10)
        self.timer1.start(10)
        if self._logging_enabled():
            self._ensure_session_log_manager().set_enabled(True)
            self._attach_log_manager_to_can()
            self.timerResData.start(1000)
        self._update_log_status()


    def _close_can_device(self):
        self._stop_can_timers()
        can_device = getattr(self, "c", None)
        if can_device is not None:
            try:
                can_device.log_manager = None
                can_device.close()
            except Exception as exc:
                print(f"close CAN failed: {exc}")
        self._set_bus_status(False, "CAN: 未连接", "warning")


    def _connect_can(self, show_dialog=False):
        self._stop_can_timers()
        self.rx_frame_count = 0
        self._update_rx_status()
        can_config = self._current_bus_config()
        config["SAVE_LOG"] = 1 if getattr(self, "save_log_checkbox", None) and self.save_log_checkbox.isChecked() else 0

        if getattr(self, "c", None) is not None:
            try:
                self.c.close()
            except Exception as exc:
                print(f"close old CAN failed: {exc}")

        self.c = Communication()
        self._attach_log_manager_to_can()
        stat, msg = self.c.set_can_board_configuration(
            can_type=can_config["can_type"],
            can_idx=can_config["can_idx"],
            chn=can_config["chn"],
            baud_rate=can_config["baud_rate"],
        )
        if not stat:
            self._set_bus_status(False, f"CAN: 配置失败 {msg}", "danger")
            if show_dialog:
                QMessageBox.warning(self, "CAN配置失败", msg)
            return False

        try:
            self.c.open_new()
        except Exception as exc:
            error_msg = str(exc)
            self._set_bus_status(False, "CAN: 打开失败", "danger")
            if show_dialog:
                QMessageBox.warning(self, "CAN打开失败", error_msg)
            return False

        self._save_bus_config(can_config)
        self._set_bus_status(
            True,
            f"CAN: 设备{can_config['can_idx']} 通道{can_config['chn']} {can_config['baud_rate']}k",
            "success",
        )
        self._start_can_timers()
        return True


    def on_apply_bus_settings(self):
        self._connect_can(show_dialog=True)


    def closeEvent(self, event):
        self._close_can_device()
        self._close_session_log()
        super().closeEvent(event)


    def init(self):
        self.can_ready = False
        self.rx_frame_count = 0
        self.c = None
        self._cluster_syncing = False
        self._setup_product_controls()
        self._load_bus_config_controls(load_can_board_config())
        self._configure_single_cluster_tab()
        self._hide_embedded_cluster_controls()
        self._set_bus_status(False, "CAN: 未连接", "warning")
        self._update_rx_status()

        # 创建一个QTimer对象
        self.send_time = QTimer(self)
        # 给QTimer设定一个时间，每到达这个时间一次就会调用一次该方法
        self.send_time.timeout.connect(self.CANCommunication)
        # 设置QTimer开始计时，且设定时间为1000ms
        self.send_time.start(200)

        self.send_time1 = QTimer(self)
        # 给QTimer设定一个时间，每到达这个时间一次就会调用一次该方法
        self.send_time1.timeout.connect(self.RequestAlarmData)
        # 设置QTimer开始计时，且设定时间为1000ms
        self.send_time1.start(10)

        # 逐行加载数据的定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_next_row)  # 逐行加载
        self.current_COUNT = 0
        # 开始定时器，每 10 毫秒加载一行
        # The alarm page now refreshes directly from CAN responses.

        #BAU请求数据定时器
        self.timer1 = QTimer(self)
        self.timer1.timeout.connect(self.RequestBAUVAR)
        self.timer1.timeout.connect(self.RequestBCUVAR)
        self.timer1.start(10)


        #设置告警级别定时器
        self.timer2 = QTimer(self)
        self.timer2.timeout.connect(self.AlarmLevel)
        self.timer2.start(1000)

        self.timerRealtimeMonitor = QTimer(self)
        self.timerRealtimeMonitor.timeout.connect(self._refresh_realtime_monitor_page_if_visible)
        self.timerRealtimeMonitor.start(500)

        self.timerActiveAlarm = QTimer(self)
        self.timerActiveAlarm.timeout.connect(self._refresh_active_alarm_page_if_visible)
        self.timerActiveAlarm.start(self.S28.refresh_interval_ms())


        #告警切换槽函数
        self.S21.comboBox.currentIndexChanged.connect(self.on_alarm_cluster_changed)



        self.timer_Forcecharge = QTimer(self)
        self.timer_Forcecharge.timeout.connect(self.ForceChargeOpenClose)
        #self.timer_Forcecharge.start(1)

        self.S17.read_indexes_button.clicked.connect(self.on_host_control_read_indexes)
        self.S17.write_indexes_button.clicked.connect(self.on_host_control_write_indexes)
        self.S17.write_hvil_button.clicked.connect(self.on_host_control_write_hvil)
        self.S17.write_soc_button.clicked.connect(self.on_host_control_write_soc)
        self.S17.restore_product_info_button.clicked.connect(self.on_host_control_restore_product_info)
        self.S17.sync_time_button.clicked.connect(self.on_host_control_sync_time)
        self.S17.restore_run_button.clicked.connect(self.on_host_control_restore_run)
        self.S17.restore_factory_button.clicked.connect(self.on_host_control_restore_factory)
        self.S17.save_flash_button.clicked.connect(self.on_host_control_save_flash)
        for channel_id, checkbox in self.S17.channel_checks.items():
            checkbox.toggled.connect(
                lambda checked, channel_id=channel_id: self.on_host_control_channel_toggled(channel_id, checked)
            )
        self.S21.button.clicked.connect(self.on_alarm_parameter_read)
        self.S28.read_button.clicked.connect(self.on_active_alarm_read)
        self.S28.auto_refresh_checkbox.toggled.connect(self.on_active_alarm_auto_refresh_toggled)
        self.S28.interval_spinbox.valueChanged.connect(self.on_active_alarm_interval_changed)
       # self.S21.button.clicked.connect(self.AlarmDatafh)


        self.S18.comboBox.currentIndexChanged.connect(self.S18currentIndexChanged)
        self.S19.comboBox.currentIndexChanged.connect(self.S18currentIndexChangedBAL)
        self.S20.comboBox.currentIndexChanged.connect(self.S20currentIndexChangedTem)
        self._connect_cluster_page_selectors()


        self.S25.moduleApplyRequested.connect(self.on_balance_control_apply)
        self.S25.moduleCloseRequested.connect(self.on_balance_control_close_module)
        self.S25.allCloseRequested.connect(self.on_balance_control_close_all)

        #DI状态
        self.timerDI = QTimer(self)
        self.timerDI.timeout.connect(self.DIState)
        self.timerDI.timeout.connect(self.DIStateBAU)
        #self.timerDI.start(1000)

        self.S22.pushButton.clicked.connect(self.DIStateStart)
        self.S22.pushButton_2.clicked.connect(self.DIStateClose)


        #参数管理
        self.S23.pushButton.clicked.connect(self.ParProcess)
        self.S26.read_button.clicked.connect(self.on_history_log_read)
        self.S26.stop_button.clicked.connect(self.on_history_log_stop)
        self.S26.save_button.clicked.connect(self.on_history_log_save)
        self.S26.clear_table_button.clicked.connect(self.on_history_log_clear_table)
        self.S26.clear_device_button.clicked.connect(self.on_history_log_clear_device)

        self.S21.submit_button.clicked.connect(self.on_alarm_parameter_save_flash)

        self.FLAG_WORK_MODE = 1


        #修改告警槽函数
        self.S21.modify_button.clicked.connect(self.on_alarm_parameter_write_current)


        #告警修改索引
        self.AlarmIndex = 0
        self.alarm_request_limit = self.S21.alarm_count() * 32
        self.pending_alarm_writes = {}
        self.S21.set_cluster_context()


        self.table_index = 1
        self._set_active_cluster(
            getattr(self, "selected_cluster_index", self._default_cluster_option_index()),
            refresh=False,
            source="init",
        )


        self.history_log_stop_requested = False
        self.tabWidget.currentChanged.connect(self.on_tab_changed)

        self.BAL_index = 0
        self.DXYC_index= 0

        #参数查询
        #BCU参数查询1
        self.S23.pushButton_14.clicked.connect(lambda:self.BCUVARSearch(1))
        # BCU参数查询2
        self.S23.pushButton_16.clicked.connect(lambda:self.BCUVARSearch(2))
        # BCU参数查询3
        self.S23.pushButton_18.clicked.connect(lambda: self.BCUVARSearch(3))
        # BCU参数查询4
        self.S23.pushButton_20.clicked.connect(lambda: self.BCUVARSearch(4))


        #BAU参数查询
        self.S23.pushButton_6.clicked.connect(lambda: self.BAUVARSearch(1))
        self.S23.pushButton_8.clicked.connect(lambda: self.BAUVARSearch(2))
        self.S23.pushButton_10.clicked.connect(lambda: self.BAUVARSearch(3))
        self.S23.pushButton_12.clicked.connect(lambda: self.BAUVARSearch(4))


        self.LECU_LOW = [0 for i in range(config["LECU_NUM"])]
        self.LECU_HIGH =[0 for i in range(config["LECU_NUM"])]

        self.LECU1_LOW = 0
        self.LECU1_HIGH = 0

        self.LECU2_LOW = 0
        self.LECU2_HIGH = 0

        self.PACK_LIFE_HIGH = 0
        self.PACK_LIFE_LOW = 0

        self.PACK_TEMP_LIFE_HIGH = 0
        self.PACK_TEMP_LIFE_LOW = 0


        self.BCUSignalQ = BCUSignalQ
        self.BCUSignalQ_index = 0

        self.BAUSignalQ = BAUSignalQ
        self.BAUSignalQ_index = 0

        self.BCUSignalQ_DXYC=BCUSignalQ_DXYC
        self.BCUSignalQ_DXYC_index = 0
        self.realtime_monitor_signal_ids = REALTIME_MONITOR_SIGNAL_IDS
        self.realtime_monitor_signal_definitions = REALTIME_MONITOR_SIGNAL_DEFINITIONS
        self.realtime_monitor_definitions_by_id = {}
        for definition in self.realtime_monitor_signal_definitions:
            data_id = int(definition["data_id"])
            self.realtime_monitor_definitions_by_id.setdefault(data_id, []).append(definition)
        self.realtime_monitor_query_index = 0
        self.realtime_monitor_raw_words = {
            cluster_index: {}
            for cluster_index, _address in getattr(self, "cluster_options", [])
        }
        self.realtime_monitor_values = {
            cluster_index: {}
            for cluster_index, _address in getattr(self, "cluster_options", [])
        }

        self.last_dx_time = 0
        self.last_dy_time = 0
        self.last_bal_time = 0
        self.last_tem_time = 0
        self.voltage_snapshot_dirty = False
        self.temperature_snapshot_dirty = False
        self.balance_snapshot_dirty = False
        self.abnormal_snapshot_dirty = False

        self.ResDataRec =[copy.deepcopy(ResDataRec) for i in range(config["BCU_NUM"]+1)]


        self.timerResData = QTimer(self)
        self.timerResData.timeout.connect(self.SaveRunData)
        # Started after CAN opens successfully when logging is enabled.
        self._connect_can(show_dialog=False)



    def on_tab_changed(self, index):
        # 触发的函数：根据选中的标签页输出信息
        if index == self.ZERO_TAB_INDEX or self._is_hidden_cluster_tab_index(index):
            self.tabWidget.setCurrentIndex(self.CLUSTER_TAB_INDEX)
            return
        self.table_index = index
        if index == self.CLUSTER_TAB_INDEX:
            if self._active_cluster_index() == 0:
                default_option_index = self._default_cluster_option_index()
                default_cluster_index = self.cluster_options[default_option_index][0]
                self._set_active_cluster(default_cluster_index, refresh=False, source="tab")
        else:
            self._sync_page_cluster_combo_boxes(self._active_cluster_index())
            if index == self._active_alarm_tab_index():
                self._refresh_active_alarm_page_if_visible(force=True)
            if index == self._realtime_monitor_tab_index():
                self._refresh_realtime_monitor_page()
            if index == self._control_tab_index():
                self._refresh_host_control_snapshot(show_status=True)





    def showTime(self):
        pass
        #t = time.time()
        #self.lineEdit.setText(str(t))


    def CANCommunication(self):
        if not getattr(self, "can_ready", False) or getattr(self, "c", None) is None:
            return
        try:
            self.rec = self.c._PrintReceiveData()
        except Exception as exc:
            self._stop_can_timers()
            self._set_bus_status(False, f"CAN: 接收失败 {exc}", "danger")
            return
        if self.rec:
            self.rx_frame_count += self.rec
            self._update_rx_status()
        ID = ""
        #time.sleep(1)
        for i in range(0,self.rec):
            #pass
            ID = "NONE"
            try:
                ID = hex(self.c.ReceiveBuffer[i].ID)  # 输出当前帧的ID

                byte0 = self.c.ReceiveBuffer[i].Data[0]
                byte1 = self.c.ReceiveBuffer[i].Data[1]
                byte2 = self.c.ReceiveBuffer[i].Data[2]
                byte3 = self.c.ReceiveBuffer[i].Data[3]
                byte4 = self.c.ReceiveBuffer[i].Data[4]
                byte5 = self.c.ReceiveBuffer[i].Data[5]
                byte6 = self.c.ReceiveBuffer[i].Data[6]
                byte7 = self.c.ReceiveBuffer[i].Data[7]
            except:
                pass



            #################################################################################################################
            #index = self.table_index
            for index in range(config["BCU_NUM"]+1):
                # if (("0x1881F2" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                #     bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                #     if ((bauvarid == 0x9040D) and (config["Has_N"])==255):
                #         config["Has_N"] = byte4 + byte5 * 256
                if index != self._active_cluster_index():
                    continue
                addr = config["ADDRESLIST"][index]
                display_index = self.CLUSTER_TAB_INDEX
                if (("0x1881F2" + str(addr).casefold()).casefold() == ID.casefold()):
                    data_id = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256 * 256
                    raw_word = self._u16_from_response(byte4, byte5)
                    self._cache_realtime_monitor_index_value(index, data_id, raw_word)
                if index-1<config["BCU_NUM"]:

                    #带中线
                    if config["Has_N"]==1:
                        STIID("0x1201ef"+addr,ID,self.TW[display_index][0], 0, "霍尔电流", str(Unsignal_Change(byte3* 256+byte2)/10), "A",self.ResDataRec[index],0)
                        STIID("0x1201ef"+addr,ID,self.TW[display_index][0], 1, "B端电压", str((byte1* 256 + byte0 )/10), "V",self.ResDataRec[index],0)
                        STIID("0x1201ef"+addr,ID,self.TW[display_index][0], 2, "P端电压", str((byte7 * 256 + byte6) / 10), "V",self.ResDataRec[index],0)
                        STIID("0x1201ef"+addr,ID,self.TW[display_index][0], 3, "运行状态", str((byte4)), "0、初始 1、自测 2、准备 3、预充 4、高压待机 5、放电 6、充电 7、放空 8、充满 9、错误 10、切断 ",self.ResDataRec[index],0)
                        STIID("0x1202EF"+addr,ID,self.TW[display_index][0],4,"SOC",str((byte7 * 256 + byte6)),"0.1%",self.ResDataRec[index],0)
                        STIID("0x1203EF"+addr,ID,self.TW[display_index][0],5,"最大单体电压",str((byte3* 256+byte2)),"mv",self.ResDataRec[index],0)
                        STIID("0x1203EF"+addr, ID, self.TW[display_index][0], 6, "最小单体电压", str((byte7 * 256 + byte6)), "mv",self.ResDataRec[index],0)
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][0], 7, "充电继电器", str(byte2&0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],0)
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][0], 8, "放电继电器", str(byte2>>4 & 0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],0)
                        STIID("0x1228EF"+addr, ID, self.TW[display_index][0], 9, "最严重告警等级", str((byte1* 256 + byte0 )&0xFF), "",self.ResDataRec[index],0)

                        if (byte0)==index:
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][0], 10, "BAU控制命令", str(byte4), "",self.ResDataRec[index],0)
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][0], 11, "BCU地址", str(byte0), "",self.ResDataRec[index],0)
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][0], 12, "是否强充", str(byte1), "",self.ResDataRec[index],0)
                        STIID("0x1207EF"+addr, ID, self.TW[display_index][0], 13, "最大允许充电电流", str((byte1* 256 + byte0 )/10), "A",self.ResDataRec[index],0)
                        STIID("0x1207EF"+addr, ID, self.TW[display_index][0], 14, "最大允许放电电流", str((byte3* 256 + byte2 )/10), "A",self.ResDataRec[index],0)

                        # STIID("0x18FE10"+addr,ID,self.TW[display_index][0],15,"MAX_SOC_UP",str(byte1* 256 + byte0 ),"0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE10" + addr, ID, self.TW[display_index][0], 16, "MIN_SOC_UP", str(byte3 * 256 + byte2), "0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE10" + addr, ID, self.TW[display_index][0], 17, "PURE_SOC_UP", str(byte5 * 256 + byte4), "0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE10" + addr, ID, self.TW[display_index][0], 18, "REVISE_SOC_UP", str(byte7 * 256 + byte6), "0.1%",self.ResDataRec[index],0)
                        #
                        # STIID("0x18FE11"+addr,ID,self.TW[display_index][0],19,"REVISESOC_TEMP_UP",str(byte1* 256 + byte0 ),"0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE11" + addr, ID, self.TW[display_index][0], 20, "MIN_SOC_TEMP_UP", str(byte3 * 256 + byte2), "0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE11" + addr, ID, self.TW[display_index][0], 21, "MAX_SOC_TEMP_UP", str(byte5 * 256 + byte4), "0.1%",self.ResDataRec[index],0)
                        # STIID("0x18FE11" + addr, ID, self.TW[display_index][0], 22, "FUZZY_SOC_UP", str(byte7 * 256 + byte6), "0.1%",self.ResDataRec[index],0)
                        # if ((byte0>>7)&0x01==0) and (byte3*256+byte2)!=0x1212 and ((byte3*256+byte2)!=0x1212) and (byte0 !=0xFD) and (byte0 !=0xFE) and (byte0 !=0xFF):
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][0], 23, "告警ID", str(byte0&0x7F), "",self.ResDataRec[index],0)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][0], 24, "告警等级", str(byte1), "",self.ResDataRec[index],0)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][0], 25, "告警阈值", str(byte5 * 256 + byte4), "",self.ResDataRec[index],0)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][0], 26, "告警值", str(byte7 * 256 + byte6), "",self.ResDataRec[index],0)



                        # STIID("0x18FE17" + addr, ID, self.TW[display_index][0], 30, "OCVMAXSOC_UP", str(byte1 * 256 + byte0), "OCV矫正最大SOC",self.ResDataRec[index],0)
                        # STIID("0x18FE17" + addr, ID, self.TW[display_index][0], 31, "OCVMINSOC_UP", str(byte3 * 256 + byte2), "OCV矫正最小SOC",self.ResDataRec[index],0)
                        # STIID("0x18FE17" + addr, ID, self.TW[display_index][0], 32, "OCV_UPDT_COUNT_UP", str(byte4), "OCV更新次数",self.ResDataRec[index],0)
                        # STIID("0x18FE17" + addr, ID, self.TW[display_index][0], 33, "OCV_FAIL_CODE_UP", str(byte5), "OCV无法原因标志(NA)：0-正常；bit0-最大电芯电压或最小电芯电压处于平台区；bit1-休眠时间不满足；bit2-初始上电电流过大；bit3-电压超超范围无效；bit4-电压处于平台期；bit5-温度无效；bit6-静置时间不满足；bit-7；部分电芯电压处于平台区。",self.ResDataRec,0)
                        #STIID("0x18FE17" + addr, ID, self.TW[display_index][0], 34, "FULL_CHRG_FLG_UP", str(byte6),"满充满放标志，0-默认；1-满充；",self.ResDataRec[index],0)

                        STIID("0x18FE14" + addr, ID, self.TW[display_index][0], 35, "TOTAL_CHRG_AH", str(byte1 * 256 + byte0), "0.01AH",self.ResDataRec[index],0)
                        STIID("0x18FE14" + addr, ID, self.TW[display_index][0], 36, "TOTAL_DSCH_AH", str(byte3 * 256 + byte2),"0.01AH",self.ResDataRec[index],0)
                        STIID("0x18FE14" + addr, ID, self.TW[display_index][0], 37, "CHRG_TIMES", str(byte5 * 256 + byte4),"累计充电次数",self.ResDataRec[index],0)
                        STIID("0x18FE14" + addr, ID, self.TW[display_index][0], 38, "DSCH_TIMES", str(byte7 * 256 + byte6),"累计放电次数",self.ResDataRec[index],0)
                        #STIID("0x18FE19" + addr, ID, self.TW[display_index][0], 39, "满充满放状态", str(byte1 * 256 + byte0),"",self.ResDataRec[index],0)
                        # STIID("0x18FE20" + addr, ID, self.TW[display_index][0], 40, "SOC正向追赶速率", str(byte1 * 256 + byte0), "")
                        # STIID("0x18FE20" + addr, ID, self.TW[display_index][0], 41, "SOC反向追赶速率", str(byte3 * 256 + byte2), "")
                        STIID("0x18FE22" + addr, ID, self.TW[display_index][0], 42, "告警代码", str(byte3 * 256*256*256+byte2 * 256*256+byte1 * 256 + byte0), "",self.ResDataRec[index],0)


                        if (("0x1881F2" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                            bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256

                            if bauvarid == 0x354:
                                STI(self.TW[display_index][0], 15, str("MAX_SOC_UP"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x34C:
                                STI(self.TW[display_index][0], 16, str("MAX_SOC_Temp_UP"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x356:
                                STI(self.TW[display_index][0], 17, str("MIN_SOC_UP"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x34A:
                                STI(self.TW[display_index][0], 18, str("MIN_SOC_Temp_UP"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x346:
                                STI(self.TW[display_index][0], 19, str("REVSE_SOC_UP"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x348:
                                STI(self.TW[display_index][0], 20, str("REVISE_SOC_Temp_UP"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x358:
                                STI(self.TW[display_index][0], 21, str("PURE_SOC_UP"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x33C:
                                STI(self.TW[display_index][0], 22, str("OCVMAXSOC_UP"),str((byte4 + byte5 * 256)), "OCV矫正最大SOC[0.1%]")

                            if bauvarid == 0x33A:
                                STI(self.TW[display_index][0], 23, str("OCVMINSOC_UP"),str((byte4 + byte5 * 256)), "OCV矫正最大SOC[0.1%]")

                            if bauvarid == 0x33E:
                                STI(self.TW[display_index][0], 24, str("OCV更新次数"),str((byte4 + byte5 * 256)), "OCVUP_DATA_COUNT_UP")

                            if bauvarid == 0x340:
                                STI(self.TW[display_index][0], 25, str("OCV无法原因标志"),str((byte4 + byte5 * 256)), "OCV无法原因标志(NA)：0-正常；bit0-最大电芯电压或最小电芯电压处于平台区；bit1-休眠时间不满足；bit2-初始上电电流过大；bit3-电压超超范围无效；bit4-电压处于平台期；bit5-温度无效；bit6-静置时间不满足；bit-7；部分电芯电压处于平台区。")







                            if bauvarid == 0x1D2:
                                STI(self.TW[display_index][0], 43, str("剩余充电时间"),str((byte4 + byte5 * 256)), "S")

                            if bauvarid == 0x1D3:
                                STI(self.TW[display_index][0], 44, str("剩余放电时间"),str((byte4 + byte5 * 256)), "S")

                            if bauvarid == 0x326:
                                STI(self.TW[display_index][0], 45, str("最高温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")
                                self.ResDataRec[index]["最高温度上半簇"] = Unsignal_Change(byte4 + byte5 * 256)
                            if bauvarid == 0x32A:
                                STI(self.TW[display_index][0], 46, str("最低温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")
                                self.ResDataRec[index]["最低温度上半簇"] = Unsignal_Change(byte4 + byte5 * 256)
                            if bauvarid == 0x31C:
                                STI(self.TW[display_index][0], 47, str("平均温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")
                            if bauvarid == 0x1D:
                                STI(self.TW[display_index][0], 48, str("SOE"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.1%")

                            if bauvarid == 0x20:
                                STI(self.TW[display_index][0], 49, str("SOE_Disp"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.1%")

                            if bauvarid == 0x254:
                                STI(self.TW[display_index][0], 50, str("剩余可放电"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x255:
                                STI(self.TW[display_index][0], 51, str("剩余可充电"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x1CD:
                                STI(self.TW[display_index][0], 52, str("单次充电电量"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x1CE:
                                STI(self.TW[display_index][0], 53, str("单次放电电量"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x352:
                                STI(self.TW[display_index][0], 54, str("OCV置位结果"), str(Unsignal_Change(byte4 + byte5 * 256)),"")

                            if bauvarid == 0x342:
                                STI(self.TW[display_index][0], 55, str("满充满放状态"), str(Unsignal_Change(byte4 + byte5 * 256)),"0-默认，1-满充，2满放")

                            if bauvarid == 0x334:
                                STI(self.TW[display_index][0], 56, str("满充状态"), str(Unsignal_Change(byte4 + byte5 * 256)),"0-默认，1-满充")





                       # STIID("", ID, self.tableWidget, 6, "放电继电器", str((byte7 * 256 + byte6)), "0断开-1闭合")
                        # # 下半簇

                        STIID("0x1301ef"+addr,ID,self.TW[display_index][1],0,"分流器电流", str(Unsignal_Change(byte3* 256+byte2)/10), "A",self.ResDataRec[index],1)
                        STIID("0x1301ef"+addr,ID,self.TW[display_index][1],1, "B端电压", str((byte1* 256 + byte0 )/10), "V",self.ResDataRec[index],1)
                        STIID("0x1301ef"+addr, ID, self.TW[display_index][1], 2, "P端电压", str((byte7 * 256 + byte6) / 10), "V",self.ResDataRec[index],1)
                        STIID("0x1201ef"+addr, ID, self.TW[display_index][1], 3, "运行状态", str((byte5)),"0、初始 1、自测 2、准备 3、预充 4、高压待机 5、放电 6、充电 7、放空 8、充满 9、错误 10、切断 ",self.ResDataRec[index],1)
                        STIID("0x1302EF"+addr, ID, self.TW[display_index][1], 4, "SOC", str((byte7 * 256 + byte6)), "0.1%",self.ResDataRec[index],1)
                        STIID("0x1206EF"+addr, ID, self.TW[display_index][1], 5, "最大单体电压", str((byte3* 256+byte2)),"mv",self.ResDataRec[index],1)
                        STIID("0x1206EF"+addr, ID, self.TW[display_index][1], 6, "最小单体电压", str((byte5 * 256 + byte4)), "mv",self.ResDataRec[index],1)
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][1], 7, "充电继电器", str(byte2>>1&0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],1)
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][1],8, "放电继电器", str(byte2>>5 & 0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],1)
                        STIID("0x1228EF"+addr, ID, self.TW[display_index][1], 9, "最严重告警等级", str((byte3 * 256 + byte2)&0xFF), "",self.ResDataRec[index],1)
                        if (byte0)==index:
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][1], 10, "BAU控制命令", str(byte5), "",self.ResDataRec[index],1)
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][1], 11, "BCU地址", str(byte0), "",self.ResDataRec[index],1)
                            STIID("0x12F200"+config["BAUaddr"], ID, self.TW[display_index][1], 12, "是否强充", str(byte1), "",self.ResDataRec[index],1)
                        STIID("0x1307EF"+addr, ID, self.TW[display_index][1], 13, "最大允许充电电流", str((byte1* 256 + byte0 )/10), "A",self.ResDataRec[index],1)
                        STIID("0x1307EF"+addr, ID, self.TW[display_index][1], 14, "最大允许放电电流", str((byte3* 256 + byte2 )/10), "A",self.ResDataRec[index],1)

                        # STIID("0x18FE12"+addr,ID,self.TW[display_index][1],15,"MAX_SOC_DOWN",str(byte1* 256 + byte0 ),"0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE12" + addr, ID, self.TW[display_index][1], 16, "MIN_SOC_DOWN", str(byte3 * 256 + byte2), "0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE12" + addr, ID, self.TW[display_index][1], 17, "PURE_SOC_DOWN", str(byte5 * 256 + byte4), "0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE12" + addr, ID, self.TW[display_index][1], 18, "REVISE_SOC_DOWN", str(byte7 * 256 + byte6), "0.1%",self.ResDataRec[index],1)
                        #
                        # STIID("0x18FE13"+addr,ID,self.TW[display_index][1],19,"REVISESOC_TEMP_DOWN",str(byte1* 256 + byte0 ),"0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE13" + addr, ID, self.TW[display_index][1], 20, "MIN_SOC_TEMP_DOWN", str(byte3 * 256 + byte2), "0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE13" + addr, ID, self.TW[display_index][1], 21, "MAX_SOC_TEMP_DOWN", str(byte5 * 256 + byte4), "0.1%",self.ResDataRec[index],1)
                        # STIID("0x18FE13" + addr, ID, self.TW[display_index][1], 22, "FUZZY_SOC_DOWN", str(byte7 * 256 + byte6), "0.1%",self.ResDataRec[index],1)
                        # if ((byte0>>7)&0x01==1) and ((byte3*256+byte2)!=0x1212) and (byte0 !=0xFD) and (byte0 !=0xFE) and (byte0 !=0xFF):
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][1], 23, "告警ID", str(byte0&0x7F), "",self.ResDataRec[index],1)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][1], 24, "告警等级", str(byte1), "",self.ResDataRec[index],1)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][1], 25, "告警阈值", str(byte5 * 256 + byte4), "",self.ResDataRec[index],1)
                        #     STIID("0x1215EF" + addr, ID, self.TW[display_index][1], 26, "告警值", str(byte7 * 256 + byte6), "",self.ResDataRec[index],1)







                        # STIID("0x18FE18" + addr, ID, self.TW[display_index][1], 30, "OCVMAXSOC_DOWN", str(byte1 * 256 + byte0), "OCV矫正最大SOC",self.ResDataRec[index],1)
                        # STIID("0x18FE18" + addr, ID, self.TW[display_index][1], 31, "OCVMINSOC_DOWN", str(byte3 * 256 + byte2), "OCV矫正最小SOC",self.ResDataRec[index],1)
                        # STIID("0x18FE18" + addr, ID, self.TW[display_index][1], 32, "OCV_UPDT_COUNT_DOWN", str(byte4), "OCV更新次数",self.ResDataRec[index],1)
                        # STIID("0x18FE18" + addr, ID, self.TW[display_index][1], 33, "OCV_FAIL_CODE_DOWN", str(byte5), "OCV无法原因标志(NA)：0-正常；bit0-最大电芯电压或最小电芯电压处于平台区；bit1-休眠时间不满足；bit2-初始上电电流过大；bit3-电压超超范围无效；bit4-电压处于平台期；bit5-温度无效；bit6-静置时间不满足；bit-7；部分电芯电压处于平台区。",self.ResDataRec[index],1)
                       # STIID("0x18FE18" + addr, ID, self.TW[display_index][1], 34, "FULL_CHRG_FLG_DOWN", str(byte6),"满充满放标志，0-默认；1-满充；2-满放",self.ResDataRec[index],1)

                        STIID("0x18FE15" + addr, ID, self.TW[display_index][1], 35, "TOTAL_CHRG_AH", str(byte1 * 256 + byte0), "0.01AH",self.ResDataRec[index],1)
                        STIID("0x18FE15" + addr, ID, self.TW[display_index][1], 36, "TOTAL_DSCH_AH", str(byte3 * 256 + byte2),"0.01AH",self.ResDataRec[index],1)
                        STIID("0x18FE15" + addr, ID, self.TW[display_index][1], 37, "CHRG_TIMES", str(byte5 * 256 + byte4),"累计充电次数",self.ResDataRec[index],1)
                        STIID("0x18FE15" + addr, ID, self.TW[display_index][1], 38, "DSCH_TIMES", str(byte7 * 256 + byte6),"累计放电次数",self.ResDataRec[index],1)
                        #STIID("0x18FE19" + addr, ID, self.TW[display_index][1], 39, "满充满放状态", str(byte3 * 256 + byte2), "",self.ResDataRec[index],1)
                        # STIID("0x18FE20" + addr, ID, self.TW[display_index][1], 40, "SOC正向追赶速率", str(byte5 * 256 + byte4), "")
                        # STIID("0x18FE20" + addr, ID, self.TW[display_index][1], 41, "SOC反向追赶速率", str(byte7 * 256 + byte6), "")
                        STIID("0x18FE22" + addr, ID, self.TW[display_index][1], 42, "告警代码", str(byte7 * 256*256*256+byte6 * 256*256+byte5 * 256 + byte4), "",self.ResDataRec[index],1)
                        if (("0x1881F2" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                            bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256

                            if bauvarid == 0x355:
                                STI(self.TW[display_index][1], 15, str("MAX_SOC_DOWN"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x34D:
                                STI(self.TW[display_index][1], 16, str("MAX_SOC_Temp_DOWN"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x357:
                                STI(self.TW[display_index][1], 17, str("MIN_SOC_DOWN"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x34B:
                                STI(self.TW[display_index][1], 18, str("MIN_SOC_Temp_DOWN"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x347:
                                STI(self.TW[display_index][1], 19, str("REVSE_SOC_DOWN"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x349:
                                STI(self.TW[display_index][1], 20, str("REVISE_SOC_Temp_DOWN"),str((byte4 + byte5 * 256)), "0.1%")
                            if bauvarid == 0x359:
                                STI(self.TW[display_index][1], 21, str("PURE_SOC_DOWN"),str((byte4 + byte5 * 256)), "0.1%")

                            if bauvarid == 0x33D:
                                STI(self.TW[display_index][1], 22, str("OCVMAXSOC_UP"), str((byte4 + byte5 * 256)),
                                    "OCV矫正最大SOC[0.1%]")

                            if bauvarid == 0x33B:
                                STI(self.TW[display_index][1], 23, str("OCVMINSOC_UP"), str((byte4 + byte5 * 256)),
                                    "OCV矫正最大SOC[0.1%]")

                            if bauvarid == 0x33F:
                                STI(self.TW[display_index][1], 24, str("OCV更新次数"), str((byte4 + byte5 * 256)),
                                    "OCVUP_DATA_COUNT_UP")

                            if bauvarid == 0x341:
                                STI(self.TW[display_index][1], 25, str("OCV无法原因标志"), str((byte4 + byte5 * 256)),
                                    "OCV无法原因标志(NA)：0-正常；bit0-最大电芯电压或最小电芯电压处于平台区；bit1-休眠时间不满足；bit2-初始上电电流过大；bit3-电压超超范围无效；bit4-电压处于平台期；bit5-温度无效；bit6-静置时间不满足；bit-7；部分电芯电压处于平台区。")

                            if bauvarid == 0x1D4:
                                STI(self.TW[display_index][1], 43, str("剩余充电时间"),str((byte4 + byte5 * 256)), "S")

                            if bauvarid == 0x1D5:
                                STI(self.TW[display_index][1], 44, str("剩余放电时间"),str((byte4 + byte5 * 256)), "S")

                            if bauvarid == 0x327:
                                STI(self.TW[display_index][1], 45, str("最高温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")
                                self.ResDataRec[index]["最高温度下半簇"] = Unsignal_Change(byte4 + byte5 * 256)
                            if bauvarid == 0x32B:
                                STI(self.TW[display_index][1], 46, str("最低温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")
                                self.ResDataRec[index]["最低温度下半簇"] = Unsignal_Change(byte4 + byte5 * 256)
                            if bauvarid == 0x31D:
                                STI(self.TW[display_index][1], 47, str("平均温度"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1℃")

                            if bauvarid == 0x1E:
                                STI(self.TW[display_index][1], 48, str("SOE"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.1%")

                            if bauvarid == 0x21:
                                STI(self.TW[display_index][1], 49, str("SOE_Disp"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.1%")

                            if bauvarid == 0x256:
                                STI(self.TW[display_index][1], 50, str("剩余可放电"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x257:
                                STI(self.TW[display_index][1], 51, str("剩余可充电"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x1CF:
                                STI(self.TW[display_index][1], 52, str("单次充电电量"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x1D0:
                                STI(self.TW[display_index][1], 53, str("单次放电电量"), str(Unsignal_Change(byte4 + byte5 * 256)),"0.01KWH")

                            if bauvarid == 0x353:
                                STI(self.TW[display_index][1], 54, str("OCV置位结果"), str(Unsignal_Change(byte4 + byte5 * 256)),"")

                            if bauvarid == 0x343:
                                STI(self.TW[display_index][1], 55, str("满充满放状态"),str(Unsignal_Change(byte4 + byte5 * 256)), "0-默认，1-满充，2满放")

                            if bauvarid == 0x335:
                                STI(self.TW[display_index][1], 56, str("满充状态"), str(Unsignal_Change(byte4 + byte5 * 256)),"0-默认，1-满充")

                    #不带中线
                    else:
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][0], 7, "充电继电器", str(byte2&0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],0)
                        STIID("0x120CEF"+addr, ID, self.TW[display_index][0], 8, "放电继电器", str(byte2>>4 & 0x01), "0断开-1闭合,继电器回读状态",self.ResDataRec[index],0)
                        if (("0x1881F2" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                            bcuvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256

                            if bcuvarid == 0xE:
                                STI(self.TW[display_index][0], 0, str("系统电流"),str((Unsignal_Change(byte4 + byte5 * 256))/10), "A")

                            if bcuvarid == 0x5B:
                                STI(self.TW[display_index][0], 1, str("B端电压"), str((byte4 + byte5 * 256) / 10), "V")

                            if bcuvarid == 0x5C:
                                STI(self.TW[display_index][0], 2, str("P端电压"), str((byte4 + byte5 * 256) / 10), "V")

                            if bcuvarid == 0xC:
                                STI(self.TW[display_index][0], 3, str("运行状态"), str((byte4 + byte5 * 256)), "0、初始 1、自测 2、准备 3、预充 4、高压待机 5、放电 6、充电 7、放空 8、充满 9、错误 10、切断 ")

                            if bcuvarid == 0x10:
                                STI(self.TW[display_index][0], 4, str("SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x148:
                                STI(self.TW[display_index][0], 5, str("最大单体电压"), str((byte4 + byte5 * 256)), "mv")

                            if bcuvarid == 0x14B:
                                STI(self.TW[display_index][0], 6, str("最小单体电压"), str((byte4 + byte5 * 256)), "mv")

                            # if bcuvarid == 0x00:
                            #     STI(self.TW[display_index][0], 7, str("充电继电器"), str("暂无"), "0断开-1闭合,继电器回读状态")
                            #
                            # if bcuvarid == 0x00:
                            #     STI(self.TW[display_index][0], 8, str("放电继电器"), str("暂无"), "0断开-1闭合,继电器回读状态")

                            if bcuvarid == 0x114:
                                STI(self.TW[display_index][0], 9, str("最严重告警等级"), str((byte4 + byte5 * 256)), "")

                            if bcuvarid == 0x1AF:
                                STI(self.TW[display_index][0], 10, str("最大允许充电电流"), str((byte4 + byte5 * 256)/10), "A")

                            if bcuvarid == 0x1AD:
                                STI(self.TW[display_index][0], 11, str("最大允许放电电流"), str((byte4 + byte5 * 256)/10), "A")

                            if bcuvarid == 0x1C0:
                                STI(self.TW[display_index][0], 15, str("MAX_SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C1:
                                STI(self.TW[display_index][0], 16, str("MIN_SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C2:
                                STI(self.TW[display_index][0], 17, str("PURE_SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C3:
                                STI(self.TW[display_index][0], 18, str("REVISE_SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C4:
                                STI(self.TW[display_index][0], 19, str("REVISESOC_TEMP"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C5:
                                STI(self.TW[display_index][0], 20, str("CELL_MIN_SOC_TEMP"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C6:
                                STI(self.TW[display_index][0], 21, str("CELL_MAX_SOC_TEMP"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1C7:
                                STI(self.TW[display_index][0], 22, str("PACK_FUZZY_SOC"), str((byte4 + byte5 * 256)), "0.1%")

                            if bcuvarid == 0x1BE:
                                STI(self.TW[display_index][0], 30, str("OCVMAXSOC"), str((byte4 + byte5 * 256)), "OCV矫正最大SOC")

                            if bcuvarid == 0x1BF:
                                STI(self.TW[display_index][0], 31, str("OCVMINSOC"), str((byte4 + byte5 * 256)), "OCV矫正最小SOC")

                            if bcuvarid == 0x1CA:
                                STI(self.TW[display_index][0], 32, str("OCV_UPDT_COUNT"), str((byte4 + byte5 * 256)), "OCV更新次数")

                            if bcuvarid == 0x1CB:
                                STI(self.TW[display_index][0], 33, str("OCV_FAIL_CODE"), str((byte4 + byte5 * 256)), "OCV无法原因标志(NA)：0-正常；bit0-最大电芯电压或最小电芯电压处于平台区；bit1-休眠时间不满足；bit2-初始上电电流过大；bit3-电压超超范围无效；bit4-电压处于平台期；bit5-温度无效；bit6-静置时间不满足；bit-7；部分电芯电压处于平台区。")

                            if bcuvarid == 0x1C9:
                                STI(self.TW[display_index][0], 34, str("满充标志位"), str((byte4 + byte5 * 256)),"上报满充标志位，0-未满充，1-满充")

                            if bcuvarid == 0x90801:
                                STI(self.TW[display_index][0], 35, str("TOTAL_CHRG_AH"), str((byte4 + byte5 * 256)),"0.01AH")

                            if bcuvarid == 0x90802:
                                STI(self.TW[display_index][0], 36, str("TOTAL_DSCH_AH"), str((byte4 + byte5 * 256)),"0.01AH")

                            if bcuvarid == 0x90803:
                                STI(self.TW[display_index][0], 37, str("CHRG_TIMES"), str((byte4 + byte5 * 256)),"累计充电次数")

                            if bcuvarid == 0x90804:
                                STI(self.TW[display_index][0], 38, str("DSCH_TIMES"), str((byte4 + byte5 * 256)),"累计放电次数")

                            if bcuvarid == 0x1FF:
                                STI(self.TW[display_index][0], 43, str("剩余充电时间"), str((byte4 + byte5 * 256)),"S")

                            if bcuvarid == 0x200:
                                STI(self.TW[display_index][0], 44, str("剩余放电时间"), str((byte4 + byte5 * 256)),"S")

                            if bcuvarid == 0x14E:
                                STI(self.TW[display_index][0], 45, str("最高温度"), str((byte4 + byte5 * 256)),"0.1℃")

                            if bcuvarid == 0x151:
                                STI(self.TW[display_index][0], 46, str("最低温度"), str((byte4 + byte5 * 256)),"0.1℃")

                            if bcuvarid == 0x144:
                                STI(self.TW[display_index][0], 47, str("平均温度"), str((byte4 + byte5 * 256)),"0.1℃")

                            if bcuvarid == 0x15:
                                STI(self.TW[display_index][0], 48, str("SOE"), str((byte4 + byte5 * 256)),"0.1%")

                            if bcuvarid == 0x1F:
                                STI(self.TW[display_index][0], 49, str("SOE_Disp"), str((byte4 + byte5 * 256)),"0.1%")

                            if bcuvarid == 0x252:
                                STI(self.TW[display_index][0], 50, str("剩余可放电"), str((byte4 + byte5 * 256)), "0.01KHW")

                            if bcuvarid == 0x253:
                                STI(self.TW[display_index][0], 51, str("剩余可充电"), str((byte4 + byte5 * 256)), "0.01KHW")

                            if bcuvarid == 0x1FD:
                                STI(self.TW[display_index][0], 52, str("单次充电电量"), str((byte4 + byte5 * 256)),"0.01KHW")

                            if bcuvarid == 0x1FE:
                                STI(self.TW[display_index][0], 53, str("单次放电电量"), str((byte4 + byte5 * 256)),"0.01KHW")

                            if bcuvarid == 0x1D7:
                                STI(self.TW[display_index][0], 54, str("OCV置位结果"), str((byte4 + byte5 * 256)),"")

                            if bcuvarid == 0x1C8:
                                STI(self.TW[display_index][0], 55, str("满充满放状态"), str((byte4 + byte5 * 256)),"0-默认，1-满充，2-满放")

                            if bcuvarid == 0x1C9:
                                STI(self.TW[display_index][0], 56, str("满充满放状态"), str((byte4 + byte5 * 256)),"0-默认，1-满充，2-满放")
                            # if bcuvarid == 0x1C8:
                            #     STI(self.TW[display_index][0], 39, str("FULL_CHRG_DSCHG_FLG"), str((byte4 + byte5 * 256)),"满充满放标志，0-默认；1-满充；2-满放")









                    # # 整簇
                    STIID("0x100000"+addr, ID, self.TW[display_index][2], 0, "系统运行时间", str(byte3*256*256*256+byte2*256*256+byte1 * 256 + byte0), "S",self.ResDataRec[index],2)
                    #STIID("0x1301ef"+addr,ID,self.TW[display_index][2],1,"B总压",str((byte5 * 256 + byte4)/10),"V",self.ResDataRec[index],2)
                    #STIID("0x1203ef"+addr, ID, self.TW[display_index][2], 2, "P总压", str((byte5 * 256 + byte4) / 10), "V",self.ResDataRec[index],2)
                    STIID("0x1203ef"+addr, ID, self.TW[display_index][2], 3, "SOH", str((byte1 * 256 + byte0)), "0.1%",self.ResDataRec[index],2)

                    STIID("0x120CEF"+addr, ID, self.TW[display_index][2], 8, "断路器", str(byte2>>3&0x01), "0断开-1闭合",self.ResDataRec[index],2)
                    # STIID("0x1204EF"+addr, ID, self.TW[display_index][2], 9, "可充电电量", str((byte1* 256 + byte0 )), "0.1AH",self.ResDataRec[index],2)
                    # STIID("0x1204EF"+addr, ID, self.TW[display_index][2], 10, "可放电电量", str((byte3 * 256 + byte2)), "0.1AH",self.ResDataRec[index],2)
                    # STIID("0x1204EF"+addr, ID, self.TW[display_index][2], 11, "单次累计充电电量", str((byte5* 256 + byte4 )), "0.01KWH",self.ResDataRec[index],2)
                    # STIID("0x1204EF"+addr, ID, self.TW[display_index][2], 12, "单次累计放电电量", str((byte7 * 256 + byte6)), "0.01KWH",self.ResDataRec[index],2)

                    STIID("0x1205EF" + addr, ID, self.TW[display_index][2], 13, "累计充电电量", str(byte3*256*256*256+byte2*256*256+byte1 * 256 + byte0), "0.1KWH",self.ResDataRec[index],2)
                    STIID("0x1205EF" + addr, ID, self.TW[display_index][2], 14, "累计放电电量", str(byte7*256*256*256+byte6*256*256+byte5 * 256 + byte4), "0.1KWH",self.ResDataRec[index],2)



                    STIID("0x1202EF" + addr, ID, self.TW[display_index][2], 15, "正对地电阻", str((byte1 * 256 + byte0)),"KΩ",self.ResDataRec[index],2)
                    STIID("0x1202EF" + addr, ID, self.TW[display_index][2], 16, "负对地电阻", str((byte3 * 256 + byte2)), "KΩ",self.ResDataRec[index],2)
                    STIID("0x18FE16" + addr, ID, self.TW[display_index][2], 17, "总绝缘电阻", str((byte1 * 256 + byte0)), "KΩ",self.ResDataRec[index],2)


                    STIID("0x1209EF" + addr, ID, self.TW[display_index][2], 18, "最大单体电压", str((byte1 * 256 + byte0)), "mv",self.ResDataRec[index],2)
                    STIID("0x1209EF" + addr, ID, self.TW[display_index][2], 19, "最小单体电压", str((byte3 * 256 + byte2)), "mv",self.ResDataRec[index],2)
                    temp = byte5 * 256 + byte4
                    STIID("0x1209EF" + addr, ID, self.TW[display_index][2], 20, "最大单体电压位置", "{}-{}".format((temp>>8)&0xFF,(temp)&0xFF), "模组-单体",self.ResDataRec[index],2)
                    temp = byte7 * 256 + byte6
                    STIID("0x1209EF" + addr, ID, self.TW[display_index][2], 21, "最小单体电压位置", "{}-{}".format((temp>>8)&0xFF,(temp)&0xFF), "模组-单体",self.ResDataRec[index],2)

                    STIID("0x120AEF" + addr, ID, self.TW[display_index][2], 22, "最大单体温度", str(Unsignal_Change(byte1 * 256 + byte0)/10), "℃",self.ResDataRec[index],2)
                    STIID("0x120AEF" + addr, ID, self.TW[display_index][2], 23, "最小单体温度", str(Unsignal_Change(byte3 * 256 + byte2)/10), "℃",self.ResDataRec[index],2)

                    STIID("0x18FE19" + addr, ID, self.TW[display_index][2], 24, "高压箱最高温度", str(Unsignal_Change(byte5 * 256 + byte4)), "0.1℃",self.ResDataRec[index],2)
                    STIID("0x18FE19" + addr, ID, self.TW[display_index][2], 25, "工装模式",str((byte7 * 256 + byte6)), "0-正常，1-工装",self.ResDataRec[index],2)

                    #STIID("0x1206EF" + addr, ID, self.TW[display_index][2], 26, "簇总容量",str((byte7 * 256 + byte6)/10), "AH",self.ResDataRec[index],2)

                    if (("0x1881F2" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                        bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                        if bauvarid == 0x9084A:
                            self.PACK_LIFE_HIGH = byte4 + byte5 * 256
                        if bauvarid == 0x9084B:
                            self.PACK_LIFE_LOW = byte4 + byte5 * 256
                        # STI(self.TW[display_index][2], 27, str("PACK_LIFE_LOW"),str(self.PACK_LIFE_LOW), "0.1MIN")
                        # STI(self.TW[display_index][2], 28, str("PACK_LIFE_HIGH"), str(self.PACK_LIFE_HIGH), "0.1MIN")
                            STI(self.TW[display_index][2], 28, str("PACK_LIFE"), str(self.PACK_LIFE_LOW+(self.PACK_LIFE_HIGH<<16)), "MIN")

                        if bauvarid == 0x90878:
                            self.PACK_TEMP_LIFE_HIGH = byte4 + byte5 * 256

                        if bauvarid == 0x90879:
                            self.PACK_TEMP_LIFE_LOW = byte4 + byte5 * 256

                            STI(self.TW[display_index][2], 29, str("SOH温度修正后寿命"),str(self.PACK_TEMP_LIFE_LOW + (self.PACK_TEMP_LIFE_HIGH << 16)), "0.1MIN")

                        if bauvarid==0x90401:
                            STI(self.TW[display_index][2], 30, str("模组数"), str((byte4 + byte5 * 256)),"模组数")
                        if bauvarid==0x90402:
                            STI(self.TW[display_index][2], 31, str("每个模组AFE数量"), str((byte4 + byte5 * 256)),"每个模组AFE数量")
                        if bauvarid==0x9045F:
                            STI(self.TW[display_index][2], 32, str("每个模组单体数量"), str((byte4 + byte5 * 256)),"每个模组单体数量")
                        if bauvarid==0x90460:
                            STI(self.TW[display_index][2], 33, str("每个模组温度数量"), str((byte4 + byte5 * 256)),"每个模组温度数量")
                        if bauvarid==0x90461:
                            STI(self.TW[display_index][2], 34, str("极柱温度数"), str((byte4 + byte5 * 256)),"极柱温度数")
                        if bauvarid == 0x9040D:
                            STI(self.TW[display_index][2], 35, str("中线标志位"), str((byte4 + byte5 * 256)), "1-带中线，0-不带中线")

                        if bauvarid == 0x5B:
                            STI(self.TW[display_index][2], 1, str("B总压"), str((byte5 * 256 + byte4)/10), "V")

                        if bauvarid == 0x5C:
                            STI(self.TW[display_index][2], 2, str("P总压"), str((byte5 * 256 + byte4)/10), "V")

                        if bauvarid == 0x90446:
                            STI(self.TW[display_index][2], 37, str("均衡启动压差"), str((byte5 * 256 + byte4)), "mv")
                        if bauvarid == 0x90447:
                            STI(self.TW[display_index][2], 38, str("均衡启动停止压差"), str((byte5 * 256 + byte4)), "mv")
                        if bauvarid == 0x9044A:
                            STI(self.TW[display_index][2], 39, str("均衡启动电压"), str((byte5 * 256 + byte4)), "mv")
                        if bauvarid == 0x9044B:
                            STI(self.TW[display_index][2], 40, str("均衡保护电压上限"), str((byte5 * 256 + byte4)), "mv")
                        if bauvarid == 0x9044C:
                            STI(self.TW[display_index][2], 41, str("均衡保护电压下限"), str((byte5 * 256 + byte4)), "mv")
                        if bauvarid == 0x9044D:
                            STI(self.TW[display_index][2], 42, str("均衡开启温度上限"), str(Unsignal_Change(byte5 * 256 + byte4)/10), "℃")
                        if bauvarid == 0x9044E:
                            STI(self.TW[display_index][2], 43, str("均衡开启温度下限"), str(Unsignal_Change(byte5 * 256 + byte4)/10), "℃")
                        if bauvarid == 0x9045D:
                            STI(self.TW[display_index][2], 45, str("容量"), str(Unsignal_Change(byte5 * 256 + byte4)/10), "AH")
                        if bauvarid == 0x90479:
                            STI(self.TW[display_index][2], 46, str("最大预充时间"), str(Unsignal_Change(byte5 * 256 + byte4)/10), "S")
                        if bauvarid == 0x9047A:
                            STI(self.TW[display_index][2], 47, str("预充压差"), str(((byte5 * 256 + byte4)&0x7FFF)/10), "V")
                        if bauvarid == 0x9047C:
                            STI(self.TW[display_index][2], 48, str("最小预充时间"), str(((byte5 * 256 + byte4))/10), "S")

                        if bauvarid == 0x9049C:
                            STI(self.TW[display_index][2], 49, str("禁充恢复最大时间"), str(((byte5 * 256 + byte4))), "H")

                        if bauvarid == 0x9049D:
                            STI(self.TW[display_index][2], 50, str("禁充恢复最小时间"), str(((byte5 * 256 + byte4))), "H")

                        if bauvarid == 0x9047D:
                            STI(self.TW[display_index][2], 51, str("预充最大电流"), str(((byte5 * 256 + byte4))), "0.1A")

                        if bauvarid == 0x9049E:
                            STI(self.TW[display_index][2], 52, str("SOC\SOE定期下降时间"), str(((byte5 * 256 + byte4))), "H")

                        if bauvarid == 0x9049F:
                            STI(self.TW[display_index][2], 53, str("SOC\SOE定期下降量"), str(((byte5 * 256 + byte4))), "0.1%")



            try:
                if ("0x1881F2EF".casefold()  == ID.casefold()):
                    bauvarid = byte0+byte1*256+byte2*256*256+byte3*256*256
                    # 第一块###########################################################################################################
                    if bauvarid==90:
                        STI(self.TW[config["BCU_NUM"]+1][0],0,str("温度1(5A)"),str(Unsignal_Change(byte4+byte5*256)),"0.1℃")
                    if bauvarid==91:
                        STI(self.TW[config["BCU_NUM"]+1][0],1,str("温度2(5B)"),str(Unsignal_Change(byte4+byte5*256)),"0.1℃")

                    if bauvarid==0x30C1:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 2, str("PAR_SYS_BCU_NUM"),str(Unsignal_Change(byte4 + byte5 * 256)), "PAR_SYS_BCU_NUM")

                    if bauvarid==0x30D0:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 3, str("PAR_SYS_BRANCH_NUM"),str(Unsignal_Change(byte4 + byte5 * 256)), "PAR_SYS_BRANCH_NUM")

                    if bauvarid==0x30D6:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 4, str("PAR_SYS_MIN_RUNNING_BCU_NUM"),str(Unsignal_Change(byte4 + byte5 * 256)), "最小在线簇数")

                    if bauvarid==0x3016:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 5, str("断路器控制"),str(Unsignal_Change(byte4 + byte5 * 256)), "断路器控制 0-断开 1-闭合")

                    for i in range(0,6):
                        if bauvarid==(0x3019+i):
                            STI(self.TW[config["BCU_NUM"] + 1][0], 6+i, str("簇{}使能".format(str(i+1))),str(Unsignal_Change(byte4 + byte5 * 256)), "0=未请求，1=断开，2=闭合 ")

                    if bauvarid == 0x185:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 22, str("手动并网"), str(Unsignal_Change(byte4 + byte5 * 256)), "手动并网 0=未请求，1=并网，2=离网")

                    if bauvarid == 0x3029:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 23, str("系统强充"), str(Unsignal_Change(byte4 + byte5 * 256)), "系统强充 0-关 1开启")

                    if bauvarid == 0x3105:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 24, str("最小并簇电压"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1V")

                    if bauvarid == 0x3104:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 25, str("压差不均衡阈值"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1V")

                    if bauvarid == 0x3106:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 26, str("电流不均衡阈值"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid == 0xBE:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 27, str("BAU告警"), str(Unsignal_Change(byte4 + byte5 * 256)), "低字节：告警级别；高字节：(0=默认正常，1=即将切断，2=故障切断，3=特殊故障立即切断)")

                    if bauvarid == 0x30D5:
                        STI(self.TW[config["BCU_NUM"] + 1][0], 28, str("中线配置"),
                            str(Unsignal_Change(byte4 + byte5 * 256)),
                            "1-有中线，0-无中线")

                    for i in range(0, 6):
                        if bauvarid==706 + i * 100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 29+i, str("簇{}上半簇预充错误".format(str(i+1))),str(Unsignal_Change(byte4 + byte5 * 256)), "0=默认，1=错误")
                    for i in range(0, 6):
                        if bauvarid==707 + i * 100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 35+i, str("簇{}下半簇预充错误".format(str(i+1))),str(Unsignal_Change(byte4 + byte5 * 256)), "0=默认，1=错误")
                    for i in range(0, 6):
                        if bauvarid==708 + i * 100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 41+i, str("簇{}上半簇并网失败".format(str(i+1))),str(Unsignal_Change(byte4 + byte5 * 256)), "0=默认，1=错误")
                    for i in range(0, 6):
                        if bauvarid==709 + i * 100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 47+i, str("簇{}下半簇并网失败".format(str(i+1))),str(Unsignal_Change(byte4 + byte5 * 256)), "0=默认，1=错误")


                    for i in range(0, 6):
                        if bauvarid==698 + i*100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 54+i, str("簇{} P端电压上半簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")
                    for i in range(0, 6):
                        if bauvarid==699 + i*100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 61+i, str("簇{} P端电压下半簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")
                    for i in range(0, 6):
                        if bauvarid==641 + i*100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 68+i, str("簇{} P端电压整簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")

                    for i in range(0, 6):
                        if bauvarid==0x1246 + i*1359:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 75+i, str("簇{}霍尔电流".format(str(i+1))),str((byte4 + byte5 * 256)/10), "A")

                    for i in range(0, 6):
                        if bauvarid==0x2B8 + i*100:
                            STI(self.TW[config["BCU_NUM"] + 1][0], 82+i, str("簇{}上半簇运行状态".format(str(i+1))),str((byte4 + byte5 * 256)), "")
                    #第二块###########################################################################################################
                    if bauvarid==0xDC:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 0, str("堆最大允许放电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid==0xDE:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 1, str("堆最大允许充电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid==0xED:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 2, str("堆上半簇最大允许放电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid == 0xEF:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 3, str("堆下半簇最大允许放电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid==0xD2:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 4, str("堆上半簇最大允许充电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    if bauvarid == 0xD4:
                        STI(self.TW[config["BCU_NUM"] + 1][1], 5, str("堆下半簇最大允许充电电流"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1A")

                    for i in range(0, 6):
                        if bauvarid==0x1244 + i*1359:
                            STI(self.TW[config["BCU_NUM"] + 1][1], 54+i, str("簇{} B端电压上半簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")
                    for i in range(0, 6):
                        if bauvarid==0x1245 + i*1359:
                            STI(self.TW[config["BCU_NUM"] + 1][1], 61+i, str("簇{} B端电压下半簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")
                    for i in range(0, 6):
                        if bauvarid==0x1001 + i*1359:
                            STI(self.TW[config["BCU_NUM"] + 1][1], 68+i, str("簇{} B端电压整簇".format(str(i+1))),str((byte4 + byte5 * 256)), "0.1V")

                    for i in range(0, 6):
                        if bauvarid==0x1247 + i*1359:
                            STI(self.TW[config["BCU_NUM"] + 1][1], 75+i, str("簇{}分流器".format(str(i+1))),str((byte4 + byte5 * 256)/10), "A")

                    for i in range(0, 6):
                        if bauvarid==0x2B9 + i*100:
                            STI(self.TW[config["BCU_NUM"] + 1][1], 82+i, str("簇{}下半簇运行状态".format(str(i+1))),str((byte4 + byte5 * 256)), "")
                    # 第三块###########################################################################################################
                    if bauvarid==0xF:
                        STI(self.TW[config["BCU_NUM"] + 1][2], 0, str("系统运行状态"), str(Unsignal_Change(byte4 + byte5 * 256)), "[0、初始 1、自测 2、准备 4、高压待机  10、切断 ]")

                    if bauvarid==0x3101:
                        STI(self.TW[config["BCU_NUM"] + 1][2], 1, str("预充时间"), str(Unsignal_Change(byte4 + byte5 * 256)), "0.1s")

            except:
                pass

            # 电压 #温度

            if (("0x1235EF" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                if((byte1 * 256 + byte0)>>12==0):
                    for i in range(0, int(config["LECU_NUM"])*int(config["CELL_NUM"])):
                        if byte0 < int(config["LECU_NUM"])*int(config["CELL_NUM"]):
                            Vres[(byte1 * 256 + byte0 + 0)&0x3FF] = byte3 * 256 + byte2
                        if byte0 < int(config["LECU_NUM"])*int(config["CELL_NUM"])-1:
                            Vres[(byte1 * 256 + byte0 + 1)&0x3FF] = byte5 * 256 + byte4
                        if byte0 < int(config["LECU_NUM"])*int(config["CELL_NUM"])-2:
                            Vres[(byte1 * 256 + byte0 + 2)&0x3FF] = byte7 * 256 + byte6

                    now = time.time()
                    if now - self.last_dy_time > 1.0:  # 每1秒最多处理一次
                        self.last_dy_time = now
                        self.S18.setVoltageValues(Vres)
                        self.voltage_snapshot_dirty = True


            if (("0x1235EF" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                if ((byte1 * 256 + byte0) >> 12 == 1):
                    for i in range(0, int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"])):
                        if byte0 < int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"]):
                            VresTem[(byte1 * 256 + byte0 + 0)&0x3FF] = Unsignal_Change(byte3 * 256 + byte2)
                        if byte0 < int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"]) - 1:
                            VresTem[(byte1 * 256 + byte0 + 1)&0x3FF] = Unsignal_Change(byte5 * 256 + byte4)
                        if byte0 < int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"]) - 2:
                            VresTem[(byte1 * 256 + byte0 + 2)&0x3FF] = Unsignal_Change(byte7 * 256 + byte6)

                    now = time.time()
                    if now - self.last_tem_time > 1.0:  # 每1秒最多处理一次
                        self.last_tem_time = now
                        self.S20.setVoltageValues(VresTem)
                        self.temperature_snapshot_dirty = True




            if (("0x1881F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
               # for LECU_index in range(config["LECU_NUM"]):
                if bauvarid>4096:
                    if ((bauvarid-4096)%BAL_JG_LEN == 30) or ((bauvarid-4096)%BAL_JG_LEN == 31):
                        #for LECU_index in range(config["LECU_NUM"]):
                        if ((bauvarid-4096)%BAL_JG_LEN == 30) and ((bauvarid-4096)//BAL_JG_LEN)<config["LECU_NUM"]:
                            self.LECU_LOW[(bauvarid-4096)//BAL_JG_LEN] = byte4 + byte5 * 256

                        if ((bauvarid-4096)%BAL_JG_LEN == 31) and ((bauvarid-4096)//BAL_JG_LEN)<config["LECU_NUM"]:
                            self.LECU_HIGH[(bauvarid - 4096) // BAL_JG_LEN] = byte4 + byte5 * 256


                        #遍历模组
                        cell_index = 0;
                        for i in range(0,config["LECU_NUM"]):
                            for j in range(0,config["CELL_NUM"]):
                                if j<16:
                                    VresBAL[cell_index] = (self.LECU_LOW[i]>>j)& 0x01
                                    cell_index=cell_index+1
                                if (j>=16) and (j<32):
                                    VresBAL[cell_index] = (self.LECU_HIGH[i] >>( j-16)) & 0x01
                                    cell_index = cell_index + 1
                        now = time.time()
                        if now - self.last_bal_time > 1.0:  # 每1秒最多处理一次
                            self.last_bal_time = now
                            self.S19.setVoltageValues(VresBAL)
                            if hasattr(self, "S25"):
                                self.S25.set_values(VresBAL)
                            self.balance_snapshot_dirty = True


            # 电芯异常
            if (("0x1881F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                # 遍历模组
                for i in range(0, config["LECU_NUM"]):
                    for j in range(0, config["CELL_NUM"]):
                        if bauvarid==ABNORM_ADDR + i * 320 + j:
                            VresDXYC[i*config["CELL_NUM"]+j] = byte4 + byte5 * 256

                now = time.time()
                if now - self.last_dx_time > 1.0:  # 每1秒最多处理一次
                    self.last_dx_time = now
                    self.S24.setVoltageValues(VresDXYC)
                    self.abnormal_snapshot_dirty = True



            # DIBCU状态

            if (("0x1881F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                # self.S22.tableWidget.setItem(0, 0, QTableWidgetItem("J1 DI1_H"))
                # self.S22.tableWidget.setItem(0, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                varid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                varid = varid
                # self.S21.setItem(varid//32,varid%32+1,str(byte4+byte5*256))
                if varid == 0x24:
                    self.S22.tableWidget.setItem(0, 0, QTableWidgetItem("J1 DI1_H"))
                    self.S22.tableWidget.setItem(0, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x25:
                    self.S22.tableWidget.setItem(1, 0, QTableWidgetItem("J1 DI2_H"))
                    self.S22.tableWidget.setItem(1, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x26:
                    self.S22.tableWidget.setItem(2, 0, QTableWidgetItem("J1 DI3_H"))
                    self.S22.tableWidget.setItem(2, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x27:
                    self.S22.tableWidget.setItem(3, 0, QTableWidgetItem("J1 DI4_H"))
                    self.S22.tableWidget.setItem(3, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x28:
                    self.S22.tableWidget.setItem(4, 0, QTableWidgetItem("J1 DI5_H"))
                    self.S22.tableWidget.setItem(4, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x29:
                    self.S22.tableWidget.setItem(5, 0, QTableWidgetItem("J1 DI6_H"))
                    self.S22.tableWidget.setItem(5, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x2D:
                    self.S22.tableWidget.setItem(6, 0, QTableWidgetItem("J1 DI4_L"))
                    self.S22.tableWidget.setItem(6, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x70:
                    self.S22.tableWidget.setItem(7, 0, QTableWidgetItem("J1 RT1 温度检测"))
                    self.S22.tableWidget.setItem(7, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x71:
                    self.S22.tableWidget.setItem(8, 0, QTableWidgetItem("J1 RT2 温度检测"))
                    self.S22.tableWidget.setItem(8, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x72:
                    self.S22.tableWidget.setItem(9, 0, QTableWidgetItem("J1 RT3 温度检测"))
                    self.S22.tableWidget.setItem(9, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x73:
                    self.S22.tableWidget.setItem(10, 0,QTableWidgetItem("J1 RT4 温度检测"))
                    self.S22.tableWidget.setItem(10, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x74:
                    self.S22.tableWidget.setItem(11, 0, QTableWidgetItem("J1 RT5 温度检测"))
                    self.S22.tableWidget.setItem(11, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x75:
                    self.S22.tableWidget.setItem(12, 0, QTableWidgetItem("J1 RT6 温度检测"))
                    self.S22.tableWidget.setItem(12, 1, QTableWidgetItem(str(Unsignal_Change(byte4 + byte5 * 256))))
                if varid == 0x2A:
                    self.S22.tableWidget.setItem(13, 0, QTableWidgetItem("J5 DI1_L"))
                    self.S22.tableWidget.setItem(13, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x2B:
                    self.S22.tableWidget.setItem(14, 0, QTableWidgetItem("J5 DI2_L"))
                    self.S22.tableWidget.setItem(14, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x2F:
                    self.S22.tableWidget.setItem(15, 0, QTableWidgetItem("ADDR_DI"))
                    self.S22.tableWidget.setItem(15, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
                if varid == 0x2C:
                    self.S22.tableWidget.setItem(16, 0, QTableWidgetItem("DI3_L"))
                    self.S22.tableWidget.setItem(16, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))
            # print(Alarm_list)

            # DIBCU状态
            if (("0x1881F2EF".casefold()).casefold() == ID.casefold()):
                varid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                varid = varid
                if varid==0x2D:
                    self.S22.tableWidget_2.setItem(0,0,QTableWidgetItem("J7_DI1_H"))
                    self.S22.tableWidget_2.setItem(0, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))

                if varid==0x2E:
                    self.S22.tableWidget_2.setItem(1,0,QTableWidgetItem("J7_DI2_H"))
                    self.S22.tableWidget_2.setItem(1, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))

                if varid==0x2F:
                    self.S22.tableWidget_2.setItem(2,0,QTableWidgetItem("J7_DI3_H"))
                    self.S22.tableWidget_2.setItem(2, 1, QTableWidgetItem(str(byte4 + byte5 * 256)))

                if varid==0x30:
                    self.S22.tableWidget_2.setItem(3,0,QTableWidgetItem("J7_DI1_L"))
                    self.S22.tableWidget_2.setItem(3,1, QTableWidgetItem(str(byte4 + byte5 * 256)))

                if varid==0x31:
                    self.S22.tableWidget_2.setItem(4,0,QTableWidgetItem("J7_DI2_L"))
                    self.S22.tableWidget_2.setItem(4,1, QTableWidgetItem(str(byte4 + byte5 * 256)))



            # 告警参数获取
            # for i in range(64):
            #     for j in range(32):
            try:
                if (("0x1881F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                    data_id = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256 * 256
                    varid = data_id - config["Glaoal_Index_alarm"]
                    alarm_row = varid // 32
                    field_index = varid % 32
                    if 0 <= alarm_row < len(Alarm_list) and 0 <= field_index < 32:
                        Alarm_list[alarm_row][field_index] = byte4 + byte5 * 256
                        if alarm_row < self.S21.alarm_count():
                            self.S21.update_alarm_row(alarm_row, Alarm_list[alarm_row])
                # print(Alarm_list)
            except:
                pass


            if (("0x1883F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                varid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256 * 256

                pending = getattr(self, "pending_alarm_writes", {})
                if varid in pending:
                    success = (byte4 + byte5 * 256) != 0
                    if not success:
                        self.pending_alarm_write_failed = getattr(self, "pending_alarm_write_failed", 0) + 1
                    pending.pop(varid, None)
                    if pending:
                        self.S21.set_status_text(f"告警参数写入中，剩余 {len(pending)} 项...")
                    else:
                        failed = getattr(self, "pending_alarm_write_failed", 0)
                        if failed:
                            self.S21.set_status_text(f"告警参数写入完成，失败 {failed} 项，请检查工装模式或参数范围。")
                            QMessageBox.warning(self, "告警参数写入", f"写入完成，但有 {failed} 项被下位机拒绝。")
                        else:
                            self.S21.set_status_text("告警参数写入成功。")
                            QMessageBox.information(self, "告警参数写入", "选中告警参数写入成功。")
                    self.pending_alarm_writes = pending
                elif(varid == self.AlarmIndex):
                    if(byte4==1):
                        QMessageBox.information(self, "修改结果显示", "修改成功！")

            if self.table_index == self._parameter_tab_index():
                if (("0x1881F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                    bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                    try:
                        if bauvarid==int(self.S23.lineEdit_13.text()):
                            self.S23.lineEdit_14.setText(str(byte4+byte5*256))
                    except:
                        self.S23.lineEdit_14.setText(str("NULL"))

                    try:
                        if bauvarid == int(self.S23.lineEdit_15.text()):
                            self.S23.lineEdit_16.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_16.setText(str("NULL"))

                    try:
                        if bauvarid == int(self.S23.lineEdit_17.text()):
                            self.S23.lineEdit_18.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_18.setText(str("NULL"))

                    try:
                        if bauvarid == int(self.S23.lineEdit_19.text()):
                            self.S23.lineEdit_20.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_20.setText(str("NULL"))

                if ("0x1881F2EF".casefold()== ID.casefold()):
                    bauvarid = byte0 + byte1 * 256 + byte2 * 256 * 256 + byte3 * 256 * 256
                    try:
                        if bauvarid==int(self.S23.lineEdit_5.text()):
                            self.S23.lineEdit_6.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_6.setText(str("NULL"))

                    try:
                        if bauvarid==int(self.S23.lineEdit_7.text()):
                            self.S23.lineEdit_8.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_8.setText(str("NULL"))

                    try:
                        if bauvarid==int(self.S23.lineEdit_9.text()):
                            self.S23.lineEdit_10.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_10.setText(str("NULL"))

                    try:
                        if bauvarid==int(self.S23.lineEdit_11.text()):
                            self.S23.lineEdit_12.setText(str(byte4 + byte5 * 256))
                    except:
                        self.S23.lineEdit_12.setText(str("NULL"))






            # 工装模式切换代码
            if (self.FLAG_WORK_MODE==0):
                if (("0x18A1F2" + config["ADDRESLIST"][self._active_cluster_index()].casefold()).casefold() == ID.casefold()):
                    data = byte3*256*256*256+byte4*256*256+byte5*256+byte6
                    res_data = CanDiag_Seed_2_Key(data)
                    #发送秘钥
                    tdata = [0x06,0x27,0x12,(res_data>>24)&0xFF,(res_data>>16)&0xFF,(res_data>>8)&0xFF,(res_data)&0xFF,0xAA]
                    #print(hex(tdata))

                    if self._active_cluster_index() == 0:
                        self.c.Transmit(0x18A000F2, tdata, extern_flag=True, data_len=8)
                    if self._active_cluster_index() != 0:
                        self.c.Transmit(0x18A0A0F2 + ((self._active_cluster_index() - 1) << 8), tdata, extern_flag=True, data_len=8)

                #    打开工装
                    index = self.S17.comboBox.currentIndex()
                    if index==0:
                        data = [1, 0, 0xFF, 0xFF, 1, 0, 0xFF, 0xFF]
                    if index==1:
                        data = [1, 0, 0xFF, 0xFF, 0, 0, 0xFF, 0xFF]
                    self.CtrlData(self._active_cluster_index(), data)
                    self.FLAG_WORK_MODE=1
                    # index = self.S17.comboBox.currentIndex()
                    # data = [1, 0, 0xFF, 0xFF, not index, 0, 0xFF, 0xFF]
                    # self.CtrlData(self._active_cluster_index(), data)

            #################################################################################################################
            for index, addr in enumerate(config["ADDRESLIST"]):
                if index>config["BCU_NUM"]:
                    continue

                if (("0x1215EF" + config["ADDRESLIST"][
                    index].casefold()).casefold() == ID.casefold()):
                    # 绿色：表示安全或低风险。
                    # 黄色：表示中等风险或警告。
                    # 橙色：表示较高的风险。
                    # 红色：表示危险或高风险。
                    if (byte1 == 0) or (byte1 > 5):
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 0
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("green"))
                    if byte1 == 3:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 3
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("yellow"))
                    if byte1 == 2:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 2
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("orange"))
                    if byte1 == 1:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 1
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("red"))

                if (("0x1215EF" + config["ADDRESLIST"][index].casefold()).casefold() == ID.casefold()):
                    # 绿色：表示安全或低风险。
                    # 黄色：表示中等风险或警告。
                    # 橙色：表示较高的风险。
                    # 红色：表示危险或高风险。

                    if (byte1 == 0) or (byte1 > 5):
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 0
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("green"))
                    if byte1 == 3:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 3
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("yellow"))
                    if byte1 == 2:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 2
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("orange"))
                    if byte1 == 1:
                        AlarmClassDict[config["ADDRESLIST"][index]][(byte0 & 0x7F) - 1] = 1
                        # self.S21.change_row_color((byte0&0x7F)-1,QColor("red"))


    def Send_Extend_Frames_SD(self):
        #workmode_cmd = self.comboBox.
        index = self.S17.comboBox_2.currentIndex()
        data = [index+1,0,0,0,2,2,0,0]
        for i in range(10):
            # c.Transmit(0x212,data,extern_flag=True,data_len=7)
            self.c.Transmit(0x12F200EF,data,extern_flag=True,data_len=8)
    def Send_Extend_Frames_XD(self):
        #workmode_cmd = self.comboBox.
        index = self.S17.comboBox_2.currentIndex()
        data = [index+1,0,0,0,24,24,0,0]
        for i in range(10):
            # c.Transmit(0x212,data,extern_flag=True,data_len=7)
            self.c.Transmit(0x12F200EF,data,extern_flag=True,data_len=8)


    def ForceChargeOpenClose(self):
        index1 = self._active_cluster_index()
        index2 = self.S17.comboBox_9.currentIndex()
        #持续开
        if(index2==0):
            data = [index1, 1, 0, 0, 2, 2, 0, 0]
            for i in range(10):
                # c.Transmit(0x212,data,extern_flag=True,data_len=7)
                self.c.Transmit(0x12F200EF, data, extern_flag=True, data_len=8)



    def ForceChargeOpen(self):
        index2 = self.S17.comboBox_9.currentIndex()
        if (index2 == 0):
            self.timer_Forcecharge.start(1)
        if (index2==1):
            self.timer_Forcecharge.stop()



    def S18currentIndexChanged(self):
        if self.table_index == self._voltage_tab_index():
            try:
                Vres = [0 for i in range(int(config["LECU_NUM"]) * int(config["CELL_NUM"]))]
                self.S18.setVoltageValues(Vres)
            except:
                pass
    def S18currentIndexChangedBAL(self):
        if self.table_index == self._balance_tab_index():
            try:
                VresBAL = [0 for i in range(int(config["LECU_NUM"]) * int(config["CELL_NUM"]))]
                self.S19.setVoltageValues(VresBAL)
            except:
                pass

    def S20currentIndexChangedTem(self):
        if self.table_index == self._temperature_tab_index():
            try:
                VresTem = [0 for i in range(int(config["LECU_NUM"]) * int(config["CELL_Tem_NUM"]))]
                self.S20.setVoltageValues(VresTem)
            except:
                pass


    def WordMode(self):
        self.FLAG_WORK_MODE=0
        index = bool(self.S17.comboBox.currentIndex())
        # index =0关闭工装  =1 打开工装
        Cindex = self._active_cluster_index()
        #簇索引


        #上位机发(0x18A0A0F2)
        data = [0x02,0x27,0x11,0xAA,0xAA,0xAA,0xAA,0xAA]
        if Cindex == 0:
            self.c.Transmit(0x18A000F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x18A0A0F2 + ((Cindex - 1) << 8), data, extern_flag=True, data_len=8)








    def on_alarm_cluster_changed(self, *_args):
        self._set_active_cluster(self._active_cluster_index(), refresh=False, source="alarm_page")
        self.S21.set_cluster_context()
        self.S21.clear_cached_values()
        self.on_alarm_parameter_read()


    def on_alarm_parameter_read(self):
        global g_index
        g_index = 0
        self.current_COUNT = 0
        self.alarm_request_limit = self.S21.alarm_count() * 32
        self.S21.set_cluster_context()
        self.S21.clear_cached_values()
        if not getattr(self, "can_ready", False):
            self.S21.set_status_text("CAN未连接，无法读取告警参数。")
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再读取告警参数。")
            return
        if self.send_time1 is not None and not self.send_time1.isActive():
            self.send_time1.start(10)
        self.S21.set_status_text(
            f"正在读取告警参数：共 {self.alarm_request_limit} 个字段。"
        )


    def on_alarm_parameter_write_current(self):
        if not getattr(self, "can_ready", False):
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再写入告警参数。")
            return
        alarm_id, raw_fields = self.S21.build_current_raw_fields()
        if alarm_id is None:
            QMessageBox.warning(self, "未选择告警", "请先在告警列表中选择一条告警。")
            return
        if hasattr(self.S21, "has_complete_current_record") and not self.S21.has_complete_current_record():
            QMessageBox.warning(self, "告警未读取", "请先读取并选中告警，确认右侧参数已刷新后再写入。")
            return
        if not raw_fields:
            QMessageBox.warning(self, "无可写入字段", "当前告警没有可写入参数。")
            return

        base_id = config["Glaoal_Index_alarm"] + alarm_id * 32
        pending = {}
        for field_index, raw_value in sorted(raw_fields.items()):
            data_id = base_id + int(field_index)
            raw_value = int(raw_value) & 0xFFFF
            data = [
                data_id & 0xFF,
                (data_id >> 8) & 0xFF,
                (data_id >> 16) & 0xFF,
                (data_id >> 24) & 0xFF,
                raw_value & 0xFF,
                (raw_value >> 8) & 0xFF,
                0,
                0,
            ]
            pending[data_id] = field_index
            self.SetData(self._active_cluster_index(), data)
            time.sleep(0.003)

        self.pending_alarm_writes = pending
        self.pending_alarm_write_failed = 0
        self.AlarmIndex = base_id
        self.S21.set_status_text(f"已发送 {len(pending)} 个告警参数写入请求，等待下位机确认。")


    def on_alarm_parameter_save_flash(self):
        if not getattr(self, "can_ready", False):
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再保存参数。")
            return
        data = [4, 0, 0, 0, 8, 0, 0, 0]
        self.CtrlData(self._active_cluster_index(), data)
        self.S21.set_status_text("已发送保存参数到FLASH命令，请观察下位机返回状态。")


    def _active_alarm_ready(self, show_dialog=True):
        page = getattr(self, "S28", None)
        if page is None:
            return False
        page.set_cluster_context(self._active_cluster_index(), getattr(self, "selected_cluster_address", ""))
        if not getattr(self, "can_ready", False) or getattr(self, "c", None) is None:
            page.set_status_text("CAN未连接，无法读取实时告警。", failed=True)
            if show_dialog:
                QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再读取实时告警。")
            return False
        if self._active_cluster_index() <= 0:
            page.set_status_text("未选择目标簇，无法读取实时告警。", failed=True)
            if show_dialog:
                QMessageBox.warning(self, "未选择簇", "请先选择目标簇。")
            return False
        return True


    def on_active_alarm_interval_changed(self, _value):
        timer = getattr(self, "timerActiveAlarm", None)
        if timer is not None:
            timer.setInterval(self.S28.refresh_interval_ms())


    def on_active_alarm_auto_refresh_toggled(self, checked):
        if checked:
            self.S28.set_status_text("自动刷新已开启。")
            self._refresh_active_alarm_page_if_visible(force=True)
        else:
            self.S28.set_status_text("自动刷新已关闭，可点击“刷新一次”手动读取。")


    def _refresh_active_alarm_page_if_visible(self, force=False):
        if not hasattr(self, "S28"):
            return
        if getattr(self, "table_index", None) != self._active_alarm_tab_index():
            return
        if not self.S28.auto_refresh_enabled():
            return
        self.refresh_active_alarm_page(show_dialog=False)


    def read_active_alarm_count(self, cluster_index):
        expected_id = self._diag_response_id(cluster_index, RESP_READ_ACTIVE_ALARM)
        self._flush_diag_rx()
        self._send_diag_request(cluster_index, CMD_READ_ACTIVE_ALARM, bytes([0]), "读取实时告警总数")
        frame = self._wait_diag_frame(
            expected_id,
            lambda frame: len(frame.data) >= 1 and frame.data[0] not in (0xFE, 0xFF),
            1.5,
            "读取实时告警总数",
        )
        return int(frame.data[0])


    def read_active_alarm_entry(self, cluster_index, alarm_index):
        alarm_index = int(alarm_index)
        expected_id = self._diag_response_id(cluster_index, RESP_READ_ACTIVE_ALARM)
        self._flush_diag_rx()
        self._send_diag_request(cluster_index, CMD_READ_ACTIVE_ALARM, bytes([alarm_index & 0xFF]), "读取实时告警")
        info_frame = self._wait_diag_frame(
            expected_id,
            lambda frame: len(frame.data) >= 8 and frame.data[0] == 0xFE and frame.data[1] == alarm_index,
            1.5,
            "读取实时告警内容",
        )
        time_frame = self._wait_diag_frame(
            expected_id,
            lambda frame: len(frame.data) >= 8 and frame.data[0] == 0xFF and frame.data[1] == alarm_index,
            1.5,
            "读取实时告警时间",
        )
        return self.decode_active_alarm_frames(info_frame, time_frame)


    @staticmethod
    def _active_alarm_level_text(level):
        level = int(level)
        text = {
            0: "无告警",
            1: "一级",
            2: "二级",
            3: "三级",
            4: "四级",
            5: "五级",
            6: "即将切断",
            7: "故障切断",
            8: "特殊切断",
        }.get(level, f"{level}级")
        return f"{level} {text}"


    @staticmethod
    def _active_alarm_bat_text(bat_no):
        bat_no = int(bat_no)
        text = {0: "上半簇", 1: "下半簇"}.get(bat_no, f"半簇{bat_no}")
        return f"{bat_no} {text}"


    @staticmethod
    def _decode_active_alarm_time(year, month, day, hour, minute, second):
        year = int(year)
        month = int(month)
        day = int(day)
        hour = int(hour)
        minute = int(minute)
        second = int(second)
        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            return "--"
        return f"{2000 + year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


    def _active_alarm_name(self, raw_alarm_id):
        raw_alarm_id = int(raw_alarm_id)
        names = list(config.get("Alarm_name_key", {}).keys())
        if 0 <= raw_alarm_id < len(names):
            return str(names[raw_alarm_id])
        return f"告警{raw_alarm_id + 1:03d}"


    def decode_active_alarm_frames(self, info_frame, time_frame):
        info = bytes(info_frame.data)
        alarm_time = bytes(time_frame.data)
        raw_alarm_id = int(info[6])
        cell_no = int(info[2])
        bsu_no = int(info[3])
        equip_type = int(info[4])
        alarm_level = int(info[5])
        bat_no = int(info[7])
        position = f"CSU:{bsu_no:03d} / Cell:{cell_no:03d}"
        return {
            "index": int(info[1]),
            "raw_alarm_id": raw_alarm_id,
            "alarm_id": raw_alarm_id + 1,
            "alarm_name": self._active_alarm_name(raw_alarm_id),
            "alarm_level": alarm_level,
            "alarm_level_text": self._active_alarm_level_text(alarm_level),
            "cell_no": cell_no,
            "bsu_no": bsu_no,
            "equip_type": equip_type,
            "position": position,
            "bat_no": bat_no,
            "bat_text": self._active_alarm_bat_text(bat_no),
            "start_time": self._decode_active_alarm_time(
                alarm_time[2],
                alarm_time[3],
                alarm_time[4],
                alarm_time[5],
                alarm_time[6],
                alarm_time[7],
            ),
            "raw_info": info[:8],
            "raw_time": alarm_time[:8],
        }


    def refresh_active_alarm_page(self, show_dialog=False):
        page = getattr(self, "S28", None)
        if page is None:
            return
        if getattr(self, "_active_alarm_refreshing", False):
            return
        if not self._active_alarm_ready(show_dialog=show_dialog):
            return
        self._active_alarm_refreshing = True
        cluster_index = self._active_cluster_index()
        active_timers = self._pause_history_log_timers()
        records = []
        total_count = 0
        error_count = 0
        try:
            page.set_reading(True)
            page.set_active_alarm_status(None, None)
            page.set_status_text("正在读取实时告警总数...")
            QApplication.processEvents()
            total_count = self.read_active_alarm_count(cluster_index)
            read_limit = min(total_count, 0xF0)
            page.set_active_alarm_status(total_count, 0)
            if total_count <= 0:
                page.set_active_alarm_records([], total_count=0)
                page.set_status_text("当前簇无实时告警。")
                return
            for alarm_index in range(1, read_limit + 1):
                page.set_status_text(f"正在读取实时告警 {alarm_index}/{total_count}...")
                QApplication.processEvents()
                try:
                    records.append(self.read_active_alarm_entry(cluster_index, alarm_index))
                except Exception as exc:
                    error_count += 1
                    page.set_status_text(f"实时告警 {alarm_index} 读取失败: {exc}", failed=True)
                    QApplication.processEvents()
            page.set_active_alarm_records(records, total_count=total_count)
            if total_count > read_limit:
                page.set_status_text(f"实时告警读取完成，设备上报 {total_count} 条，按协议最多显示前 {read_limit} 条。")
            elif error_count:
                page.set_status_text(f"实时告警读取完成，成功 {len(records)} 条，失败 {error_count} 条。", failed=True)
            else:
                page.set_status_text(f"实时告警读取完成，共 {len(records)} 条。")
        except Exception as exc:
            page.set_active_alarm_status(total_count, len(records), failed=True)
            page.set_status_text(f"读取实时告警失败: {exc}", failed=True)
            if show_dialog:
                QMessageBox.critical(self, "读取实时告警失败", str(exc))
        finally:
            page.set_reading(False)
            self._resume_history_log_timers(active_timers)
            self._active_alarm_refreshing = False


    def on_active_alarm_read(self):
        self.refresh_active_alarm_page(show_dialog=True)


    def RequestAlarmData(self):
        global g_index

        if not getattr(self, "can_ready", False):
            return
        Cindex = self._active_cluster_index()
        request_limit = getattr(self, "alarm_request_limit", self.S21.alarm_count() * 32)
        if g_index >= request_limit:
            return

        data_id = config["Glaoal_Index_alarm"] + g_index
        b1 = data_id & 0xFF
        b2 = (data_id >> 8) & 0xFF
        b3 = (data_id >> 16) & 0xFF
        b4 = (data_id >> 24) & 0xFF
        data = [b1,b2,b3,b4,0,0,0,0]

        if Cindex==0:
            self.c.Transmit(0x188000F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1880A0F2 + ((Cindex-1) << 8), data, extern_flag=True, data_len=8)

        g_index = g_index+1
        if g_index >= request_limit:
            self.S21.set_status_text("告警参数读取请求已发送完成，等待下位机响应刷新表格。")



    def REAlarmDatafh(self):
        self.on_alarm_parameter_read()

    def load_next_row(self):
        if hasattr(self.S21, "update_alarm_row"):
            return
        #self.tabWidget.setUpdatesEnabled(False)
        ROW = self.current_COUNT//50
        COL = self.current_COUNT%50
        if ROW < len(list(config["Alarm_name_key"])):
            # 模拟为每个单元格添加数据
            if ROW<len(list(config["Alarm_name_key"].keys())) and (COL == 0):
                self.S21.setItem(ROW, COL, list(config["Alarm_name_key"].keys())[ROW])



            if COL<=19:
                try:
                    if COL!=15:
                        self.S21.setItem(ROW, COL + 1, str(Unsignal_Change(Alarm_list[ROW][COL])))
                    else:
                        self.S21.setItem(ROW, COL + 1,str((Alarm_list[ROW][COL])))
                except:
                    pass
            # else:
            #     pass
            # 切断关联继电器（0
            # 表示不切断，1
            # 表示切断；3
            # 个bit对应3个类继电器(
            #     从低到高依次为：放电、加热、充电)：bit0 - bit2表示1级关联，bit4 - bit6表示2级关联，bit8 - bit10表示3级关联）
            if COL == 20:
                temp_d = Alarm_list[ROW][COL]
                b0 = temp_d&0x01
                b1 = (temp_d>>1)&0x01
                b2 = (temp_d >> 2) & 0x01
                b3 = (temp_d >> 3) & 0x01
                b4 = (temp_d >> 4) & 0x01
                b5 = (temp_d >> 5) & 0x01
                b6 = (temp_d >> 6) & 0x01
                b7 = (temp_d >> 7) & 0x01
                b8 = (temp_d >> 8) & 0x01
                b9 = (temp_d >> 9) & 0x01
                b10 = (temp_d >> 10) & 0x01
                self.S21.setItem(ROW, COL + 1+0, str(b0))#放电一级继电器关联
                self.S21.setItem(ROW, COL + 1+1, str(b1))  # 放电一级继电器关联
                self.S21.setItem(ROW, COL + 1 + 2, str(b2))  # 充电一级继电器关联

                self.S21.setItem(ROW, COL + 1+3, str(b4))#放电一级继电器关联
                self.S21.setItem(ROW, COL + 1+4, str(b5))  # 放电一级继电器关联
                self.S21.setItem(ROW, COL + 1 + 5, str(b6))  # 充电一级继电器关联

                self.S21.setItem(ROW, COL + 1+6, str(b8))#放电一级继电器关联
                self.S21.setItem(ROW, COL + 1+7, str(b9))  # 放电一级继电器关联
                self.S21.setItem(ROW, COL + 1 +8, str(b10))  # 充电一级继电器关联
            elif COL==29:
               self.S21.setItem(ROW, COL+1, str(Alarm_list[ROW][21]))  # 充电一级继电器关联
            elif COL==30:
               self.S21.setItem(ROW, COL+1, str(Alarm_list[ROW][22]))  # 充电二级继电器关联
            elif COL==31:
               self.S21.setItem(ROW, COL+1, str(Alarm_list[ROW][23]))  # 充电三级继电器关联
            #高字节表示充电降额，低字节表示放电降额
            elif (COL>31) and (COL<42):
                temp_d = Alarm_list[ROW][24]
                Dis_lv1 = temp_d&(0xFF)
                Charge_lv1 = (temp_d>>8) & (0xFF)

                temp_d = Alarm_list[ROW][25]
                Dis_lv2 = temp_d&(0xFF)
                Charge_lv2 = (temp_d>>8) & (0xFF)

                temp_d = Alarm_list[ROW][26]
                Dis_lv3 = temp_d&(0xFF)
                Charge_lv3 = (temp_d>>8) & (0xFF)

                temp_d = Alarm_list[ROW][27]
                Dis_lv4 = temp_d&(0xFF)
                Charge_lv4 = (temp_d>>8) & (0xFF)

                temp_d = Alarm_list[ROW][28]
                Dis_lv5 = temp_d&(0xFF)
                Charge_lv5 = (temp_d>>8) & (0xFF)

                self.S21.setItem(ROW, 33, str(Charge_lv1))  #1级充电输出额
                self.S21.setItem(ROW, 34, str(Charge_lv2))  # 2级充电输出额
                self.S21.setItem(ROW, 35, str(Charge_lv3))  # 3级充电输出额
                self.S21.setItem(ROW, 36, str(Charge_lv4))  # 4级充电输出额
                self.S21.setItem(ROW, 37, str(Charge_lv5))  # 5级充电输出额

                self.S21.setItem(ROW, 38, str(Dis_lv1))  # 1级放电输出额
                self.S21.setItem(ROW, 39, str(Dis_lv2))  # 2级放电输出额
                self.S21.setItem(ROW, 40, str(Dis_lv3))  # 3级放电输出额
                self.S21.setItem(ROW, 41, str(Dis_lv4))  # 4级放电输出额
                self.S21.setItem(ROW, 42, str(Dis_lv5))  # 5级放电输出额
            else:
                #告警级别（按位设置，位0表示1级告警，位1表示2级告警，位2表示3级告警，位3表示4级告警，位4表示5级告警）
                temp_d = Alarm_list[ROW][29]
                self.S21.setItem(ROW, 43, str(temp_d&0x01))  # 5级放电输出额
                self.S21.setItem(ROW, 44, str((temp_d>>1)&0x01))  # 5级放电输出额
                self.S21.setItem(ROW, 45, str((temp_d >> 2) & 0x01))  # 5级放电输出额
                self.S21.setItem(ROW, 46, str((temp_d >> 3) & 0x01))  # 5级放电输出额
                self.S21.setItem(ROW, 47, str((temp_d >> 4) & 0x01))  # 5级放电输出额

            #屏蔽未使用的告警项
            # for enu, i in enumerate(Alarm_name_key.keys()):
            #     if(Alarm_name_key[i]==0):
            #         self.set_row_color(enu, QColor(192, 192, 192))  # 第 2 行 (索引为 1)

            # 每次加载一行数据后，增加行数
            self.current_COUNT += 1
            #print(self.current_COUNT)
            #self.tabWidget.setUpdatesEnabled(True)
        else:
            # 全部数据加载完毕后，恢复界面更新并停止定时器
            self.current_COUNT=0
            #self.timer.stop()





    def RequestBAUVAR(self):
        if self.table_index == self._current_bau_tab_index():

            for i in range(1):
                # 请求剩余充电时间上半簇

                data = self.BAUSignalQ[self.BAUSignalQ_index]
                data = [data & 0xFF, (data >> 8) & 0xFF, (data >> 16) & 0xFF, (data >> 24) & 0xFF, 0, 0, 0, 0]
                self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)
                self.BAUSignalQ_index = (self.BAUSignalQ_index + 1) % len(self.BAUSignalQ)



    def RequestBCUVAR(self):
        if self.table_index == self._realtime_monitor_tab_index():
            index = self._active_cluster_index()
            signal_ids = getattr(self, "realtime_monitor_signal_ids", ())
            if index > 0 and signal_ids:
                data = signal_ids[self.realtime_monitor_query_index]
                data = [data&0xFF, (data>>8)&0xFF,  (data>>16)&0xFF,  (data>>24)&0xFF, 0, 0, 0, 0]
                self.QueryData(index,data)
                self.realtime_monitor_query_index = (self.realtime_monitor_query_index + 1) % len(signal_ids)
            return

        if self.table_index == self.CLUSTER_TAB_INDEX:
            index = self._active_cluster_index()
            for i in range(1):
                #请求剩余充电时间上半簇

                data = self.BCUSignalQ[self.BCUSignalQ_index]
                data = [data&0xFF, (data>>8)&0xFF,  (data>>16)&0xFF,  (data>>24)&0xFF, 0, 0, 0, 0]
                self.QueryData(index,data)
                self.BCUSignalQ_index = (self.BCUSignalQ_index+1)%len(self.BCUSignalQ)


        if self.table_index == self._balance_tab_index():

            BAL_STARTE_0_15_LOW =(4126+self.BAL_index * BAL_JG_LEN)&0xFF
            BAL_STARTE_0_15_HIGH = ((4126 + self.BAL_index * BAL_JG_LEN)>>8) & 0xFF
            data = [BAL_STARTE_0_15_LOW, BAL_STARTE_0_15_HIGH, 0, 0, 0, 0, 0, 0]#LECU1[0-15]
            self.QueryData(self._active_cluster_index(), data)

            BAL_STARTE_0_15_LOW =(4127+self.BAL_index * BAL_JG_LEN)&0xFF
            BAL_STARTE_0_15_HIGH = ((4127 + self.BAL_index * BAL_JG_LEN)>>8) & 0xFF
            data = [BAL_STARTE_0_15_LOW, BAL_STARTE_0_15_HIGH, 0, 0, 0, 0, 0, 0]#LECU1[0-15]
            self.QueryData(self._active_cluster_index(), data)


            self.BAL_index = (self.BAL_index+1)%config['LECU_NUM']

        if self.table_index == self._abnormal_cell_tab_index():
            index = self._active_cluster_index()
            for i in range(1):
                # 请求剩余充电时间上半簇

                data = self.BCUSignalQ_DXYC[self.BCUSignalQ_DXYC_index]
                data = [data & 0xFF, (data >> 8) & 0xFF, (data >> 16) & 0xFF, (data >> 24) & 0xFF, 0, 0, 0, 0]
                self.QueryData(index, data)
                self.BCUSignalQ_DXYC_index = (self.BCUSignalQ_DXYC_index + 1) % len(self.BCUSignalQ_DXYC)


    def ChanlCtrlBAUEnable(self):
        index = self.S17.comboBox_10.currentIndex()
        #1-J8-HSD1
        if index==0:
            data = [2,0,1,0,1,0,0,0]

        #2 - J8 - HSD2
        if index==1:
            data = [2,0,2,0,1,0,0,0]
        #3 - J8 - HSD3
        if index==2:
            data = [2,0,3,0,1,0,0,0]
        #4-J8-HSD4
        if index==3:
            data = [2,0,4,0,1,0,0,0]
        #5-J8-LSD1
        if index==4:
            data = [2,0,5,0,1,0,0,0]
        #6-J8-LSD2
        if index==5:
            data = [2,0,6,0,1,0,0,0]
        #11-HSDDIG控制LSD1/2 HSD1/2/3/4
        if index==6:
            data = [2,0,11,0,1,0,0,0]
        #12-J3-BCU_ADDR_DO
        if index==7:
            data = [2,0,12,0,1,0,0,0]
        #13-BZ-BEEP-蜂鸣器
        if index==8:
            data = [2,0,13,0,1,0,0,0]
        #15-VOUT_5V 电源控制（屏5V供电）
        if index==9:
            data = [2,0,15,0,1,0,0,0]
        #20-J4-DO_CTRL_COM1
        if index==10:
            data = [2,0,20,0,1,0,0,0]
        #21-J4-DO_CTRL_COM2
        if index==11:
            data = [2,0,21,0,1,0,0,0]
        #22-J4-DO_CTRL_COM3
        if index==12:
            data = [2,0,22,0,1,0,0,0]
        #23-J4-DO_CTRL_COM4
        if index==13:
            data = [2,0,23,0,1,0,0,0]
        #24-J4-DO_CTRL_COM5
        if index==14:
            data = [2,0,24,0,1,0,0,0]
        #25-J4-DO_CTRL_COM6
        if index==15:
            data = [2,0,25,0,1,0,0,0]
        #42-LED-绿色指示灯-DO
        if index==16:
            data = [2,0,42,0,1,0,0,0]
        #82-J8-DO控制
        if index==17:
            data = [2,0,82,0,1,0,0,0]
        #84-J9-蓝牙控制-控制蓝牙24V供电
        if index==18:
            data = [2,0,84,0,1,0,0,0]
        #85-J9-蓝牙-唤醒IO
        if index==19:
            data = [2,0,85,0,1,0,0,0]
        #86-J9-蓝牙-控制蓝牙3.3V供电
        if index==20:
            data = [2,0,86,0,1,0,0,0]

        self.c.Transmit(0x1888EFF2, data, extern_flag=True, data_len=8)



    def ChanlCtrlBAUDisEnable(self):
        index = self.S17.comboBox_10.currentIndex()
        #1-J8-HSD1
        if index==0:
            data = [2,0,1,0,0,0,0,0]

        #2 - J8 - HSD2
        if index==1:
            data = [2,0,2,0,0,0,0,0]
        #3 - J8 - HSD3
        if index==2:
            data = [2,0,3,0,0,0,0,0]
        #4-J8-HSD4
        if index==3:
            data = [2,0,4,0,0,0,0,0]
        #5-J8-LSD1
        if index==4:
            data = [2,0,5,0,0,0,0,0]
        #6-J8-LSD2
        if index==5:
            data = [2,0,6,0,0,0,0,0]
        #11-HSDDIG控制LSD1/2 HSD1/2/3/4
        if index==6:
            data = [2,0,11,0,0,0,0,0]
        #12-J3-BCU_ADDR_DO
        if index==7:
            data = [2,0,12,0,0,0,0,0]
        #13-BZ-BEEP-蜂鸣器
        if index==8:
            data = [2,0,13,0,0,0,0,0]
        #15-VOUT_5V 电源控制（屏5V供电）
        if index==9:
            data = [2,0,15,0,0,0,0,0]
        #20-J4-DO_CTRL_COM1
        if index==10:
            data = [2,0,20,0,0,0,0,0]
        #21-J4-DO_CTRL_COM2
        if index==11:
            data = [2,0,21,0,0,0,0,0]
        #22-J4-DO_CTRL_COM3
        if index==12:
            data = [2,0,22,0,0,0,0,0]
        #23-J4-DO_CTRL_COM4
        if index==13:
            data = [2,0,23,0,0,0,0,0]
        #24-J4-DO_CTRL_COM5
        if index==14:
            data = [2,0,24,0,0,0,0,0]
        #25-J4-DO_CTRL_COM6
        if index==15:
            data = [2,0,25,0,0,0,0,0]
        #42-LED-绿色指示灯-DO
        if index==16:
            data = [2,0,42,0,0,0,0,0]
        #82-J8-DO控制
        if index==17:
            data = [2,0,82,0,0,0,0,0]
        #84-J9-蓝牙控制-控制蓝牙24V供电
        if index==18:
            data = [2,0,84,0,0,0,0,0]
        #85-J9-蓝牙-唤醒IO
        if index==19:
            data = [2,0,85,0,0,0,0,0]
        #86-J9-蓝牙-控制蓝牙3.3V供电
        if index==20:
            data = [2,0,86,0,0,0,0,0]

        self.c.Transmit(0x1888EFF2, data, extern_flag=True, data_len=8)


    def ChanlCtrlBCUEnable(self):
        index = self.S17.comboBox_12.currentIndex()
        Cindex = self._active_cluster_index()
        #1-J1-HSD1
        if index==0:
            data = [2, 0, 1, 0, 1, 0, 0, 0]
        #2-J1-HSD2
        if index==1:
            data = [2, 0, 2, 0, 1, 0, 0, 0]
        #3-J1-HSD3
        if index==2:
            data = [2, 0, 3, 0, 1, 0, 0, 0]
        #4-J1-HSD4
        if index==3:
            data = [2, 0, 4, 0, 1, 0, 0, 0]
        #5-J1-HSD5
        if index==4:
            data = [2, 0, 5, 0, 1, 0, 0, 0]
        #6-J1-HSD6
        if index==5:
            data = [2, 0, 6, 0, 1, 0, 0, 0]
        #7-J1-HSD7
        if index==6:
            data = [2, 0, 7, 0, 1, 0, 0, 0]
        #8-J1-HSD8
        if index==7:
            data = [2, 0, 8, 0, 1, 0, 0, 0]
        #25-J2-PWR_FAN
        if index==8:
            data = [2, 0, 25, 0, 1, 0, 0, 0]
        #20-J5-COM1
        if index==9:
            data = [2, 0, 20, 0, 1, 0, 0, 0]
        #21-J5-COM2
        if index==10:
            data = [2, 0, 21, 0, 1, 0, 0, 0]
        #22-J5-COM3
        if index==11:
            data = [2, 0, 22, 0, 1, 0, 0, 0]
        #23-J5-COM4
        if index==12:
            data = [2, 0, 23, 0, 1, 0, 0, 0]
        #11-J8-ADDR_DO
        if index==13:
            data = [2, 0, 11, 0, 1, 0, 0, 0]
        #9-J9_LSD1-
        if index==14:
            data = [2, 0, 9, 0, 1, 0, 0, 0]
        #10_J9_LSD2-
        if index==15:
            data = [2, 0, 10, 0, 1, 0, 0, 0]
        #24_J9_DO控制
        if index==16:
            data = [2, 0, 24, 0, 1, 0, 0, 0]
        #44_LED1
        if index==17:
            data = [2, 0, 44, 0, 1, 0, 0, 0]
        #45_LED2
        if index==18:
            data = [2, 0, 45, 0, 1, 0, 0, 0]
        #46_SOC_LED1
        if index==19:
            data = [2, 0, 46, 0, 1, 0, 0, 0]
        #47_SCO_LED2
        if index==20:
            data = [2, 0, 47, 0, 1, 0, 0, 0]
        #43_RLED
        if index==21:
            data = [2, 0, 43, 0, 1, 0, 0, 0]
        #42_GLED
        if index==22:
            data = [2, 0, 42, 0, 1, 0, 0, 0]
        #48_SOC_LED3
        if index==23:
            data = [2, 0, 48, 0, 1, 0, 0, 0]
        #49_SOC_LED4
        if index==24:
            data = [2, 0, 49, 0, 1, 0, 0, 0]

        #data = [b1,b2,b3,b4,0,0,0,0]
        if Cindex==0:
            self.c.Transmit(0x188800F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1888A0F2 + ((Cindex-1) << 8), data, extern_flag=True, data_len=8)

    def ChanlCtrlBCUDisEnable(self):
        index = self.S17.comboBox_12.currentIndex()
        Cindex = self._active_cluster_index()
        # 1-J1-HSD1
        if index == 0:
            data = [2, 0, 1, 0, 0, 0, 0, 0]
        # 2-J1-HSD2
        if index == 1:
            data = [2, 0, 2, 0, 0, 0, 0, 0]
        # 3-J1-HSD3
        if index == 2:
            data = [2, 0, 3, 0, 0, 0, 0, 0]
        # 4-J1-HSD4
        if index == 3:
            data = [2, 0, 4, 0, 0, 0, 0, 0]
        # 5-J1-HSD5
        if index == 4:
            data = [2, 0, 5, 0, 0, 0, 0, 0]
        # 6-J1-HSD6
        if index == 5:
            data = [2, 0, 6, 0, 0, 0, 0, 0]
        # 7-J1-HSD7
        if index == 6:
            data = [2, 0, 7, 0, 0, 0, 0, 0]
        # 8-J1-HSD8
        if index == 7:
            data = [2, 0, 8, 0, 0, 0, 0, 0]
        # 25-J2-PWR_FAN
        if index == 8:
            data = [2, 0, 25, 0, 0, 0, 0, 0]
        # 20-J5-COM1
        if index == 9:
            data = [2, 0, 20, 0, 0, 0, 0, 0]
        # 21-J5-COM2
        if index == 10:
            data = [2, 0, 21, 0, 0, 0, 0, 0]
        # 22-J5-COM3
        if index == 11:
            data = [2, 0, 22, 0, 0, 0, 0, 0]
        # 23-J5-COM4
        if index == 12:
            data = [2, 0, 23, 0, 0, 0, 0, 0]
        # 11-J8-ADDR_DO
        if index == 13:
            data = [2, 0, 11, 0, 0, 0, 0, 0]
        # 9-J9_LSD1-
        if index == 14:
            data = [2, 0, 9, 0, 0, 0, 0, 0]
        # 10_J9_LSD2-
        if index == 15:
            data = [2, 0, 10, 0, 0, 0, 0, 0]
        # 24_J9_DO控制
        if index == 16:
            data = [2, 0, 24, 0, 0, 0, 0, 0]
        # 44_LED1
        if index == 17:
            data = [2, 0, 44, 0, 0, 0, 0, 0]
        # 45_LED2
        if index == 18:
            data = [2, 0, 45, 0, 0, 0, 0, 0]
        # 46_SOC_LED1
        if index == 19:
            data = [2, 0, 46, 0, 0, 0, 0, 0]
        # 47_SCO_LED2
        if index == 20:
            data = [2, 0, 47, 0, 0, 0, 0, 0]
        # 43_RLED
        if index == 21:
            data = [2, 0, 43, 0, 0, 0, 0, 0]
        # 42_GLED
        if index == 22:
            data = [2, 0, 42, 0, 0, 0, 0, 0]
        # 48_SOC_LED3
        if index == 23:
            data = [2, 0, 48, 0, 0, 0, 0, 0]
        # 49_SOC_LED4
        if index == 24:
            data = [2, 0, 49, 0, 0, 0, 0, 0]

        # data = [b1,b2,b3,b4,0,0,0,0]
        if Cindex == 0:
            self.c.Transmit(0x188800F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1888A0F2 + ((Cindex-1) << 8), data, extern_flag=True, data_len=8)


    def BALANCECtrl(self):
        AFE_index = self.S17.comboBox_2.currentIndex()
        Cindex = self._active_cluster_index()

        b1 = self.S17.CB1.isChecked()
        b2 = self.S17.CB2.isChecked()
        b3 = self.S17.CB3.isChecked()
        b4 = self.S17.CB4.isChecked()
        b5 = self.S17.CB5.isChecked()
        b6 = self.S17.CB6.isChecked()
        b7 = self.S17.CB7.isChecked()
        b8 = self.S17.CB8.isChecked()
        b9 = self.S17.CB9.isChecked()
        b10 = self.S17.CB10.isChecked()
        b11 = self.S17.CB11.isChecked()
        b12 = self.S17.CB12.isChecked()
        b13 = self.S17.CB13.isChecked()
        b14 = self.S17.CB14.isChecked()
        b15 = self.S17.CB15.isChecked()
        b16 = self.S17.CB16.isChecked()

        Ctrl_cmd = b1+(b2<<1)+(b3<<2)+(b4<<3)+(b5<<4)+(b6<<5)+(b7<<6)+(b8<<7)+(b9<<8)+(b10<<9)+(b11<<10)+(b12<<11)+(b13<<12)+(b14<<13)+(b15<<14)+(b16<<15)

        data = [7,0,AFE_index,0,Ctrl_cmd&0xFF,(Ctrl_cmd>>8)&0xFF,0,0]

        if Cindex == 0:
            self.c.Transmit(0x188800F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1888A0F2 + ((Cindex-1) << 8), data, extern_flag=True, data_len=8)

    def BALANCECtrlClose(self):
        Cindex = self._active_cluster_index()
        for module_index in range(int(config["LECU_NUM"])):
            data = [7, 0, module_index, 0, 0, 0, 0, 0]
            self.CtrlData(Cindex, data)

        self.S17.CB1.setChecked(False)
        self.S17.CB2.setChecked(False)
        self.S17.CB3.setChecked(False)
        self.S17.CB4.setChecked(False)
        self.S17.CB5.setChecked(False)
        self.S17.CB6.setChecked(False)
        self.S17.CB7.setChecked(False)
        self.S17.CB8.setChecked(False)
        self.S17.CB9.setChecked(False)
        self.S17.CB10.setChecked(False)
        self.S17.CB11.setChecked(False)
        self.S17.CB12.setChecked(False)
        self.S17.CB13.setChecked(False)
        self.S17.CB14.setChecked(False)
        self.S17.CB15.setChecked(False)
        self.S17.CB16.setChecked(False)


    def _send_balance_mask(self, module_index, enabled_values):
        if not getattr(self, "can_ready", False):
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再发送均衡控制命令。")
            return False
        mask = 0
        for cell_index, enabled in enumerate(enabled_values):
            if enabled:
                mask |= 1 << cell_index
        data = [7, 0, int(module_index), 0, mask & 0xFF, (mask >> 8) & 0xFF, 0, 0]
        self.CtrlData(self._active_cluster_index(), data)
        return True


    def on_balance_control_apply(self, module_index, enabled_values):
        if self._send_balance_mask(module_index, enabled_values):
            enabled_count = sum(1 for enabled in enabled_values if enabled)
            self.S25.set_status_text(
                f"已发送模组 {module_index + 1} 均衡控制命令，开启 {enabled_count} 个单体。"
            )


    def on_balance_control_close_module(self, module_index):
        if self._send_balance_mask(module_index, [False] * int(config["CELL_NUM"])):
            self.S25.set_status_text(f"已发送模组 {module_index + 1} 均衡关闭命令。")


    def on_balance_control_close_all(self):
        if not getattr(self, "can_ready", False):
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再发送均衡控制命令。")
            return
        for module_index in range(int(config["LECU_NUM"])):
            self._send_balance_mask(module_index, [False] * int(config["CELL_NUM"]))
            time.sleep(0.003)
        self.S25.set_status_text("已发送全部模组均衡关闭命令。")


    def _history_log_dir(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "hisData")


    def _history_log_ready(self):
        if not getattr(self, "can_ready", False) or getattr(self, "c", None) is None:
            QMessageBox.warning(self, "CAN未连接", "请先连接CAN后再读取历史日志。")
            return False
        if self._active_cluster_index() <= 0:
            QMessageBox.warning(self, "未选择簇", "请先选择目标簇。")
            return False
        return True


    def _pause_history_log_timers(self):
        active_timer_names = []
        for timer_name in (
            "send_time",
            "send_time1",
            "timer1",
            "timerResData",
            "timerDI",
            "timer_Forcecharge",
            "timerActiveAlarm",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None and timer.isActive():
                timer.stop()
                active_timer_names.append(timer_name)
        return active_timer_names


    def _resume_history_log_timers(self, active_timer_names):
        if not getattr(self, "can_ready", False):
            return
        for timer_name in active_timer_names:
            timer = getattr(self, timer_name, None)
            if timer is not None and not timer.isActive():
                timer.start()


    def _history_log_addr(self, cluster_index):
        return int(str(config["ADDRESLIST"][cluster_index]), 16)


    def _history_log_request_id(self, cluster_index):
        target = self._history_log_addr(cluster_index)
        source = int(str(config.get("IPCaddr", "F2")), 16)
        return 0x18000000 | (0x86 << 16) | (target << 8) | source


    def _history_log_response_id(self, cluster_index, response_pf=0x87):
        source = self._history_log_addr(cluster_index)
        target = int(str(config.get("IPCaddr", "F2")), 16)
        return 0x18000000 | (int(response_pf) << 16) | (target << 8) | source


    def _flush_can_rx(self):
        self._history_log_frame_backlog = []
        flushed_count = 0
        for _ in range(4):
            frames = self.c.receive_frames(max_count=200, timeout_ms=0)
            if not frames:
                break
            flushed_count += len(frames)
        if flushed_count:
            self.rx_frame_count += flushed_count
            self._update_rx_status()


    def _pop_history_log_backlog(self, expected_id, predicate):
        backlog = getattr(self, "_history_log_frame_backlog", [])
        for index, frame in enumerate(backlog):
            if int(frame.frame_id) == int(expected_id) and predicate(frame):
                return backlog.pop(index)
        return None


    def _send_history_log_request(self, cluster_index, log_index, log_type):
        data = [
            int(log_index) & 0xFF,
            (int(log_index) >> 8) & 0xFF,
            int(log_type) & 0xFF,
            0,
            0,
            0,
            0,
            0,
        ]
        result = self.c.Transmit(
            self._history_log_request_id(cluster_index),
            data,
            extern_flag=True,
            data_len=8,
        )
        if result <= 0:
            raise RuntimeError("历史日志读取请求发送失败")


    def _wait_history_log_frame(self, expected_id, predicate, timeout_s, label):
        deadline = time.monotonic() + max(float(timeout_s), 0.0)
        while time.monotonic() <= deadline:
            frame = self._pop_history_log_backlog(expected_id, predicate)
            if frame is not None:
                return frame
            remaining_ms = max(int((deadline - time.monotonic()) * 1000), 1)
            frames = self.c.receive_frames(max_count=200, timeout_ms=min(remaining_ms, 50))
            if frames:
                self.rx_frame_count += len(frames)
                self._update_rx_status()
            for frame_index, frame in enumerate(frames):
                if int(frame.frame_id) != int(expected_id):
                    continue
                if predicate(frame):
                    self._history_log_frame_backlog.extend(
                        later_frame
                        for later_frame in frames[frame_index + 1:]
                        if int(later_frame.frame_id) == int(expected_id)
                    )
                    return frame
                self._history_log_frame_backlog.append(frame)
            QApplication.processEvents()
        raise RuntimeError(f"{label}响应超时")


    def read_history_log_count(self, cluster_index, log_type):
        if int(log_type) != self.S26.LOG_TYPE_ALARM:
            raise RuntimeError("当前下位机CAN日志接口仅支持读取告警日志。")
        expected_id = self._history_log_response_id(cluster_index)
        last_error = None
        for _attempt in range(2):
            try:
                self._flush_can_rx()
                self._send_history_log_request(cluster_index, 0, log_type)
                frame = self._wait_history_log_frame(
                    expected_id,
                    lambda frame: len(frame.data) >= 4 and frame.data[0] == 0xFF and frame.data[1] == int(log_type),
                    2.0,
                    "读取日志总数",
                )
                return int(frame.data[2]) | (int(frame.data[3]) << 8)
            except Exception as exc:
                last_error = exc
                time.sleep(0.05)
        raise last_error


    def read_history_log_entry(self, cluster_index, log_index, log_type):
        last_error = None
        for _attempt in range(2):
            try:
                self._flush_can_rx()
                self._send_history_log_request(cluster_index, log_index, log_type)
                payload = self._collect_history_log_payload(cluster_index, timeout_s=5.0)
                return self.decode_history_log_payload(payload, log_type)
            except Exception as exc:
                last_error = exc
                time.sleep(0.05)
        raise last_error


    def _collect_history_log_payload(self, cluster_index, timeout_s):
        expected_id = self._history_log_response_id(cluster_index)
        deadline = time.monotonic() + max(float(timeout_s), 0.0)
        chunks = {}
        while len(chunks) < 8 and time.monotonic() <= deadline:
            remaining_s = max(deadline - time.monotonic(), 0.0)
            frame = self._wait_history_log_frame(
                expected_id,
                lambda frame: len(frame.data) >= 1 and (frame.data[0] == 0xFE or 1 <= frame.data[0] <= 8),
                remaining_s,
                "读取日志数据",
            )
            chunk_index = int(frame.data[0])
            if chunk_index == 0xFE:
                raise RuntimeError("设备拒绝读取该条历史日志")
            chunks[chunk_index] = bytes(frame.data[1:8]).ljust(7, b"\x00")
        missing = [str(index) for index in range(1, 9) if index not in chunks]
        if missing:
            raise RuntimeError(f"读取日志数据响应不完整，缺少包: {', '.join(missing)}")
        return b"".join(chunks[index] for index in range(1, 9))[:52]


    def on_history_log_read(self):
        if not self._history_log_ready():
            return
        log_type = self.S26.selected_log_type()
        if int(log_type) != self.S26.LOG_TYPE_ALARM:
            self.S26.clear_records()
            self.S26.set_status("当前下位机CAN接口暂仅支持读取告警日志。", failed=True)
            return
        self.history_log_stop_requested = False
        self.S26.clear_records()
        self.S26.set_reading(True)
        self.S26.set_status("正在读取日志总数...")

        active_timers = self._pause_history_log_timers()
        total_count = 0
        read_count = 0
        error_count = 0
        try:
            cluster_index = self._active_cluster_index()
            total_count = self.read_history_log_count(cluster_index, log_type)
            self.S26.set_counts(total_count, 0)
            if total_count <= 0:
                self.S26.set_status("设备暂无历史日志")
                return
            for log_index in range(total_count, 0, -1):
                if self.history_log_stop_requested:
                    self.S26.set_status(f"已停止，成功读取 {read_count} 条，失败 {error_count} 条")
                    break
                self.S26.set_status(f"正在读取第 {log_index} 条...")
                QApplication.processEvents()
                try:
                    record = self.read_history_log_entry(cluster_index, log_index, log_type)
                except Exception as exc:
                    error_count += 1
                    self.S26.set_counts(total_count, read_count)
                    self.S26.set_status(f"第 {log_index} 条读取失败: {exc}", failed=True)
                    QApplication.processEvents()
                    continue
                read_count += 1
                self.S26.append_record(record)
                self.S26.set_counts(total_count, read_count)
                QApplication.processEvents()
            if not self.history_log_stop_requested:
                self.S26.set_status(f"日志读取正常，成功 {read_count} 条，失败 {error_count} 条")
        except Exception as exc:
            self.S26.set_status(f"读取失败: {exc}", failed=True)
            QMessageBox.critical(self, "读取历史日志失败", str(exc))
        finally:
            self.S26.set_reading(False)
            self.history_log_stop_requested = False
            self._resume_history_log_timers(active_timers)


    def on_history_log_stop(self):
        self.history_log_stop_requested = True
        self.S26.set_status("正在停止读取...")


    def on_history_log_save(self):
        if not self.S26.records:
            QMessageBox.information(self, "没有可保存的日志", "当前表格没有历史日志数据。")
            return
        path = self.S26.choose_save_path()
        if not path:
            return
        try:
            self.S26.save_records_to_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "保存历史日志失败", str(exc))
            return
        self.S26.set_status(f"日志已保存: {path}")


    def on_history_log_clear_table(self):
        self.S26.clear_records()


    def on_history_log_clear_device(self):
        if not self._history_log_ready():
            return
        log_type = self.S26.selected_log_type()
        para2 = 6 if int(log_type) == self.S26.LOG_TYPE_ALARM else 7
        log_type_text = "告警日志" if int(log_type) == self.S26.LOG_TYPE_ALARM else "其他日志"
        reply = QMessageBox.question(
            self,
            "清空历史日志",
            f"确认清空簇{self._active_cluster_index()} ({self.selected_cluster_address}) 的{log_type_text}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        active_timers = self._pause_history_log_timers()
        try:
            self._flush_can_rx()
            data = [4, 0, 0, 0, para2, 0, 0, 0]
            self.CtrlData(self._active_cluster_index(), data)
            expected_id = self._history_log_response_id(self._active_cluster_index(), response_pf=0x89)
            self._wait_history_log_frame(
                expected_id,
                lambda frame: len(frame.data) >= 1,
                1.0,
                "清空历史日志",
            )
        except Exception as exc:
            QMessageBox.critical(self, "清空历史日志失败", str(exc))
            return
        finally:
            self._resume_history_log_timers(active_timers)
        self.S26.clear_records()
        self.S26.set_status("设备历史日志已清空")


    @staticmethod
    def _u16(payload, offset):
        return int.from_bytes(payload[offset:offset + 2], byteorder="little", signed=False)


    @staticmethod
    def _s16(payload, offset):
        return int.from_bytes(payload[offset:offset + 2], byteorder="little", signed=True)


    @staticmethod
    def _u32(payload, offset):
        return int.from_bytes(payload[offset:offset + 4], byteorder="little", signed=False)


    @staticmethod
    def _decode_history_time(raw_time):
        year = 2000 + (raw_time & 0x3F)
        month = (raw_time >> 6) & 0x0F
        day = (raw_time >> 10) & 0x1F
        hour = (raw_time >> 15) & 0x1F
        minute = (raw_time >> 20) & 0x3F
        second = (raw_time >> 26) & 0x3F
        if not (1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 59):
            return "--"
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


    @staticmethod
    def _decode_relay_status(relay_byte):
        active_relays = [
            f"{index}继电器闭合"
            for index in range(1, 9)
            if int(relay_byte) & (1 << (index - 1))
        ]
        return "，".join(active_relays) if active_relays else "0"


    @staticmethod
    def _history_log_subtype_text(subtype):
        subtype_text = {
            3: "告警产生",
            4: "告警消失",
            8: "清空历史事件日志",
            9: "清空实时数据日志",
            10: "保存参数到FLASH",
            11: "保存校准系数",
            12: "设置时间",
            13: "PAR类索引修改",
        }
        return subtype_text.get(int(subtype), f"子类型{subtype}")


    @staticmethod
    def _decode_history_alarm_position(alarm_info):
        cell_no = alarm_info & 0x7F
        bsu_no = (alarm_info >> 7) & 0x7F
        equip_type = (alarm_info >> 14) & 0x0F
        bat_no = (alarm_info >> 31) & 0x01
        return f"BCU: {equip_type:03d}---CSU: {bsu_no:03d}---Cell: {cell_no:03d}---Bat: {bat_no}"


    @staticmethod
    def _decode_log_cell_voltage_info(raw_value):
        cell_voltage = raw_value & 0x3FFF
        bcu_no = (raw_value >> 14) & 0x3F
        csu_no = (raw_value >> 20) & 0x3F
        cell_no = (raw_value >> 26) & 0x3F
        return cell_voltage, f"BCU:{bcu_no:03d}|CSU:{csu_no:03d}|Cell:{cell_no:03d}"


    @classmethod
    def _decode_log_cell_temperature_info(cls, payload, offset):
        cell_temperature = cls._s16(payload, offset) / 10.0
        position = cls._u16(payload, offset + 2)
        bcu_no = position & 0x1F
        csu_no = (position >> 5) & 0x1F
        cell_no = (position >> 10) & 0x3F
        return cell_temperature, f"BCU:{bcu_no:03d}|CSU:{csu_no:03d}|Cell:{cell_no:03d}"


    def _history_log_alarm_name(self, alarm_id):
        alarm_id = int(alarm_id)
        if alarm_id <= 0:
            return "-"
        names = list(config.get("Alarm_name_key", {}).keys())
        index = alarm_id - 1
        if 0 <= index < len(names):
            return str(names[index])
        return f"告警{alarm_id:03d}"


    def decode_history_log_payload(self, payload, log_type):
        payload = bytes(payload)
        if len(payload) < 52:
            raise RuntimeError(f"历史日志数据长度不足: {len(payload)} < 52")

        sequence = self._u16(payload, 0)
        subtype = payload[2]
        run_status = payload[3]
        relay_byte = payload[8]
        alarm_count = payload[9]
        raw_word = self._u16(payload, 10)
        alarm_info = self._u32(payload, 12)
        alarm_id = (alarm_info >> 24) & 0x3F
        alarm_level = (alarm_info >> 18) & 0x3F
        max_cell_voltage, max_cell_voltage_position = self._decode_log_cell_voltage_info(
            self._u32(payload, 32)
        )
        min_cell_voltage, min_cell_voltage_position = self._decode_log_cell_voltage_info(
            self._u32(payload, 36)
        )
        max_cell_temperature, max_cell_temperature_position = self._decode_log_cell_temperature_info(
            payload,
            40,
        )
        min_cell_temperature, min_cell_temperature_position = self._decode_log_cell_temperature_info(
            payload,
            44,
        )

        return HistoryLogRecord(
            sequence=sequence,
            timestamp=self._decode_history_time(self._u32(payload, 4)),
            log_type="告警日志" if int(log_type) == self.S26.LOG_TYPE_ALARM else "其他日志",
            log_subtype=self._history_log_subtype_text(subtype),
            run_status=run_status,
            relay_status=self._decode_relay_status(relay_byte),
            alarm_count=alarm_count,
            raw_word=raw_word,
            alarm_id=alarm_id,
            alarm_name=self._history_log_alarm_name(alarm_id),
            alarm_level=alarm_level,
            alarm_position=self._decode_history_alarm_position(alarm_info),
            total_voltage=self._u16(payload, 16) / 10.0,
            total_current=self._s16(payload, 18) / 10.0,
            soc=self._u16(payload, 20) / 10.0,
            soh=self._u16(payload, 22) / 10.0,
            p_bus_resistance=self._u16(payload, 24),
            n_bus_resistance=self._u16(payload, 26),
            diff_voltage=self._u16(payload, 28),
            diff_temperature=self._u16(payload, 30) / 10.0,
            max_cell_voltage=max_cell_voltage,
            max_cell_voltage_position=max_cell_voltage_position,
            min_cell_voltage=min_cell_voltage,
            min_cell_voltage_position=min_cell_voltage_position,
            max_cell_temperature=max_cell_temperature,
            max_cell_temperature_position=max_cell_temperature_position,
            min_cell_temperature=min_cell_temperature,
            min_cell_temperature_position=min_cell_temperature_position,
            threshold_value=self._s16(payload, 48),
            actual_value=self._s16(payload, 50),
            raw_payload=payload[:52],
        )


    def DIState(self):
        Cindex = self._active_cluster_index()
        #DI1_H
        data = [0x24,0,0,0,0,0,0,0]
        self.QueryData(Cindex,data)

        #DI2_H
        data = [0x25,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #DI3_H
        data = [0x26,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #DI4_H
        data = [0x27,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        # DI5_H
        data = [0x28,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #DI6_H
        data = [0x29,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #DI4_L
        data = [0x2D,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #RT1 温度检测
        data = [0x70,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)


        #RT2 温度检测
        data = [0x71,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #RT3 温度加测
        data = [0x72,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #RT4 温度检测
        data = [0x73,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #RT5 温度检测
        data = [0x74,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #RT6 温度检测
        data = [0x75,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #DI1_L
        data = [0x2A,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)
        #DI2_L
        data = [0x2B,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #ADDR_DI
        data = [0x2F,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)

        #DI3_L
        data = [0x2C,0,0,0,0,0,0,0]
        self.QueryData(Cindex, data)


    def DIStateBAU(self):
        # J7 DI1_H
        data = [0x2D, 0, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)

        # J7 DI2_H
        data = [0x2E, 0, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)

        # J7 DI3_H
        data = [0x2F, 0, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)

        # J4 DI1_L
        data = [0x30, 0, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)

        # J4 DI2_L
        data = [0x31, 0, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)

    def DIStateClose(self):
        self.timerDI.stop()

    def DIStateStart(self):
        self.timerDI.start(10)
    def QueryData(self,Cindex,data):
        if Cindex == 0:
            self.c.Transmit(0x188000F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1880A0F2 + ((Cindex - 1) << 8), data, extern_flag=True, data_len=8)

    def CtrlData(self,Cindex,data):
        if Cindex == 0:
            self.c.Transmit(0x188800F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1888A0F2 + ((Cindex - 1) << 8), data, extern_flag=True, data_len=8)

    def SetData(self,Cindex,data):
        if Cindex == 0:
            self.c.Transmit(0x188200F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1882A0F2 + ((Cindex - 1) << 8), data, extern_flag=True, data_len=8)

    def ParProcess(self):
        Cindex = self._active_cluster_index()
        index = self.S23.comboBox_2.currentIndex()+1
        if ((index==4) or (index==5)):
            return

        # 01：恢复校准系数
        # 02：恢复出厂参数
        # 03：恢复运行参数
        # 04：清空EEPROM
        # 05: 恢复产品信息
        # 06：清空告警日志
        # 07：清空普通日志
        # 08：保存参数到FLASH
        # 09：保存校准系数到FLASH
        data = [4, 0, 0, 0, index, 0, 0, 0]
        self.CtrlData(Cindex,data)

    def RequestSetData(self):
        global g_index

        Cindex=self._active_cluster_index()
        #print(g_index)
        b1 = (config["Glaoal_Index_alarm"] + g_index) & (0xFF)
        b2 = ((config["Glaoal_Index_alarm"] + g_index) >> 8) & (0xFF)
        b3 = ((config["Glaoal_Index_alarm"] + g_index) >> 16) & (0xFF)
        b4 = ((config["Glaoal_Index_alarm"] + g_index) >> 24) & (0xFF)
        b5 = ((config["Glaoal_Index_alarm"] + g_index) >> 32) & (0xFF)
        b6 = ((config["Glaoal_Index_alarm"] + g_index) >> 40) & (0xFF)
        data = [b1, b2, b3, b4, b5, b6, 0, 0]

        if Cindex == 0:
            self.c.Transmit(0x188200F2, data, extern_flag=True, data_len=8)
        if Cindex != 0:
            self.c.Transmit(0x1882A0F2 + ((Cindex - 1) << 8), data, extern_flag=True, data_len=8)

        if g_index > 64 * 32:
            self.send_time1.timeout.disconnect(self.RequestSetData)
        g_index = g_index + 1



    def AlarmLevel(self):
        addr = config["ADDRESLIST"][self._active_cluster_index()]
        #遍历字典
        #for addr in AlarmClassDict:
            #遍历ID
        for id in AlarmClassDict[addr]:
            if int(AlarmClassDict[addr][id])==0:
                self.S21.change_row_color(int(id), QColor("green"))
            if int(AlarmClassDict[addr][id]) == 3:
                self.S21.change_row_color(int(id), QColor("yellow"))
            if int(AlarmClassDict[addr][id]) == 2:
                self.S21.change_row_color(int(id), QColor("orange"))
            if int(AlarmClassDict[addr][id]) == 1:
                self.S21.change_row_color(int(id), QColor("red"))


    def ModifyAlarm(self):
        self.on_alarm_parameter_write_current()


    def SaveRunData(self):
        if not self._logging_enabled():
            return
        active_cluster_index = self._active_cluster_index()
        target_cluster_indices = self._log_target_cluster_indices()
        if not target_cluster_indices:
            return

        manager = self._ensure_session_log_manager()
        if not manager.enabled:
            manager.set_enabled(True)
        active_address = ""
        if 0 < active_cluster_index < len(self.ResDataRec):
            active_address = self._cluster_address(active_cluster_index)

        try:
            for cluster_index in target_cluster_indices:
                manager.write_cluster_snapshot(cluster_index, self.ResDataRec[cluster_index])

            if active_address and self.voltage_snapshot_dirty:
                manager.write_voltage_snapshot(active_address, list(Vres))
                self.voltage_snapshot_dirty = False
            if active_address and self.temperature_snapshot_dirty:
                manager.write_temperature_snapshot(active_address, list(VresTem))
                self.temperature_snapshot_dirty = False
            if active_address and self.balance_snapshot_dirty:
                manager.write_balance_snapshot(active_address, list(VresBAL))
                self.balance_snapshot_dirty = False
            if active_address and self.abnormal_snapshot_dirty:
                manager.write_abnormal_snapshot(active_address, list(VresDXYC))
                self.abnormal_snapshot_dirty = False
        except Exception as exc:
            timer = getattr(self, "timerResData", None)
            if timer is not None:
                timer.stop()
            manager.set_enabled(False)
            config["SAVE_LOG"] = 0
            checkbox = getattr(self, "save_log_checkbox", None)
            if checkbox is not None:
                blocker = QtCore.QSignalBlocker(checkbox)
                checkbox.setChecked(False)
                del blocker
            self._set_status_pill(
                getattr(self, "log_status_label", None),
                f"日志: 写入失败 {exc}",
                "danger",
            )
            print(f"save runtime log failed: {exc}")




    def BCUVARSearch(self,index):
        temp=0
        if index==1:
            temp = int(self.S23.lineEdit_13.text())
        elif index==2:
            temp = int(self.S23.lineEdit_15.text())
        elif index==3:
            temp = int(self.S23.lineEdit_17.text())
        elif index==4:
            temp = int(self.S23.lineEdit_19.text())
        data = [temp&0xFF, (temp>>8)&0xFF, 0, 0, 0, 0, 0, 0]
        Cindex = self._active_cluster_index()
        self.QueryData(Cindex, data)

    def BAUVARSearch(self, index):
        temp = 0
        if index==1:
            temp =  int(self.S23.lineEdit_5.text())
        elif index==2:
            temp = int(self.S23.lineEdit_7.text())
        elif index==3:
            temp = int(self.S23.lineEdit_9.text())
        elif index==4:
            temp = int(self.S23.lineEdit_11.text())
        data = [temp & 0xFF, (temp >> 8) & 0xFF, 0, 0, 0, 0, 0, 0]
        self.c.Transmit(0x1880EFF2, data, extern_flag=True, data_len=8)
#row 0 col 1
def IndexTrans(row,col,data,TB):
    row_index = row * 32 + config["Glaoal_Index_alarm"]
    res_data = 0
    res_index = 0
    if col<=20:
        res_index = col-1
        res_data = data

    if col>=21 and col<=29:
        res_index = 20
        b0 = int(TB.item(row, 21).text())
        b1 = int(TB.item(row, 22).text())
        b2 = int(TB.item(row, 23).text())

        b4 = int(TB.item(row, 24).text())
        b5 = int(TB.item(row, 25).text())
        b6 = int(TB.item(row, 26).text())

        b7 = int(TB.item(row, 27).text())
        b8 = int(TB.item(row, 28).text())
        b9 = int(TB.item(row, 29).text())

        res_data = b0+(b1<<1)+(b2<<2)+(b4<<4)+(b5<<5)+(b6<<6)+(b7<<7)+(b8<<8)+(b9<<9)

    if col==30:
        res_index = 21
        res_data = data
    if col==31:
        res_index=22
        res_data = data
    if col==32:
        res_index=23
        res_data = data

    # 高字节表示充电降额，低字节表示放电降额
    if col==33:
        res_index = 24
        res_data = (data<<8)+int(TB.item(row, 38).text())

    if col==34:
        res_index = 25
        res_data = (data<<8)+int(TB.item(row, 39).text())

    if col==35:
        res_index = 26
        res_data = (data<<8)+int(TB.item(row, 40).text())

    if col==36:
        res_index = 27
        res_data = (data<<8)+int(TB.item(row, 41).text())

    if col==37:
        res_index = 28
        res_data = (data<<8)+int(TB.item(row, 42).text())
    #########################################################
    if col==38:
        res_index = 24
        res_data = (int(TB.item(row, 33).text())<<8)+data

    if col==39:
        res_index = 25
        res_data = (int(TB.item(row, 34).text())<<8)+data

    if col==40:
        res_index = 26
        res_data = (int(TB.item(row, 35).text())<<8)+data

    if col==41:
        res_index = 27
        res_data = (int(TB.item(row, 36).text())<<8)+data

    if col==42:
        res_index = 28
        res_data = (int(TB.item(row, 37).text())<<8)+data

    if col>42:
        res_index = 29
        b0 = (int(TB.item(row, 43).text())<<0)
        b1 = (int(TB.item(row, 44).text()) << 1)
        b2 = (int(TB.item(row, 45).text()) << 2)
        b3 = (int(TB.item(row, 46).text()) << 3)
        b4 = (int(TB.item(row, 47).text()) << 4)
        if col==43:
            b0 = data
        if col==44:
            b1 = data
        if col==45:
            b2 = data
        if col==46:
            b3 = data
        if col==47:
            b4 = data
        res_data = b0+(b1<<1)+(b2<<2)+(b3<<3)+(b4<<4)
    return res_index+row_index,res_data






if __name__ == '__main__':
    app = QApplication(sys.argv)
    myshow = Edit()

    myshow.show()
    sys.exit(app.exec())
    #self.S21.change_row_color(2, QColor(255, 255, 0))
