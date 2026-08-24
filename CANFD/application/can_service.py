import re
import time
from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Dict, List

from application.config_loader import resolve_active_cluster_addresses
from application.power_diagnostics import (
    POWER_DIAGNOSTIC_POLL_SEQUENCE,
    POWER_DIAGNOSTIC_SIGNAL_IDS,
    POWER_DIAGNOSTIC_SIGNALS_BY_ID,
)
from domain.models import (
    AlarmParameterDefinition,
    AlarmParameterField,
    AlarmParameterRecord,
    HistoryLogRecord,
    LegacySignalDefinition,
    LegacySignalUpdate,
    PeriodicSignalUpdate,
    PollResult,
    RawFrame,
)


CELL_VOLTAGE_PREFIX = "CELL_VOL_ID_"
CELL_TEMPERATURE_PREFIX = "CELL_TEMP_ID_"
ALARM_STATE_PREFIX = "ALARM_STATE_ID_"
TERMINAL_TEMPERATURE_PREFIX = "BCU_TERMINAL_TEMP_"
BALANCE_TEMPERATURE_PREFIX = "BALANCE_TEMP_ID_"
ALARM_MESSAGE_FRAME_ID = 0x1204EFA0
BALANCE_TEMPERATURE_FRAME_BASES = (0x12C9EF00, 0x12CAEF00)
BALANCE_TEMPERATURE_FIRST_PAGE = 0xC9
BALANCE_TEMPERATURE_VALUES_PER_FRAME = 32
BALANCE_TEMPERATURE_UNIT = "0.1℃"
BMS_SEND_TIME_PF = 0xED
BMS_SEND_TIME_FRAME_MASK = 0x00FFFF00
BMS_SEND_TIME_FRAME_PATTERN = (BMS_SEND_TIME_PF << 16) | 0x0000FF00
CMD_READ_VAR = 0x80
RESP_READ_VAR = 0x81
CMD_WRITE_VAR = 0x82
RESP_WRITE_VAR = 0x83
CMD_READ_LOG = 0x86
RESP_READ_LOG = 0x87
CMD_CTRL_HARDWARE = 0x88
RESP_CTRL_HARDWARE = 0x89
CMD_SET_TIME = 0x90
RESP_SET_TIME = 0x91
CMD_DECODE_SECU = 0xA0
RESP_DECODE_SECU = 0xA1
CTRL_WORK_MODE = 0x01
CTRL_CHNNEL = 0x02
CTRL_PARA_CONFIG = 0x04
CTRL_PARA_CONFIG_RESET_FACTORY = 2
CTRL_PARA_CONFIG_RESET_RUN = 3
CTRL_PARA_CONFIG_RESET_PRODUCT_INFO = 5
CTRL_PARA_CONFIG_CLEAR_HISTORY_LOG = 6
CTRL_PARA_CONFIG_SAVE_ALL_TO_FLASH = 8
HISTORY_LOG_TYPE_ALARM = 1
HISTORY_LOG_TYPE_OTHER = 2
HISTORY_LOG_PAYLOAD_SIZE = 52
HISTORY_LOG_CHUNK_SIZE = 7
HISTORY_LOG_CHUNK_COUNT = 8
VAR_SYS_WORK_MODE = 11
VAR_SYS_RUN_STATUS = 12
VAR_SYS_SOC = 16
VAR_SYS_TIME_YEAR = 0x25E
VAR_SYS_TIME_MONTH = 0x25F
VAR_SYS_TIME_DAY = 0x260
VAR_SYS_TIME_HOUR = 0x261
VAR_SYS_TIME_MINUTE = 0x262
VAR_SYS_TIME_SECOND = 0x263
WORK_MODE_NORMAL = 0
WORK_MODE_GZ_TEST = 1
VAR_SYS_USER_SET_SOC = 445
VAR_SYS_ALLOW_DSCH_60S_CURR = 0x1AD
VAR_SYS_ALLOW_DSCH_60S_POWER = 0x1AE
VAR_SYS_ALLOW_CHRG_60S_CURR = 0x1AF
VAR_SYS_ALLOW_CHRG_60S_POWER = 0x1B0
ID_PAR_SYS_START = 0x90400
ID_PAR_ALARM_START = 0x94900
PAR_ALM_MAX_NUM = 32
PAR_SYS_MODULE_COUNT = ID_PAR_SYS_START + 1
PAR_SYS_AFE_COUNT = ID_PAR_SYS_START + 2
PAR_SYS_OUTPUT_HVIL_FREQ = ID_PAR_SYS_START + 197
PAR_SYS_OUTPUT_HVIL_DUTY_RATIO = ID_PAR_SYS_START + 198
ALARM_PARAMETER_REMOTE_MIN_TIMEOUT_S = 1.2
ALARM_PARAMETER_REMOTE_RETRIES = 2
ALARM_PARAMETER_REMOTE_SETTLE_DELAY_S = 0.005
ALARM_PARAMETER_REMOTE_RECORD_MIN_TIMEOUT_S = 1.8
ALARM_PARAMETER_REMOTE_RECORD_RETRIES = 3
ALARM_PARAMETER_REMOTE_RECORD_SETTLE_DELAY_S = 0.01
ALARM_PARAMETER_LOCAL_BATCH_SIZE = 12
ALARM_PARAMETER_REMOTE_BATCH_SIZE = 4
SECURITY_REQUEST_SEED = bytes((0x02, 0x27, 0x11))
SECURITY_SEND_KEY = bytes((0x06, 0x27, 0x12))
SECURITY_SEED_RESPONSE = bytes((0x06, 0x67, 0x11))
SECURITY_KEY_RESPONSE = bytes((0x02, 0x67, 0x12))
BALANCE_MODULE_COUNT = 4
BALANCE_TEMP_PER_MODULE = 8
BALANCE_BITS_PER_WORD = 16
LECU_UNIFIED_VAR_START = 0x1000
LECU_CELL_MAX_NUM = 104
VAR_LECU_CELL_MAX_NUM = 11
VAR_LECU_UINT_MAX_NUM = 64
LECU_DATA_LENGTH = LECU_CELL_MAX_NUM * VAR_LECU_CELL_MAX_NUM + VAR_LECU_UINT_MAX_NUM
BALANCE_MODULE_STRIDE = LECU_DATA_LENGTH
BALANCE_CELLS_PER_MODULE = LECU_CELL_MAX_NUM
VAR_LECU_UINT_BALANCE_CFG_START = 30
BALANCE_CONTROL_WORD_COUNT = 8
BALANCE_LOCAL_SIGNAL_IDS = tuple(
    LECU_UNIFIED_VAR_START + VAR_LECU_UINT_BALANCE_CFG_START + offset
    for offset in range(BALANCE_CONTROL_WORD_COUNT)
)
REQUEST_GROUP_CONFIG_KEY = "REQUEST_GROUPS"
DEFAULT_REQUEST_GROUP_COUNT = 3
BALANCE_STATE_PREFIXES = (
    "CELL_BALANCE_ID_",
    "CELL_BALANCE_STATE_ID_",
    "CELL_BAL_STA_ID_",
    "BALANCE_STATE_ID_",
    "BALANCE_ID_",
)

INDEX_MONITOR_SIGNAL_DEFINITIONS = (
    {"key": "work_mode", "data_id": VAR_SYS_WORK_MODE, "label": "工作模式", "unit": "", "signed": False},
    {"key": "di1", "data_id": 36, "label": "DI1", "unit": "", "signed": False},
    {"key": "di2", "data_id": 37, "label": "DI2", "unit": "", "signed": False},
    {"key": "di3", "data_id": 38, "label": "DI3", "unit": "", "signed": False},
    {"key": "di4", "data_id": 39, "label": "DI4", "unit": "", "signed": False},
    {"key": "di5", "data_id": 40, "label": "DI5", "unit": "", "signed": False},
    {"key": "di6", "data_id": 41, "label": "DI6", "unit": "", "signed": False},
    {"key": "di7", "data_id": 42, "label": "DI7", "unit": "", "signed": False},
    {"key": "di8", "data_id": 43, "label": "DI8", "unit": "", "signed": False},
    {"key": "di9", "data_id": 44, "label": "DI9", "unit": "", "signed": False},
    {"key": "di10", "data_id": 45, "label": "DI10", "unit": "", "signed": False},
    {"key": "di11", "data_id": 46, "label": "DI11", "unit": "", "signed": False},
    {"key": "di12", "data_id": 47, "label": "DI12", "unit": "", "signed": False},
    {"key": "relay1", "data_id": 48, "label": "HSD1", "unit": "", "signed": False},
    {"key": "relay2", "data_id": 49, "label": "HSD2", "unit": "", "signed": False},
    {"key": "relay3", "data_id": 50, "label": "HSD3", "unit": "", "signed": False},
    {"key": "relay4", "data_id": 51, "label": "HSD4", "unit": "", "signed": False},
    {"key": "relay5", "data_id": 52, "label": "HSD5", "unit": "", "signed": False},
    {"key": "relay6", "data_id": 53, "label": "HSD6", "unit": "", "signed": False},
    {"key": "relay7", "data_id": 54, "label": "HSD7", "unit": "", "signed": False},
    {"key": "relay8", "data_id": 55, "label": "HSD8", "unit": "", "signed": False},
    {"key": "relay9", "data_id": 56, "label": "LSD1", "unit": "", "signed": False},
    {"key": "relay10", "data_id": 57, "label": "LSD2", "unit": "", "signed": False},
    {"key": "rt1", "data_id": 112, "label": "RT01", "unit": "0.1℃", "signed": True},
    {"key": "rt2", "data_id": 113, "label": "RT02", "unit": "0.1℃", "signed": True},
    {"key": "rt3", "data_id": 114, "label": "RT03", "unit": "0.1℃", "signed": True},
    {"key": "rt4", "data_id": 115, "label": "RT04", "unit": "0.1℃", "signed": True},
    {"key": "rt5", "data_id": 116, "label": "RT05", "unit": "0.1℃", "signed": True},
    {"key": "rt6", "data_id": 117, "label": "RT06", "unit": "0.1℃", "signed": True},
    {"key": "rt7", "data_id": 118, "label": "RT07", "unit": "0.1℃", "signed": True},
    {"key": "rt8", "data_id": 119, "label": "RT08", "unit": "0.1℃", "signed": True},
    {"key": "rt9", "data_id": 120, "label": "RT09", "unit": "0.1℃", "signed": True},
    {"key": "rt10", "data_id": 121, "label": "RT10", "unit": "0.1℃", "signed": True},
    {"key": "board_temp1", "data_id": 122, "label": "板温1", "unit": "0.1℃", "signed": True},
    {"key": "board_temp2", "data_id": 123, "label": "板温2", "unit": "0.1℃", "signed": True},
    {"key": "avg_voltage", "data_id": 323, "label": "平均单体电压", "unit": "mV", "signed": False},
    {"key": "avg_temp", "data_id": 324, "label": "平均单体温度", "unit": "0.1℃", "signed": True},
    {"key": "online_lecu_num", "data_id": 325, "label": "在线从板数", "unit": "", "signed": False},
    {"key": "user_set_soc", "data_id": VAR_SYS_USER_SET_SOC, "label": "手动SOC", "unit": "0.1%", "signed": False},
    {
        "key": "hvil_pwm_freq",
        "data_id": PAR_SYS_OUTPUT_HVIL_FREQ,
        "label": "HVIL频率参数",
        "unit": "0.1Hz",
        "signed": False,
    },
    {
        "key": "hvil_pwm_duty",
        "data_id": PAR_SYS_OUTPUT_HVIL_DUTY_RATIO,
        "label": "HVIL占空比参数",
        "unit": "0.1%",
        "signed": False,
    },
)

INDEX_MONITOR_SIGNAL_DEFINITIONS = (
    {"key": "work_mode", "data_id": VAR_SYS_WORK_MODE, "label": "Work mode", "unit": "", "signed": False},
    {"key": "run_status", "data_id": VAR_SYS_RUN_STATUS, "label": "Run status", "unit": "", "signed": False},
    {"key": "system_current", "data_id": 0x0E, "label": "System current", "unit": "0.1A", "signed": True},
    {"key": "hall_current", "data_id": 0x315, "label": "Hall current", "unit": "0.1A", "signed": True},
    {"key": "shunt_current", "data_id": 0x316, "label": "Shunt current", "unit": "0.1A", "signed": True},
    {"key": "battery_voltage", "data_id": 0x5B, "label": "Battery voltage", "unit": "0.1V", "signed": False},
    {"key": "system_voltage", "data_id": 0x0D, "label": "System voltage", "unit": "0.1V", "signed": False},
    {"key": "pack_voltage", "data_id": 0x5C, "label": "Pack voltage", "unit": "0.1V", "signed": False},
    {"key": "soc", "data_id": VAR_SYS_SOC, "label": "SOC", "unit": "0.1%", "signed": False},
    {"key": "display_soc", "data_id": 0x12, "label": "Display SOC", "unit": "0.1%", "signed": False},
    {"key": "soh", "data_id": 0x11, "label": "SOH", "unit": "0.1%", "signed": False},
    {"key": "cell_max_soc", "data_id": 0x1C0, "label": "Cell max SOC", "unit": "0.1%", "signed": False},
    {"key": "cell_min_soc", "data_id": 0x1C1, "label": "Cell min SOC", "unit": "0.1%", "signed": False},
    {"key": "pure_soc", "data_id": 0x1C2, "label": "Pure SOC", "unit": "0.1%", "signed": False},
    {"key": "revise_soc", "data_id": 0x1C3, "label": "Revise SOC", "unit": "0.1%", "signed": False},
    {"key": "revise_soc_temp", "data_id": 0x1C4, "label": "Temp revise SOC", "unit": "0.1%", "signed": False},
    {"key": "cell_min_soc_temp", "data_id": 0x1C5, "label": "Cell min temp SOC", "unit": "0.1%", "signed": False},
    {"key": "cell_max_soc_temp", "data_id": 0x1C6, "label": "Cell max temp SOC", "unit": "0.1%", "signed": False},
    {"key": "fuzzy_soc", "data_id": 0x1C7, "label": "Fuzzy SOC", "unit": "0.1%", "signed": False},
    {"key": "diff_voltage", "data_id": 0x141, "label": "Voltage diff", "unit": "mV", "signed": False},
    {"key": "diff_temp", "data_id": 0x142, "label": "Temperature diff", "unit": "0.1C", "signed": True},
    {"key": "max_cell_voltage", "data_id": 0x148, "label": "Max cell voltage", "unit": "mV", "signed": False},
    {"key": "max_cell_voltage_position", "data_id": 0x149, "label": "Max cell voltage position", "unit": "", "signed": False},
    {"key": "min_cell_voltage", "data_id": 0x14B, "label": "Min cell voltage", "unit": "mV", "signed": False},
    {"key": "min_cell_voltage_position", "data_id": 0x14C, "label": "Min cell voltage position", "unit": "", "signed": False},
    {"key": "max_cell_temp", "data_id": 0x14E, "label": "Max cell temp", "unit": "0.1C", "signed": True},
    {"key": "max_cell_temp_position", "data_id": 0x14F, "label": "Max cell temp position", "unit": "", "signed": False},
    {"key": "min_cell_temp", "data_id": 0x151, "label": "Min cell temp", "unit": "0.1C", "signed": True},
    {"key": "min_cell_temp_position", "data_id": 0x152, "label": "Min cell temp position", "unit": "", "signed": False},
    {"key": "single_charge_kwh", "data_id": 0x1FD, "label": "Single charge energy", "unit": "0.1kWh", "signed": False},
    {"key": "single_discharge_kwh", "data_id": 0x1FE, "label": "Single discharge energy", "unit": "0.1kWh", "signed": False},
    {"key": "remaining_discharge_kwh", "data_id": 0x252, "label": "Remaining discharge energy", "unit": "0.01kWh", "signed": False},
    {"key": "remaining_charge_kwh", "data_id": 0x253, "label": "Remaining charge energy", "unit": "0.01kWh", "signed": False},
    {"key": "total_charge_kwh_low", "data_id": 0x90885, "label": "Total charge energy low", "unit": "0.01kWh", "signed": False},
    {"key": "total_charge_kwh_high", "data_id": 0x90886, "label": "Total charge energy high", "unit": "0.01kWh", "signed": False},
    {"key": "total_discharge_kwh_low", "data_id": 0x90887, "label": "Total discharge energy low", "unit": "0.01kWh", "signed": False},
    {"key": "total_discharge_kwh_high", "data_id": 0x90888, "label": "Total discharge energy high", "unit": "0.01kWh", "signed": False},
    {"key": "module_count", "data_id": PAR_SYS_MODULE_COUNT, "label": "Module count", "unit": "", "signed": False},
    {"key": "afe_count", "data_id": PAR_SYS_AFE_COUNT, "label": "AFE count", "unit": "", "signed": False},
    {"key": "di1", "data_id": 36, "label": "DI1", "unit": "", "signed": False},
    {"key": "di2", "data_id": 37, "label": "DI2", "unit": "", "signed": False},
    {"key": "di3", "data_id": 38, "label": "DI3", "unit": "", "signed": False},
    {"key": "di4", "data_id": 39, "label": "DI4", "unit": "", "signed": False},
    {"key": "di5", "data_id": 40, "label": "DI5", "unit": "", "signed": False},
    {"key": "di6", "data_id": 41, "label": "DI6", "unit": "", "signed": False},
    {"key": "di7", "data_id": 42, "label": "DI7", "unit": "", "signed": False},
    {"key": "di8", "data_id": 43, "label": "DI8", "unit": "", "signed": False},
    {"key": "di9", "data_id": 44, "label": "DI9", "unit": "", "signed": False},
    {"key": "di10", "data_id": 45, "label": "DI10", "unit": "", "signed": False},
    {"key": "di11", "data_id": 46, "label": "DI11", "unit": "", "signed": False},
    {"key": "di12", "data_id": 47, "label": "DI12", "unit": "", "signed": False},
    {"key": "relay1", "data_id": 48, "label": "HSD1", "unit": "", "signed": False},
    {"key": "relay2", "data_id": 49, "label": "HSD2", "unit": "", "signed": False},
    {"key": "relay3", "data_id": 50, "label": "HSD3", "unit": "", "signed": False},
    {"key": "relay4", "data_id": 51, "label": "HSD4", "unit": "", "signed": False},
    {"key": "relay5", "data_id": 52, "label": "HSD5", "unit": "", "signed": False},
    {"key": "relay6", "data_id": 53, "label": "HSD6", "unit": "", "signed": False},
    {"key": "relay7", "data_id": 54, "label": "HSD7", "unit": "", "signed": False},
    {"key": "relay8", "data_id": 55, "label": "HSD8", "unit": "", "signed": False},
    {"key": "relay9", "data_id": 56, "label": "LSD1", "unit": "", "signed": False},
    {"key": "relay10", "data_id": 57, "label": "LSD2", "unit": "", "signed": False},
    {"key": "rt1", "data_id": 112, "label": "RT01", "unit": "0.1C", "signed": True},
    {"key": "rt2", "data_id": 113, "label": "RT02", "unit": "0.1C", "signed": True},
    {"key": "rt3", "data_id": 114, "label": "RT03", "unit": "0.1C", "signed": True},
    {"key": "rt4", "data_id": 115, "label": "RT04", "unit": "0.1C", "signed": True},
    {"key": "rt5", "data_id": 116, "label": "RT05", "unit": "0.1C", "signed": True},
    {"key": "rt6", "data_id": 117, "label": "RT06", "unit": "0.1C", "signed": True},
    {"key": "rt7", "data_id": 118, "label": "RT07", "unit": "0.1C", "signed": True},
    {"key": "rt8", "data_id": 119, "label": "RT08", "unit": "0.1C", "signed": True},
    {"key": "rt9", "data_id": 120, "label": "RT09", "unit": "0.1C", "signed": True},
    {"key": "rt10", "data_id": 121, "label": "RT10", "unit": "0.1C", "signed": True},
    {"key": "board_temp1", "data_id": 122, "label": "Board temp 1", "unit": "0.1C", "signed": True},
    {"key": "board_temp2", "data_id": 123, "label": "Board temp 2", "unit": "0.1C", "signed": True},
    {"key": "avg_voltage", "data_id": 323, "label": "Average voltage", "unit": "mV", "signed": False},
    {"key": "avg_temp", "data_id": 324, "label": "Average temp", "unit": "0.1C", "signed": True},
    {"key": "online_lecu_num", "data_id": 325, "label": "Online LECU", "unit": "", "signed": False},
    {"key": "continuous_discharge_current", "data_id": VAR_SYS_ALLOW_DSCH_60S_CURR, "label": "60S discharge current", "unit": "0.1A", "signed": False},
    {"key": "continuous_discharge_power", "data_id": VAR_SYS_ALLOW_DSCH_60S_POWER, "label": "60S discharge power", "unit": "10W", "signed": False},
    {"key": "continuous_charge_current", "data_id": VAR_SYS_ALLOW_CHRG_60S_CURR, "label": "60S charge current", "unit": "0.1A", "signed": False},
    {"key": "continuous_charge_power", "data_id": VAR_SYS_ALLOW_CHRG_60S_POWER, "label": "60S charge power", "unit": "10W", "signed": False},
    {"key": "user_set_soc", "data_id": VAR_SYS_USER_SET_SOC, "label": "User SOC", "unit": "0.1%", "signed": False},
    {"key": "hvil_pwm_freq", "data_id": PAR_SYS_OUTPUT_HVIL_FREQ, "label": "HVIL freq", "unit": "0.1Hz", "signed": False},
    {"key": "hvil_pwm_duty", "data_id": PAR_SYS_OUTPUT_HVIL_DUTY_RATIO, "label": "HVIL duty", "unit": "0.1%", "signed": False},
)

# Current BMS clock fields exposed by the lower-controller host protocol through
# CMD_READ_VAR/RESP_READ_VAR (0x80/0x81).
INDEX_MONITOR_SIGNAL_DEFINITIONS += (
    {"key": "device_time_year", "data_id": VAR_SYS_TIME_YEAR, "label": "BMS time year", "unit": "", "signed": False},
    {"key": "device_time_month", "data_id": VAR_SYS_TIME_MONTH, "label": "BMS time month", "unit": "", "signed": False},
    {"key": "device_time_day", "data_id": VAR_SYS_TIME_DAY, "label": "BMS time day", "unit": "", "signed": False},
    {"key": "device_time_hour", "data_id": VAR_SYS_TIME_HOUR, "label": "BMS time hour", "unit": "", "signed": False},
    {"key": "device_time_minute", "data_id": VAR_SYS_TIME_MINUTE, "label": "BMS time minute", "unit": "", "signed": False},
    {"key": "device_time_second", "data_id": VAR_SYS_TIME_SECOND, "label": "BMS time second", "unit": "", "signed": False},
)

ALARM_PARAMETER_FIELDS = (
    AlarmParameterField("level1", "一级告警", 0, signed=True, summary=True),
    AlarmParameterField("level2", "二级告警", 1, signed=True, summary=True),
    AlarmParameterField("level3", "三级告警", 2, signed=True, summary=True),
    AlarmParameterField("level4", "四级告警", 3, signed=True, summary=True),
    AlarmParameterField("level5", "五级告警", 4, signed=True, summary=True),
    AlarmParameterField("hysteresis1", "一级回差", 5, summary=True),
    AlarmParameterField("hysteresis2", "二级回差", 6, summary=True),
    AlarmParameterField("hysteresis3", "三级回差", 7, summary=True),
    AlarmParameterField("hysteresis4", "四级回差", 8, summary=True),
    AlarmParameterField("hysteresis5", "五级回差", 9, summary=True),
    AlarmParameterField("alarm_on_delay1", "一级产生延时", 10),
    AlarmParameterField("alarm_on_delay2", "二级产生延时", 11),
    AlarmParameterField("alarm_on_delay3", "三级产生延时", 12),
    AlarmParameterField("alarm_on_delay4", "四级产生延时", 13),
    AlarmParameterField("alarm_on_delay5", "五级产生延时", 14),
    AlarmParameterField("alarm_off_delay1", "一级消除延时", 15),
    AlarmParameterField("alarm_off_delay2", "二级消除延时", 16),
    AlarmParameterField("alarm_off_delay3", "三级消除延时", 17),
    AlarmParameterField("alarm_off_delay4", "四级消除延时", 18),
    AlarmParameterField("alarm_off_delay5", "五级消除延时", 19),
    AlarmParameterField("relay_mask", "继电器关联", 20),
    AlarmParameterField("relay_on_delay1", "一级继电器延时", 21),
    AlarmParameterField("relay_on_delay2", "二级继电器延时", 22),
    AlarmParameterField("relay_on_delay3", "三级继电器延时", 23),
    AlarmParameterField("derate1", "一级降额", 24),
    AlarmParameterField("derate2", "二级降额", 25),
    AlarmParameterField("derate3", "三级降额", 26),
    AlarmParameterField("derate4", "四级降额", 27),
    AlarmParameterField("derate5", "五级降额", 28),
    AlarmParameterField("display_level", "告警使能", 29),
)
ALARM_PARAMETER_FIELDS_BY_KEY = {
    field.key: field
    for field in ALARM_PARAMETER_FIELDS
}
ALARM_PARAMETER_SUMMARY_KEYS = tuple(
    field.key
    for field in ALARM_PARAMETER_FIELDS
    if field.summary
)
ALARM_PARAMETER_NAMES = (
    "单体电压过高",
    "单体电压过低",
    "总电压过高",
    "总电压过低",
    "模组过压",
    "模组欠压",
    "电池簇充电电池单体电压极差",
    "电池簇放电电池单体电压极差",
    "单体压差过大",
    "模组压差过大",
    "充电过流",
    "放电过流",
    "电池单体高温",
    "电池单体低温",
    "充电温度过高",
    "充电温度过低",
    "放电温度过高",
    "放电温度过低",
    "电池簇充电电池单体温度极差",
    "电池簇放电电池单体温度极差",
    "绝缘低",
    "绝缘检测故障",
    "高压箱内连接器温度高",
    "电池组SOC过低",
    "极柱过温",
    "温升过高",
    "BAU通信故障",
    "BMU通讯故障",
    "BMU概要故障",
    "接触器故障",
    "BCU概要故障",
    "熔断器故障",
    "电流传感器故障",
    "断路器断开（隔离空开）",
    "NTC故障",
    "极柱温度传感器故障",
    "高压箱温度传感器故障",
    "单体温度传感器故障",
    "单体电压故障",
    "BCU功能安全告警",
    "BMU自检故障",
    "BCU自检故障",
    "充放电回路异常",
    "簇总压校验差过大",
    "预充故障",
    "断路器故障",
    "电池簇充电电池模块电压极差",
    "电池簇放电电池模块电压极差",
    "高压箱风扇故障",
)


def format_signal_value(value):
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def config_int(runtime_config, key, default):
    value = runtime_config.get(key, default)
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def config_int_list(runtime_config, key, default):
    values = runtime_config.get(key, default)
    return [config_int({key: value}, key, value) for value in values]


def config_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def decode_legacy_value(raw_word, bit_start, bit_length, signed):
    mask = (1 << bit_length) - 1
    unsigned_value = (raw_word >> bit_start) & mask
    if signed:
        sign_bit = 1 << (bit_length - 1)
        if unsigned_value & sign_bit:
            unsigned_value -= 1 << bit_length
    return unsigned_value


def security_seed_to_key(seed):
    cal_data = [0] * 4
    return_key = [0] * 4
    xor_array = (0x66, 0x77, 0x83, 0xE9)

    for index in range(4):
        cal_data[index] = ((seed >> (24 - index * 8)) & 0xFF) ^ xor_array[index]

    return_key[0] = ((cal_data[2] & 0x03) << 6) | ((cal_data[3] & 0xFC) >> 2)
    return_key[1] = ((cal_data[3] & 0x03) << 6) | (cal_data[0] & 0x3F)
    return_key[2] = (cal_data[0] & 0xFC) | ((cal_data[1] & 0xC0) >> 6)
    return_key[3] = (cal_data[1] & 0xFC) | (cal_data[2] & 0x03)

    return (
        (return_key[0] << 24)
        | (return_key[1] << 16)
        | (return_key[2] << 8)
        | return_key[3]
    )


class CanApplicationService:
    def __init__(self, runtime_config, bus_config, driver, legacy_catalog, dbc_runtime, log_manager):
        self.runtime_config = runtime_config
        self.bus_config = bus_config
        self.driver = driver
        self.legacy_catalog = legacy_catalog
        self.dbc_runtime = dbc_runtime
        self.log_manager = log_manager
        self.debug_enabled = bool(runtime_config.get("DEBUG_TRACE", 0))
        self.snapshot_logging_enabled = bool(getattr(log_manager, "enabled", True))
        self.alarm_display_names = self._build_alarm_display_names(
            runtime_config.get("Alarm_name_key", {})
        )
        self.alarm_parameter_fields = list(ALARM_PARAMETER_FIELDS)
        self.alarm_parameter_definitions = self._build_alarm_parameter_definitions()

        self.index_monitor_signal_definitions = list(INDEX_MONITOR_SIGNAL_DEFINITIONS)
        self.index_monitor_definitions_by_id = {}
        self.index_monitor_signal_ids = []
        for definition in self.index_monitor_signal_definitions:
            data_id = int(definition["data_id"])
            self.index_monitor_signal_ids.append(data_id)
            self.index_monitor_definitions_by_id.setdefault(data_id, []).append(definition)
        self.power_diagnostic_signal_ids = set(POWER_DIAGNOSTIC_SIGNAL_IDS)
        self.power_diagnostic_poll_sequence = tuple(POWER_DIAGNOSTIC_POLL_SEQUENCE)
        self._rebuild_runtime_layout()
        self._rebuild_dbc_catalogs()
        self.is_open = False
        self.active_cluster_index = None
        self.active_address = None
        self._reset_runtime_state()
        self._sync_snapshot_log_columns()

    def _rebuild_runtime_layout(self):
        self.rx_batch_size = max(
            32,
            config_int(self.runtime_config, "RX_BATCH_SIZE", 256),
        )
        self.rx_max_frames_per_poll = max(
            self.rx_batch_size,
            config_int(self.runtime_config, "RX_MAX_FRAMES_PER_POLL", 2048),
        )
        self.rx_poll_budget_s = max(
            1,
            config_int(self.runtime_config, "RX_POLL_BUDGET_MS", 8),
        ) / 1000.0
        address_list = resolve_active_cluster_addresses(self.runtime_config)
        self.cluster_index_to_address = {
            cluster_index: address
            for cluster_index, address in enumerate(address_list)
        }
        self.cluster_indices = list(self.cluster_index_to_address)
        self.cluster_addresses = [
            self.cluster_index_to_address[cluster_index]
            for cluster_index in self.cluster_indices
        ]
        self.cluster_address_to_index = {
            address: cluster_index
            for cluster_index, address in self.cluster_index_to_address.items()
        }
        self.response_id_to_cluster = {
            int(f"1881F2{address}", 16): cluster_index
            for cluster_index, address in self.cluster_index_to_address.items()
        }
        self.balance_local_signal_ids = config_int_list(
            self.runtime_config,
            "BALANCE_LOCAL_SIGNAL_IDS",
            BALANCE_LOCAL_SIGNAL_IDS,
        )
        self.balance_module_stride = config_int(
            self.runtime_config,
            "BALANCE_MODULE_STRIDE",
            BALANCE_MODULE_STRIDE,
        )
        default_balance_module_count = int(
            self.runtime_config.get(
                "LECU_NUM",
                self.runtime_config.get("BALANCE_MODULE_COUNT", BALANCE_MODULE_COUNT),
            )
        )
        self.balance_module_count = config_int(
            self.runtime_config,
            "BALANCE_MODULE_COUNT",
            default_balance_module_count,
        )
        self.balance_cells_per_module = config_int(
            self.runtime_config,
            "BALANCE_CELLS_PER_MODULE",
            self.runtime_config.get("CELL_NUM", BALANCE_CELLS_PER_MODULE),
        )
        self.balance_temperature_per_module = config_int(
            self.runtime_config,
            "BALANCE_TEMP_PER_MODULE",
            BALANCE_TEMP_PER_MODULE,
        )
        self.balance_words_per_module = len(self.balance_local_signal_ids)
        self.balance_request_signal_ids = []
        self.balance_signal_layout = {}
        for module_index in range(self.balance_module_count):
            for word_index, local_signal_id in enumerate(self.balance_local_signal_ids):
                signal_id = local_signal_id + module_index * self.balance_module_stride
                self.balance_request_signal_ids.append(signal_id)
                self.balance_signal_layout[signal_id] = (module_index, word_index)
        self._rebuild_request_groups()

    def _rebuild_request_groups(self):
        configured_groups = self.runtime_config.get(REQUEST_GROUP_CONFIG_KEY)
        if configured_groups is None:
            self.request_group_definitions = self._legacy_request_groups()
        else:
            self.request_group_definitions = self._custom_request_groups(
                configured_groups
            )

        self.request_definitions = [
            definition
            for group in self.request_group_definitions
            for definition in group
        ]
        self.request_definitions_by_id = {}
        self.request_query_signal_ids = []
        for definition in self.request_definitions:
            self.request_definitions_by_id.setdefault(
                definition.signal_id,
                [],
            ).append(definition)
            self.request_query_signal_ids.append(definition.signal_id)
        self._rebuild_snapshot_log_definitions()

    def _rebuild_snapshot_log_definitions(self):
        definitions_by_name = {}
        for definition in self.legacy_catalog.definitions:
            if definition.save_to_log:
                definitions_by_name.setdefault(definition.name, definition)

        if self.runtime_config.get(REQUEST_GROUP_CONFIG_KEY) is not None:
            for definition in self.request_definitions:
                definitions_by_name.setdefault(definition.name, definition)

        self.snapshot_log_definitions = list(definitions_by_name.values())
        self.snapshot_log_signal_names = [
            definition.name for definition in self.snapshot_log_definitions
        ]
        self.legacy_log_definitions_by_id = {}
        for definition in self.snapshot_log_definitions:
            self.legacy_log_definitions_by_id.setdefault(
                definition.signal_id,
                [],
            ).append(definition)

    def _sync_snapshot_log_columns(self):
        update_signal_names = getattr(
            self.log_manager,
            "update_legacy_signal_names",
            None,
        )
        if callable(update_signal_names):
            update_signal_names(self.snapshot_log_signal_names)

    def _legacy_request_groups(self):
        max_table_index = DEFAULT_REQUEST_GROUP_COUNT - 1
        for definition in self.legacy_catalog.definitions:
            if definition.table_index >= 0:
                max_table_index = max(max_table_index, int(definition.table_index))
        groups = [[] for _ in range(max_table_index + 1)]
        for definition in sorted(
            self.legacy_catalog.definitions,
            key=lambda item: (item.table_index, item.row_index),
        ):
            if definition.table_index < 0 or definition.row_index < 0:
                continue
            groups[definition.table_index].append(definition)
        return groups

    def _legacy_definition_for_signal(self, signal_id):
        matches = self.legacy_catalog.get_definitions(signal_id)
        if matches:
            return matches[0]
        return None

    def _custom_request_groups(self, configured_groups):
        if not isinstance(configured_groups, list):
            return self._legacy_request_groups()

        groups = []
        group_count = max(DEFAULT_REQUEST_GROUP_COUNT, len(configured_groups))
        for table_index in range(group_count):
            raw_group = (
                configured_groups[table_index]
                if table_index < len(configured_groups)
                else []
            )
            if not isinstance(raw_group, list):
                raw_group = []
            group_definitions = []
            for row_index, raw_entry in enumerate(raw_group):
                definition = self._custom_request_definition(
                    raw_entry,
                    table_index,
                    row_index,
                )
                if definition is not None:
                    group_definitions.append(definition)
            groups.append(group_definitions)
        return groups

    def _custom_request_definition(self, raw_entry, table_index, row_index):
        if raw_entry is None or raw_entry == "":
            return None
        if isinstance(raw_entry, dict):
            raw_signal_id = raw_entry.get(
                "index",
                raw_entry.get("signal_id", raw_entry.get("data_id")),
            )
        else:
            raw_signal_id = raw_entry
            raw_entry = {}
        try:
            signal_id = config_int({"index": raw_signal_id}, "index", raw_signal_id)
        except (TypeError, ValueError):
            return None

        legacy_definition = self._legacy_definition_for_signal(signal_id)
        fallback_name = (
            legacy_definition.name
            if legacy_definition is not None
            else f"索引 0x{signal_id:X}"
        )
        fallback_unit = legacy_definition.unit if legacy_definition is not None else ""
        fallback_signed = (
            legacy_definition.signed if legacy_definition is not None else False
        )
        return LegacySignalDefinition(
            signal_id=signal_id,
            name=str(raw_entry.get("name") or fallback_name),
            unit=str(raw_entry.get("unit") or fallback_unit),
            table_index=int(table_index),
            row_index=int(row_index),
            bit_start=config_int(raw_entry, "bit_start", 0),
            bit_length=config_int(raw_entry, "bit_length", 16),
            signed=config_bool(raw_entry.get("signed"), fallback_signed),
            save_to_log=config_bool(raw_entry.get("save_to_log"), False),
        )

    def open(self):
        self.reopen()

    def reopen(self, bus_config=None):
        if bus_config is not None:
            self.bus_config = bus_config

        self.driver.close()
        self.is_open = False
        self._reset_runtime_state()

        try:
            self.driver.open(self.bus_config)
        except Exception:
            self.driver.close()
            raise

        self.is_open = True
        return self.bus_config

    def update_bus_config(self, **kwargs):
        self.bus_config = replace(self.bus_config, **kwargs)
        return self.bus_config

    def update_runtime_config(self, updates):
        updates = dict(updates)
        previous_active_cluster = self.active_cluster_index
        self.runtime_config.update(updates)
        self._rebuild_runtime_layout()
        self._rebuild_dbc_catalogs()
        self._reset_runtime_state()

        request_groups_only = set(updates) == {REQUEST_GROUP_CONFIG_KEY}
        update_signal_names = getattr(
            self.log_manager,
            "update_legacy_signal_names",
            None,
        )
        update_log_layout = getattr(self.log_manager, "update_layout", None)
        if request_groups_only and callable(update_signal_names):
            update_signal_names(self.snapshot_log_signal_names)
        elif callable(update_log_layout):
            update_log_layout(
                cluster_indices=self.cluster_indices,
                cluster_addresses=self.cluster_addresses,
                legacy_signal_names=self.snapshot_log_signal_names,
                voltage_count=int(self.runtime_config.get("CELL_NUM", 0)),
                temperature_count=int(self.runtime_config.get("CELL_Tem_NUM", 0)),
                balance_module_count=self.balance_module_count,
                balance_cells_per_module=self.balance_cells_per_module,
                balance_temperature_per_module=self.balance_temperature_per_module,
            )

        if previous_active_cluster in self.cluster_index_to_address:
            self.set_active_cluster(previous_active_cluster)
        else:
            self.set_active_cluster(None)
        return self.runtime_config

    def close(self):
        if self.is_open:
            self.driver.close()
            self.is_open = False
        close_logger = getattr(self.log_manager, "close", None)
        if close_logger is not None:
            close_logger()

    def get_dbc_catalog(self, address):
        return list(self.dbc_catalogs.get(address, []))

    def get_request_group_definitions(self):
        return [
            [
                {
                    "index": definition.signal_id,
                    "name": definition.name,
                    "unit": definition.unit,
                    "signed": definition.signed,
                    "bit_start": definition.bit_start,
                    "bit_length": definition.bit_length,
                    "table_index": definition.table_index,
                    "row_index": definition.row_index,
                }
                for definition in group
            ]
            for group in self.request_group_definitions
        ]

    def set_dbc_runtime(self, dbc_runtime):
        self.dbc_runtime = dbc_runtime
        self._rebuild_dbc_catalogs()
        self._clear_periodic_decode_caches()
        return self.dbc_runtime

    def set_active_cluster(self, cluster_index):
        if cluster_index is None:
            self.active_cluster_index = None
            self.active_address = None
        else:
            cluster_index = int(cluster_index)
            if cluster_index not in self.cluster_index_to_address:
                raise RuntimeError(f"Invalid cluster index: {cluster_index}")
            self.active_cluster_index = cluster_index
            self.active_address = self.cluster_index_to_address[cluster_index]
        self.pending_can_frames.clear()
        self.pending_canfd_frames.clear()

    def _is_active_cluster(self, cluster_index):
        return self.active_cluster_index is None or int(cluster_index) == self.active_cluster_index

    def _is_active_address(self, address):
        return self.active_address is None or str(address) == self.active_address

    @staticmethod
    def _is_downstream_cluster(cluster_index):
        return int(cluster_index) > 0

    def poll(self):
        result = PollResult()
        if not self.is_open:
            return result

        started_at = time.perf_counter()
        deadline = started_at + self.rx_poll_budget_s
        remaining = self.rx_max_frames_per_poll
        while remaining > 0:
            batch_size = min(self.rx_batch_size, remaining)
            can_frames = self._receive_pending_can_frames(max_count=batch_size)
            remaining -= self._handle_frame_batch(
                can_frames,
                "rx_can",
                result,
            )

            if remaining <= 0:
                break
            batch_size = min(self.rx_batch_size, remaining)
            canfd_frames = self._receive_pending_canfd_frames(max_count=batch_size)
            remaining -= self._handle_frame_batch(
                canfd_frames,
                "rx_canfd",
                result,
            )

            if not can_frames and not canfd_frames:
                break
            if time.perf_counter() >= deadline:
                break

        self._coalesce_poll_updates(result)
        result.poll_elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return result

    def _handle_frame_batch(self, frames, frame_kind, result):
        result.received_frame_count += len(frames)
        for frame in frames:
            handled = self._handle_frame(frame, frame_kind, result)
            self._record_rx_activity(frame, handled)
            if handled:
                result.had_rx_frame = True
                result.handled_frame_count += 1
        return len(frames)

    def _record_rx_activity(self, frame, handled):
        now_monotonic = time.monotonic()
        now_text = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.rx_frame_count += 1
        self.last_rx_monotonic = now_monotonic
        self.last_rx_time_text = now_text
        self.last_rx_frame_id = int(frame.frame_id)
        if handled:
            self.rx_handled_frame_count += 1

        address = f"{int(frame.frame_id) & 0xFF:02X}"
        cluster_index = self.cluster_address_to_index.get(address)
        if cluster_index is None:
            return
        self.rx_frame_count_by_cluster[cluster_index] += 1
        self.last_rx_monotonic_by_cluster[cluster_index] = now_monotonic
        self.last_rx_time_text_by_cluster[cluster_index] = now_text
        self.last_rx_frame_id_by_cluster[cluster_index] = int(frame.frame_id)
        if handled:
            self.rx_handled_frame_count_by_cluster[cluster_index] += 1

    def _record_tx_activity(self, cluster_index, result):
        cluster_index = int(cluster_index)
        self.tx_attempt_count += 1
        if cluster_index in self.tx_attempt_count_by_cluster:
            self.tx_attempt_count_by_cluster[cluster_index] += 1
        if int(result) <= 0:
            self.tx_failure_count += 1
            if cluster_index in self.tx_failure_count_by_cluster:
                self.tx_failure_count_by_cluster[cluster_index] += 1
            return

        now_monotonic = time.monotonic()
        now_text = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.tx_frame_count += 1
        self.last_tx_monotonic = now_monotonic
        self.last_tx_time_text = now_text
        if cluster_index in self.tx_frame_count_by_cluster:
            self.tx_frame_count_by_cluster[cluster_index] += 1
            self.last_tx_monotonic_by_cluster[cluster_index] = now_monotonic
            self.last_tx_time_text_by_cluster[cluster_index] = now_text

    def get_bus_activity_snapshot(self, cluster_index=None):
        now_monotonic = time.monotonic()
        if cluster_index is None:
            tx_count = self.tx_frame_count
            tx_attempt_count = self.tx_attempt_count
            tx_failure_count = self.tx_failure_count
            rx_count = self.rx_frame_count
            rx_handled_count = self.rx_handled_frame_count
            last_tx_monotonic = self.last_tx_monotonic
            last_rx_monotonic = self.last_rx_monotonic
            last_tx_time_text = self.last_tx_time_text
            last_rx_time_text = self.last_rx_time_text
            last_rx_frame_id = self.last_rx_frame_id
        else:
            cluster_index = int(cluster_index)
            tx_count = self.tx_frame_count_by_cluster.get(cluster_index, 0)
            tx_attempt_count = self.tx_attempt_count_by_cluster.get(cluster_index, 0)
            tx_failure_count = self.tx_failure_count_by_cluster.get(cluster_index, 0)
            rx_count = self.rx_frame_count_by_cluster.get(cluster_index, 0)
            rx_handled_count = self.rx_handled_frame_count_by_cluster.get(
                cluster_index,
                0,
            )
            last_tx_monotonic = self.last_tx_monotonic_by_cluster.get(cluster_index)
            last_rx_monotonic = self.last_rx_monotonic_by_cluster.get(cluster_index)
            last_tx_time_text = self.last_tx_time_text_by_cluster.get(cluster_index, "")
            last_rx_time_text = self.last_rx_time_text_by_cluster.get(cluster_index, "")
            last_rx_frame_id = self.last_rx_frame_id_by_cluster.get(cluster_index)

        return {
            "is_open": bool(self.is_open),
            "cluster_index": cluster_index,
            "tx_count": tx_count,
            "tx_attempt_count": tx_attempt_count,
            "tx_failure_count": tx_failure_count,
            "rx_count": rx_count,
            "rx_handled_count": rx_handled_count,
            "last_tx_time": last_tx_time_text,
            "last_rx_time": last_rx_time_text,
            "last_tx_age_s": (
                None
                if last_tx_monotonic is None
                else max(now_monotonic - last_tx_monotonic, 0.0)
            ),
            "last_rx_age_s": (
                None
                if last_rx_monotonic is None
                else max(now_monotonic - last_rx_monotonic, 0.0)
            ),
            "last_rx_frame_id": last_rx_frame_id,
        }

    @staticmethod
    def _coalesce_poll_updates(result):
        result.update_count_before_coalesce = (
            len(result.legacy_updates) + len(result.periodic_updates)
        )
        if len(result.legacy_updates) > 1:
            latest_legacy_updates = {}
            for update in result.legacy_updates:
                key = (
                    update.cluster_index,
                    update.signal_id,
                    update.table_index,
                    update.row_index,
                    update.signal_name,
                )
                latest_legacy_updates[key] = update
            result.legacy_updates = list(latest_legacy_updates.values())

        if len(result.periodic_updates) > 1:
            latest_periodic_updates = {}
            for update in result.periodic_updates:
                latest_periodic_updates[(update.address, update.row_key)] = update
            result.periodic_updates = list(latest_periodic_updates.values())

        if len(result.balance_updates) > 1:
            result.balance_updates = list(dict.fromkeys(result.balance_updates))

    def _handle_frame(self, frame, frame_kind, result):
        balance_update = self._decode_balance_response(frame)
        legacy_updates = self._decode_legacy_response(frame, frame_kind)
        if balance_update is not None or legacy_updates:
            extra_fields = []
            if balance_update is not None:
                address, signal_id = balance_update
                extra_fields.append(f"addr={address}")
                extra_fields.append(f"balance_signal=0x{signal_id:04X}")
                if address not in result.balance_updates:
                    result.balance_updates.append(address)
            if legacy_updates:
                extra_fields.append(f"legacy_updates={len(legacy_updates)}")
            self.log_manager.log_rx(frame_kind, frame, extra_fields)
            result.legacy_updates.extend(legacy_updates)
            return True

        device_time_update = self._decode_device_time_frame(frame, frame_kind)
        if device_time_update is not None:
            self.log_manager.log_rx(
                frame_kind,
                frame,
                [
                    f"cluster={device_time_update.cluster_index}",
                    "protocol=bms_send_time",
                    f"device_time={device_time_update.value}",
                ],
            )
            result.legacy_updates.append(device_time_update)
            return True

        if (
            self.active_address is not None
            and f"{int(frame.frame_id) & 0xFF:02X}" != self.active_address
        ):
            return False

        decoded = self.dbc_runtime.decode_frame(frame.frame_id, frame.data) if self.dbc_runtime else None
        if decoded is None:
            balance_temperature_update = self._decode_balance_temperature_frame(
                frame,
                frame_kind,
            )
            if balance_temperature_update is not None:
                address, updates = balance_temperature_update
                result.periodic_updates.extend(updates)
                result.periodic_status[address] = (
                    f"地址 {address} 已更新，最近报文 "
                    f"BCU{frame.frame_id:08X}，时间 "
                    f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}"
                )
                return True
            return False
        if not self._is_active_address(decoded["address"]):
            return False
        extra_fields = [
            f"addr={decoded['address']}",
            f"message={decoded['message_name']}",
        ]
        self.log_manager.log_rx(frame_kind, frame, extra_fields)
        self.log_manager.log_dbc(frame_kind, frame, decoded)

        address = decoded["address"]
        if address not in self.dbc_catalogs:
            return False

        for signal in decoded["signals"]:
            update = PeriodicSignalUpdate(
                address=address,
                row_key=signal["row_key"],
                message_name=signal["message_name"],
                signal_name=signal["signal_name"],
                value=format_signal_value(signal["value"]),
                unit=signal["unit"],
            )
            result.periodic_updates.append(update)
            self._cache_periodic_signal(
                address,
                decoded["frame_id"],
                signal["signal_name"],
                signal["value"],
            )

        result.periodic_status[address] = (
            f"地址 {address} 已更新，最近报文 {decoded['message_name']}，时间 "
            f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}"
        )
        return True

    def _decode_legacy_response(self, frame, source_kind):
        cluster_index = self.response_id_to_cluster.get(frame.frame_id)
        if cluster_index is None or frame.data_len < 6:
            return []
        if not self._is_active_cluster(cluster_index):
            return []

        signal_id = int.from_bytes(frame.data[:4], byteorder="little", signed=False)
        if signal_id in self.balance_signal_layout:
            return []
        definitions = self.request_definitions_by_id.get(signal_id, [])
        log_definitions = self.legacy_log_definitions_by_id.get(signal_id, [])
        monitor_definitions = self.index_monitor_definitions_by_id.get(signal_id, [])
        diagnostic_signal = (
            signal_id in self.power_diagnostic_signal_ids
            and (frame.data_len < 7 or frame.data[6] != 0)
        )
        if (
            not definitions
            and not log_definitions
            and not monitor_definitions
            and not diagnostic_signal
        ):
            self._debug_print(
                f"legacy_unmapped,source={source_kind},cluster={cluster_index},signal_id=0x{signal_id:08X}"
            )
            return []

        raw_word = frame.data[4] | (frame.data[5] << 8)
        self.legacy_request_raw_words[cluster_index][signal_id] = raw_word
        self._update_legacy_log_state(cluster_index, log_definitions, raw_word)
        if diagnostic_signal:
            self.power_diagnostic_raw_values[cluster_index][signal_id] = raw_word
        updates = []
        for definition in definitions:
            value = decode_legacy_value(
                raw_word,
                definition.bit_start,
                definition.bit_length,
                definition.signed,
            )
            value_text = str(value)
            updates.append(
                LegacySignalUpdate(
                    cluster_index=cluster_index,
                    signal_id=signal_id,
                    signal_name=definition.name,
                    value=value_text,
                    unit=definition.unit,
                    table_index=definition.table_index,
                    row_index=definition.row_index,
                    source_kind=source_kind,
                )
            )
            self.legacy_request_raw_values[cluster_index][definition.name] = value
            self._debug_print(
                f"legacy_match,source={source_kind},cluster={cluster_index},"
                f"signal_id=0x{signal_id:08X},signal={definition.name},value={value_text}"
            )

        if diagnostic_signal:
            diagnostic_definition = POWER_DIAGNOSTIC_SIGNALS_BY_ID[signal_id]
            updates.append(
                LegacySignalUpdate(
                    cluster_index=cluster_index,
                    signal_id=signal_id,
                    signal_name=diagnostic_definition.key,
                    value=str(raw_word),
                    unit=diagnostic_definition.unit,
                    table_index=-1,
                    row_index=-1,
                    source_kind=source_kind,
                )
            )

        if monitor_definitions and frame.data_len >= 7 and frame.data[6] == 0:
            return updates

        for definition in monitor_definitions:
            value = decode_legacy_value(
                raw_word,
                0,
                16,
                definition.get("signed", False),
            )
            value_text = str(value)
            self.index_monitor_values[cluster_index][definition["key"]] = value
            if definition["key"] == "device_time_second":
                self._update_device_time_anchor_from_components(cluster_index)
            updates.append(
                LegacySignalUpdate(
                    cluster_index=cluster_index,
                    signal_id=signal_id,
                    signal_name=definition["label"],
                    value=value_text,
                    unit=definition["unit"],
                    table_index=-1,
                    row_index=-1,
                    source_kind=source_kind,
                )
            )
            self._debug_print(
                f"monitor_match,source={source_kind},cluster={cluster_index},"
                f"signal_id=0x{signal_id:08X},signal={definition['key']},value={value_text}"
            )
        return updates

    def _decode_device_time_frame(self, frame, source_kind):
        if (
            not frame.extern_flag
            or frame.data_len < 6
            or (int(frame.frame_id) & BMS_SEND_TIME_FRAME_MASK)
            != BMS_SEND_TIME_FRAME_PATTERN
        ):
            return None

        address = f"{int(frame.frame_id) & 0xFF:02X}"
        cluster_index = self.cluster_address_to_index.get(address)
        if cluster_index is None or not self._is_active_cluster(cluster_index):
            return None

        parts = (
            2000 + int(frame.data[0]),
            int(frame.data[1]),
            int(frame.data[2]),
            int(frame.data[3]),
            int(frame.data[4]),
            int(frame.data[5]),
        )
        try:
            device_time = datetime(*parts)
        except ValueError:
            return None

        values = self.index_monitor_values[cluster_index]
        for key, value in zip(
            (
                "device_time_year",
                "device_time_month",
                "device_time_day",
                "device_time_hour",
                "device_time_minute",
                "device_time_second",
            ),
            parts,
        ):
            values[key] = value

        time_text = device_time.strftime("%Y-%m-%d %H:%M:%S")
        self._set_device_time_anchor(cluster_index, device_time)
        return LegacySignalUpdate(
            cluster_index=cluster_index,
            signal_id=BMS_SEND_TIME_PF,
            signal_name="下位机系统时间",
            value=time_text,
            unit="",
            table_index=-1,
            row_index=-1,
            source_kind=source_kind,
        )

    def _update_legacy_log_state(self, cluster_index, definitions, raw_word):
        if not definitions:
            return False

        signal_state = self.legacy_signal_state[cluster_index]
        for definition in definitions:
            value = decode_legacy_value(
                raw_word,
                definition.bit_start,
                definition.bit_length,
                definition.signed,
            )
            signal_state[definition.name] = str(value)
        self.legacy_signal_dirty[cluster_index] = True
        return True

    def _decode_balance_response(self, frame):
        cluster_index = self.response_id_to_cluster.get(frame.frame_id)
        if cluster_index is None or frame.data_len < 6:
            return None
        if not self._is_active_cluster(cluster_index):
            return None

        signal_id = int.from_bytes(frame.data[:4], byteorder="little", signed=False)
        layout = self.balance_signal_layout.get(signal_id)
        if layout is None:
            return None

        module_index, word_index = layout
        address = self.cluster_index_to_address[cluster_index]
        raw_word = frame.data[4] | (frame.data[5] << 8)

        for bit_index in range(16):
            cell_offset = word_index * 16 + bit_index
            if cell_offset >= self.balance_cells_per_module:
                break
            absolute_index = module_index * self.balance_cells_per_module + cell_offset
            self.legacy_balance_values[address][absolute_index] = (
                1 if raw_word & (1 << bit_index) else 0
            )
        self.legacy_balance_dirty[address] = True

        return address, signal_id

    def _decode_balance_temperature_frame(self, frame, source_kind):
        frame_base = int(frame.frame_id) & 0xFFFFFF00
        if frame_base not in BALANCE_TEMPERATURE_FRAME_BASES:
            return None

        address = f"{int(frame.frame_id) & 0xFF:02X}"
        if address not in self.periodic_balance_temperature_values:
            return None
        if not self._is_active_address(address):
            return None

        page_index = ((int(frame.frame_id) >> 16) & 0xFF) - BALANCE_TEMPERATURE_FIRST_PAGE
        if page_index < 0:
            return None

        start_index = page_index * BALANCE_TEMPERATURE_VALUES_PER_FRAME
        max_count = self.balance_module_count * self.balance_temperature_per_module
        if max_count <= 0 or start_index >= max_count:
            return None

        value_count = min(
            BALANCE_TEMPERATURE_VALUES_PER_FRAME,
            frame.data_len // 2,
            max_count - start_index,
        )
        if value_count <= 0:
            return None

        updates = []
        self.log_manager.log_rx(
            source_kind,
            frame,
            [
                f"addr={address}",
                "message=balance_temperature",
                f"count={value_count}",
            ],
        )
        for offset in range(value_count):
            absolute_index = start_index + offset
            raw_value = int.from_bytes(
                frame.data[offset * 2 : offset * 2 + 2],
                byteorder="little",
                signed=True,
            )
            value = raw_value * 0.1
            if value.is_integer():
                value = int(value)
            self.periodic_balance_temperature_values[address][absolute_index] = value
            self.periodic_balance_temperature_dirty[address] = True
            updates.append(
                PeriodicSignalUpdate(
                    address=address,
                    row_key=f"BALANCE_TEMP.{address}.{absolute_index + 1:03d}",
                    message_name=f"BCU{frame.frame_id:08X}",
                    signal_name=f"BALANCE_TEMP_ID_{absolute_index + 1:03d}",
                    value=format_signal_value(value),
                    unit=BALANCE_TEMPERATURE_UNIT,
                )
            )
        return address, updates

    def _cache_periodic_signal(self, address, frame_id, signal_name, value):
        if signal_name.startswith(CELL_VOLTAGE_PREFIX):
            index = int(signal_name[len(CELL_VOLTAGE_PREFIX) :])
            self.periodic_voltage_values[address][index] = value
            self.periodic_voltage_dirty[address] = True
            return
        if signal_name.startswith(CELL_TEMPERATURE_PREFIX):
            index = int(signal_name[len(CELL_TEMPERATURE_PREFIX) :])
            self.periodic_temperature_values[address][index] = value
            self.periodic_temperature_dirty[address] = True
            return
        if signal_name.startswith(BALANCE_TEMPERATURE_PREFIX):
            index = int(signal_name[len(BALANCE_TEMPERATURE_PREFIX) :]) - 1
            if index >= 0:
                self.periodic_balance_temperature_values[address][index] = value
                self.periodic_balance_temperature_dirty[address] = True
            return
        for prefix in BALANCE_STATE_PREFIXES:
            if signal_name.startswith(prefix):
                label = signal_name[len(prefix) :]
                self.periodic_balance_values[address][label] = value
                return
        if frame_id == ALARM_MESSAGE_FRAME_ID and signal_name.startswith(ALARM_STATE_PREFIX):
            label = signal_name[len(ALARM_STATE_PREFIX) :]
            self.periodic_alarm_values[address][label] = value
            return
        if signal_name.startswith(TERMINAL_TEMPERATURE_PREFIX):
            label = signal_name[len(TERMINAL_TEMPERATURE_PREFIX) :]
            if re.fullmatch(r"\d+_\d+", label):
                self.periodic_terminal_temperature_values[address][label] = value

    def get_periodic_voltage_values(self, address):
        return self._ordered_values(self.periodic_voltage_values[address])

    def get_periodic_temperature_values(self, address):
        return self._ordered_values(self.periodic_temperature_values[address])

    def get_periodic_balance_temperature_values(self, address):
        values = self.periodic_balance_temperature_values.get(address)
        if not values:
            return []
        max_count = self.balance_module_count * self.balance_temperature_per_module
        ordered_values = [
            values.get(index)
            for index in range(max_count)
        ]
        if not any(value is not None for value in ordered_values):
            return []
        return ordered_values


    def get_periodic_balance_state_values(self, address):
        return self._ordered_named_values(self.periodic_balance_values[address])

    def get_legacy_balance_state_values(self, address):
        values = self.legacy_balance_values.get(address)
        if not values or not any(value is not None for value in values):
            return []

        items = []
        for module_index in range(self.balance_module_count):
            for cell_index in range(self.balance_cells_per_module):
                absolute_index = module_index * self.balance_cells_per_module + cell_index
                items.append(
                    (
                        f"M{module_index + 1}-{cell_index + 1:03d}",
                        values[absolute_index],
                    )
                )
        return items

    def _balance_control_data_id(self, module_index, cell_index):
        module_index = int(module_index)
        cell_index = int(cell_index)
        if module_index < 0 or module_index >= self.balance_module_count:
            raise RuntimeError(f"Invalid balance module index: {module_index}")
        if cell_index < 0 or cell_index >= self.balance_cells_per_module:
            raise RuntimeError(f"Invalid balance cell index: {cell_index}")
        word_index = cell_index // BALANCE_BITS_PER_WORD
        if word_index >= self.balance_words_per_module:
            raise RuntimeError(f"Balance cell index is outside configured word map: {cell_index}")
        bit_index = cell_index % BALANCE_BITS_PER_WORD
        data_id = (
            self.balance_local_signal_ids[word_index]
            + module_index * self.balance_module_stride
        )
        return data_id, word_index, bit_index

    def set_balance_cell_state(
        self,
        cluster_index,
        module_index,
        cell_index,
        enabled,
        timeout_s=1.0,
    ):
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        data_id, word_index, bit_index = self._balance_control_data_id(
            module_index,
            cell_index,
        )
        address = self.cluster_index_to_address[int(cluster_index)]
        control_words = self.balance_control_words[address]
        if data_id in control_words:
            current_word = control_words[data_id]
        else:
            current_word = self.read_data_u16(
                cluster_index,
                data_id,
                timeout_s=timeout_s,
            )
        bit_mask = 1 << bit_index
        if enabled:
            next_word = int(current_word) | bit_mask
        else:
            next_word = int(current_word) & (~bit_mask & 0xFFFF)
        self.write_data_u16(
            cluster_index,
            data_id,
            next_word,
            timeout_s=timeout_s,
        )
        control_words[data_id] = next_word
        return next_word

    def get_periodic_alarm_state_values(self, address):
        if not self.periodic_alarm_values[address]:
            return []
        return [
            (
                self._format_alarm_display_label(label),
                self.periodic_alarm_values[address][label],
            )
            for label in sorted(
                self.periodic_alarm_values[address],
                key=CanApplicationService._named_value_sort_key,
            )
        ]

    def get_periodic_terminal_temperature_values(self, address):
        return self._ordered_named_values(self.periodic_terminal_temperature_values[address])

    @staticmethod
    def _ordered_values(value_map):
        if not value_map:
            return []
        ordered_values = [None] * max(value_map)
        for index, value in value_map.items():
            ordered_values[index - 1] = value
        return ordered_values

    @staticmethod
    def _ordered_named_values(value_map):
        if not value_map:
            return []
        return [
            (label, value_map[label])
            for label in sorted(value_map, key=CanApplicationService._named_value_sort_key)
        ]

    @staticmethod
    def _named_value_sort_key(label):
        numeric_groups = [int(group) for group in re.findall(r"\d+", str(label))]
        if numeric_groups:
            return tuple(numeric_groups)
        return (str(label),)

    @classmethod
    def _build_alarm_display_names(cls, alarm_name_key):
        if not isinstance(alarm_name_key, dict):
            return {}

        display_names = {}
        for raw_key, raw_value in alarm_name_key.items():
            normalized_key = cls._normalize_alarm_label(raw_key)
            if not normalized_key:
                continue

            if isinstance(raw_value, dict):
                field_name = (
                    raw_value.get("field")
                    or raw_value.get("name")
                    or raw_value.get("label")
                )
            elif isinstance(raw_value, str):
                field_name = raw_value
            else:
                field_name = None

            if field_name:
                display_names[normalized_key] = str(field_name).strip()
        return display_names

    def _build_alarm_parameter_definitions(self):
        definitions = []
        for alarm_id in range(64):
            code = f"{alarm_id + 1:03d}"
            if alarm_id < len(ALARM_PARAMETER_NAMES):
                name = ALARM_PARAMETER_NAMES[alarm_id]
            elif code in self.alarm_display_names:
                name = self.alarm_display_names[code]
            elif alarm_id >= 46:
                name = f"预留告警{code}"
            else:
                name = f"告警{code}"
            definitions.append(
                AlarmParameterDefinition(
                    alarm_id=alarm_id,
                    code=code,
                    name=name,
                )
            )
        return definitions

    @staticmethod
    def _normalize_alarm_label(label):
        numeric_groups = re.findall(r"\d+", str(label))
        if not numeric_groups:
            return ""
        return f"{int(numeric_groups[-1]):03d}"

    def _format_alarm_display_label(self, label):
        normalized_label = self._normalize_alarm_label(label)
        field_name = self.alarm_display_names.get(normalized_label)
        if field_name:
            return f"{normalized_label} {field_name}"
        return normalized_label or str(label)

    def _get_alarm_parameter_definition(self, alarm_id):
        alarm_id = int(alarm_id)
        if alarm_id < 0 or alarm_id >= len(self.alarm_parameter_definitions):
            raise RuntimeError(f"Invalid alarm id: {alarm_id}")
        return self.alarm_parameter_definitions[alarm_id]

    @staticmethod
    def _alarm_parameter_data_id(alarm_id, field_index):
        return ID_PAR_ALARM_START + int(alarm_id) * PAR_ALM_MAX_NUM + int(field_index)

    @staticmethod
    def _decode_signed_u16(value):
        value = int(value) & 0xFFFF
        if value & 0x8000:
            return value - 0x10000
        return value

    @staticmethod
    def _decode_alarm_parameter_value(field, raw_value):
        if field.signed:
            return CanApplicationService._decode_signed_u16(raw_value)
        return int(raw_value)

    @staticmethod
    def _encode_alarm_parameter_value(field, value):
        value = int(value)
        if field.signed:
            return value & 0xFFFF
        return value & 0xFFFF

    def _cluster_address_int(self, cluster_index):
        return int(self.cluster_index_to_address[cluster_index], 16)

    def _build_request_frame_id(self, command_pf, cluster_index):
        return 0x180000F2 | (int(command_pf) << 16) | (self._cluster_address_int(cluster_index) << 8)

    def _build_response_frame_id(self, response_pf, cluster_index):
        return 0x18000000 | (int(response_pf) << 16) | (0xF2 << 8) | self._cluster_address_int(cluster_index)

    def _send_diag_request(self, frame_kind, cluster_index, command_pf, payload):
        frame = RawFrame(
            frame_id=self._build_request_frame_id(command_pf, cluster_index),
            data=bytes(payload[:8]).ljust(8, b"\x00"),
            is_fd=False,
            extern_flag=True,
            remote_flag=False,
        )
        result = self.driver.send_can(frame)
        self.log_manager.log_tx(frame_kind, cluster_index, frame, result)
        self._record_tx_activity(cluster_index, result)
        return result

    def _drain_queued_rx_frames(self):
        result = PollResult()
        while self.pending_can_frames:
            frame = self.pending_can_frames.popleft()
            handled = self._handle_frame(frame, "rx_can", result)
            self._record_rx_activity(frame, handled)
        while self.pending_canfd_frames:
            frame = self.pending_canfd_frames.popleft()
            handled = self._handle_frame(frame, "rx_canfd", result)
            self._record_rx_activity(frame, handled)

    def _receive_can_now(self, max_count=200, timeout_ms=0):
        try:
            return self.driver.receive_can(max_count=max_count, timeout_ms=timeout_ms)
        except TypeError:
            return self.driver.receive_can(max_count=max_count)

    def _receive_canfd_now(self, max_count=200, timeout_ms=0):
        try:
            return self.driver.receive_canfd(max_count=max_count, timeout_ms=timeout_ms)
        except TypeError:
            return self.driver.receive_canfd(max_count=max_count)

    def flush_rx_backlog(self, max_rounds=20, max_count=200):
        self.pending_can_frames.clear()
        self.pending_canfd_frames.clear()
        discarded = 0
        for _ in range(max(int(max_rounds), 1)):
            can_frames = self._receive_can_now(max_count=max_count, timeout_ms=0)
            canfd_frames = self._receive_canfd_now(max_count=max_count, timeout_ms=0)
            discarded += len(can_frames) + len(canfd_frames)
            if not can_frames and not canfd_frames:
                break
        return discarded

    def _prepare_diag_exchange(self, cluster_index, aggressive=False):
        self._drain_queued_rx_frames()
        if not self._is_downstream_cluster(cluster_index):
            return
        flush_rounds = 6 if aggressive else 3
        self.flush_rx_backlog(max_rounds=flush_rounds, max_count=200)

    def _wait_for_can_frame(self, expected_frame_id, matcher, timeout_s, frame_kind):
        deadline = time.monotonic() + max(float(timeout_s), 0.0)
        while time.monotonic() <= deadline:
            if not self.pending_can_frames and not self.pending_canfd_frames:
                self.pending_can_frames.extend(
                    self._receive_can_now(max_count=200, timeout_ms=0)
                )
                self.pending_canfd_frames.extend(
                    self._receive_canfd_now(max_count=200, timeout_ms=0)
                )
            if not self.pending_can_frames and not self.pending_canfd_frames:
                time.sleep(0.01)
                continue

            if self.pending_can_frames:
                frame = self.pending_can_frames.popleft()
                rx_kind = "rx_can"
            else:
                frame = self.pending_canfd_frames.popleft()
                rx_kind = "rx_canfd"
            if frame.frame_id == expected_frame_id and matcher(frame):
                self.log_manager.log_rx(rx_kind, frame, [frame_kind])
                self._record_rx_activity(frame, True)
                return frame
            handled = self._handle_frame(frame, rx_kind, PollResult())
            self._record_rx_activity(frame, handled)

        return None

    def _receive_pending_can_frames(self, max_count):
        if self.pending_can_frames:
            return [
                self.pending_can_frames.popleft()
                for _ in range(min(max_count, len(self.pending_can_frames)))
            ]
        return self._receive_can_now(max_count=max_count, timeout_ms=0)

    def _receive_pending_canfd_frames(self, max_count):
        if self.pending_canfd_frames:
            return [
                self.pending_canfd_frames.popleft()
                for _ in range(min(max_count, len(self.pending_canfd_frames)))
            ]
        return self._receive_canfd_now(max_count=max_count, timeout_ms=0)

    def _authorize_control_once(self, cluster_index, timeout_s):
        result = self._send_diag_request(
            "decode_seed",
            cluster_index,
            CMD_DECODE_SECU,
            SECURITY_REQUEST_SEED,
        )
        if result <= 0:
            raise RuntimeError("工装模式解锁请求发送失败")

        expected_response_id = self._build_response_frame_id(RESP_DECODE_SECU, cluster_index)
        seed_frame = self._wait_for_can_frame(
            expected_response_id,
            lambda frame: (
                (frame.data_len >= 7 and frame.data.startswith(SECURITY_SEED_RESPONSE))
                or frame.data[:4] == bytes((0x03, 0x7F, 0x27, 0x11))
            ),
            timeout_s,
            "decode_seed_response",
        )
        if seed_frame is None:
            raise RuntimeError("工装模式解锁种子响应超时")

        if not seed_frame.data.startswith(SECURITY_SEED_RESPONSE):
            raise RuntimeError("工装模式解锁请求被设备拒绝，设备可能还停留在上一次解锁步骤。")

        seed = int.from_bytes(seed_frame.data[3:7], byteorder="big", signed=False)
        key = security_seed_to_key(seed)
        key_payload = SECURITY_SEND_KEY + key.to_bytes(4, byteorder="big", signed=False) + b"\x00"

        result = self._send_diag_request(
            "decode_key",
            cluster_index,
            CMD_DECODE_SECU,
            key_payload,
        )
        if result <= 0:
            raise RuntimeError("工装模式解锁密钥发送失败")

        key_frame = self._wait_for_can_frame(
            expected_response_id,
            lambda frame: frame.data.startswith(SECURITY_KEY_RESPONSE) or frame.data[:2] == bytes((0x03, 0x7F)),
            timeout_s,
            "decode_key_response",
        )
        if key_frame is None:
            raise RuntimeError("工装模式解锁确认超时")

        if not key_frame.data.startswith(SECURITY_KEY_RESPONSE):
            raise RuntimeError("工装模式解锁密钥被设备拒绝")

    def _authorize_control(self, cluster_index, timeout_s, retries=1):
        attempt_count = max(int(retries), 0) + 1
        last_error = None
        self._drain_queued_rx_frames()
        for attempt_index in range(attempt_count):
            if attempt_index:
                time.sleep(0.05)
            try:
                self._authorize_control_once(cluster_index, timeout_s)
                return
            except RuntimeError as exc:
                last_error = exc
                if attempt_index + 1 >= attempt_count:
                    raise
        if last_error is not None:
            raise last_error

    def _execute_control_command(
        self,
        cluster_index,
        control_code,
        para1=0,
        para2=0,
        timeout_s=1.0,
        action_name="Control command",
    ):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        self._authorize_control(cluster_index, timeout_s, retries=1)
        payload = (
            int(control_code).to_bytes(2, byteorder="little", signed=False)
            + (int(para1) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
            + (int(para2) & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
        )
        result = self.send_control(cluster_index, payload)
        if result <= 0:
            raise RuntimeError(f"{action_name} request send failed")

        response = self._wait_for_can_frame(
            self._build_response_frame_id(RESP_CTRL_HARDWARE, cluster_index),
            lambda frame: frame.data_len >= 1,
            timeout_s,
            action_name.lower().replace(" ", "_"),
        )
        if response is None:
            raise RuntimeError(f"{action_name} response timed out")
        if response.data[0] != 1:
            raise RuntimeError(f"{action_name} was rejected")
        return True

    @staticmethod
    def _combine_words(high_word, low_word):
        if high_word is None or low_word is None:
            return None
        return ((int(high_word) & 0xFFFF) << 16) | (int(low_word) & 0xFFFF)

    @staticmethod
    def _parse_device_system_time(values):
        keys = (
            "device_time_year",
            "device_time_month",
            "device_time_day",
            "device_time_hour",
            "device_time_minute",
            "device_time_second",
        )
        parts = [values.get(key) for key in keys]
        if any(part is None for part in parts):
            return None
        try:
            return datetime(*(int(part) for part in parts))
        except (TypeError, ValueError):
            return None

    def _set_device_time_anchor(self, cluster_index, device_time, force=False):
        cluster_index = int(cluster_index)
        received_at = time.monotonic()
        anchor = self.device_time_anchors.get(cluster_index)
        if anchor is not None and not force:
            anchor_time, anchor_received_at = anchor
            elapsed_seconds = max(0, int(received_at - anchor_received_at))
            running_time = anchor_time + timedelta(seconds=elapsed_seconds)
            # A delayed indexed response or duplicate broadcast must not rewind
            # the clock and repeatedly pin the display to an old second.
            if device_time <= running_time:
                return False

        self.device_time_anchors[cluster_index] = (device_time, received_at)
        return True

    def _update_device_time_anchor_from_components(self, cluster_index):
        values = self.index_monitor_values.get(int(cluster_index), {})
        device_time = self._parse_device_system_time(values)
        if device_time is None:
            return False
        return self._set_device_time_anchor(cluster_index, device_time)

    def _device_system_time_text(self, cluster_index, values):
        anchor = self.device_time_anchors.get(int(cluster_index))
        if anchor is not None:
            device_time, received_at = anchor
            elapsed_seconds = max(0, int(time.monotonic() - received_at))
            return (device_time + timedelta(seconds=elapsed_seconds)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        device_time = self._parse_device_system_time(values)
        if device_time is None:
            return None
        return device_time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _to_input_state(raw_value):
        if raw_value is None:
            return None
        return 1 if int(raw_value) else 0

    def _raw_word_value(self, cluster_index, signal_id, signed=False):
        raw_word = self.legacy_request_raw_words.get(cluster_index, {}).get(int(signal_id))
        if raw_word is None:
            return None
        raw_word = int(raw_word) & 0xFFFF
        if signed and raw_word & 0x8000:
            return raw_word - 0x10000
        return raw_word

    def _raw_word_high_byte(self, cluster_index, signal_id):
        raw_word = self._raw_word_value(cluster_index, signal_id, signed=False)
        if raw_word is None:
            return None
        return (raw_word >> 8) & 0xFF

    def _raw_word_low_byte(self, cluster_index, signal_id):
        raw_word = self._raw_word_value(cluster_index, signal_id, signed=False)
        if raw_word is None:
            return None
        return raw_word & 0xFF

    def read_u16_variable(self, cluster_index, variable_index, timeout_s=1.0, retries=0):
        return self.read_data_u16(
            cluster_index,
            variable_index,
            timeout_s=timeout_s,
            retries=retries,
        )

    def read_data_u16(self, cluster_index, data_id, timeout_s=1.0, retries=0):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        data_id = int(data_id)
        payload = data_id.to_bytes(4, byteorder="little", signed=False)
        attempt_count = max(int(retries), 0) + 1
        expected_response_id = self._build_response_frame_id(RESP_READ_VAR, cluster_index)
        for attempt_index in range(attempt_count):
            result = self._send_diag_request(
                "read_var",
                cluster_index,
                CMD_READ_VAR,
                payload,
            )
            if result <= 0:
                raise RuntimeError("Read variable request send failed")

            response = self._wait_for_can_frame(
                expected_response_id,
                lambda frame: (
                    frame.data_len >= 7
                    and int.from_bytes(frame.data[:4], byteorder="little", signed=False)
                    == data_id
                ),
                timeout_s,
                "read_var_response",
            )
            if response is None:
                if attempt_index + 1 < attempt_count:
                    is_downstream = self._is_downstream_cluster(cluster_index)
                    self._prepare_diag_exchange(
                        cluster_index,
                        aggressive=is_downstream,
                    )
                    time.sleep(0.02 if is_downstream else 0.01)
                    continue
                raise RuntimeError("Read parameter response timed out")
            if not response.data[6]:
                raise RuntimeError(f"Read parameter 0x{data_id:05X} was rejected")
            return int.from_bytes(response.data[4:6], byteorder="little", signed=False)
        raise RuntimeError("Read parameter response timed out")

    def read_data_u16_many(
        self,
        cluster_index,
        data_ids,
        timeout_s=1.0,
        retries=0,
        batch_size=4,
        settle_delay_s=0.0,
    ):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        ordered_ids = list(dict.fromkeys(int(data_id) for data_id in data_ids))
        if not ordered_ids:
            return {}

        expected_response_id = self._build_response_frame_id(RESP_READ_VAR, cluster_index)
        attempt_count = max(int(retries), 0) + 1
        batch_size = max(int(batch_size), 1)
        values = {}

        for batch_start in range(0, len(ordered_ids), batch_size):
            batch_ids = ordered_ids[batch_start : batch_start + batch_size]
            pending_ids = set(batch_ids)

            for attempt_index in range(attempt_count):
                for data_id in tuple(pending_ids):
                    payload = data_id.to_bytes(4, byteorder="little", signed=False)
                    result = self._send_diag_request(
                        "read_var_batch",
                        cluster_index,
                        CMD_READ_VAR,
                        payload,
                    )
                    if result <= 0:
                        raise RuntimeError("Read variable batch request send failed")

                deadline = time.monotonic() + max(float(timeout_s), 0.0)
                while pending_ids:
                    remaining_s = max(deadline - time.monotonic(), 0.0)
                    response = self._wait_for_can_frame(
                        expected_response_id,
                        lambda frame: (
                            frame.data_len >= 7
                            and int.from_bytes(
                                frame.data[:4], byteorder="little", signed=False
                            )
                            in pending_ids
                        ),
                        remaining_s,
                        "read_var_batch_response",
                    )
                    if response is None:
                        break
                    data_id = int.from_bytes(
                        response.data[:4], byteorder="little", signed=False
                    )
                    if not response.data[6]:
                        raise RuntimeError(f"Read parameter 0x{data_id:05X} was rejected")
                    values[data_id] = int.from_bytes(
                        response.data[4:6], byteorder="little", signed=False
                    )
                    pending_ids.discard(data_id)

                if not pending_ids:
                    break
                if attempt_index + 1 < attempt_count:
                    is_downstream = self._is_downstream_cluster(cluster_index)
                    self._prepare_diag_exchange(
                        cluster_index,
                        aggressive=is_downstream,
                    )
                    time.sleep(0.02 if is_downstream else 0.01)

            if pending_ids:
                missing = ", ".join(f"0x{data_id:05X}" for data_id in sorted(pending_ids))
                raise RuntimeError(f"Read parameter batch response timed out: {missing}")
            if settle_delay_s > 0 and batch_start + batch_size < len(ordered_ids):
                time.sleep(float(settle_delay_s))

        return values

    def write_data_u16(self, cluster_index, data_id, value, timeout_s=1.0):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        data_id = int(data_id)
        value = int(value) & 0xFFFF
        payload = (
            data_id.to_bytes(4, byteorder="little", signed=False)
            + value.to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
        )
        result = self._send_diag_request(
            "write_var",
            cluster_index,
            CMD_WRITE_VAR,
            payload,
        )
        if result <= 0:
            raise RuntimeError("Write parameter request send failed")

        response = self._wait_for_can_frame(
            self._build_response_frame_id(RESP_WRITE_VAR, cluster_index),
            lambda frame: (
                frame.data_len >= 6
                and int.from_bytes(frame.data[:4], byteorder="little", signed=False)
                == data_id
            ),
            timeout_s,
            "write_var_response",
        )
        if response is None:
            raise RuntimeError("Write parameter response timed out")
        if not int.from_bytes(response.data[4:6], byteorder="little", signed=False):
            raise RuntimeError(f"Write parameter 0x{data_id:05X} was rejected")
        return True

    def read_factory_test_mode(self, cluster_index, timeout_s=1.0):
        return self.read_u16_variable(
            cluster_index,
            VAR_SYS_WORK_MODE,
            timeout_s=timeout_s,
            retries=1,
        )

    def get_alarm_parameter_fields(self):
        return list(self.alarm_parameter_fields)

    def get_alarm_parameter_definitions(self):
        return list(self.alarm_parameter_definitions)

    def _alarm_parameter_read_profile(self, cluster_index, timeout_s, full_record=False):
        if self._is_downstream_cluster(cluster_index):
            if full_record:
                return (
                    max(float(timeout_s), ALARM_PARAMETER_REMOTE_RECORD_MIN_TIMEOUT_S),
                    ALARM_PARAMETER_REMOTE_RECORD_RETRIES,
                    ALARM_PARAMETER_REMOTE_RECORD_SETTLE_DELAY_S,
                )
            return (
                max(float(timeout_s), ALARM_PARAMETER_REMOTE_MIN_TIMEOUT_S),
                ALARM_PARAMETER_REMOTE_RETRIES,
                ALARM_PARAMETER_REMOTE_SETTLE_DELAY_S,
            )
        return max(float(timeout_s), 0.0), 1, 0.0

    def _read_alarm_parameter_field_value(
        self,
        cluster_index,
        alarm_id,
        field,
        timeout_s,
        full_record=False,
    ):
        effective_timeout_s, retries, settle_delay_s = self._alarm_parameter_read_profile(
            cluster_index,
            timeout_s,
            full_record=full_record,
        )
        data_id = self._alarm_parameter_data_id(alarm_id, field.index)
        raw_value = self.read_data_u16(
            cluster_index,
            data_id,
            timeout_s=effective_timeout_s,
            retries=retries,
        )
        if settle_delay_s > 0:
            time.sleep(settle_delay_s)
        return raw_value

    def read_alarm_parameter_summary(self, cluster_index, timeout_s=1.0):
        self._prepare_diag_exchange(cluster_index, aggressive=False)
        effective_timeout_s, retries, settle_delay_s = self._alarm_parameter_read_profile(
            cluster_index,
            timeout_s,
            full_record=False,
        )
        batch_size = (
            ALARM_PARAMETER_REMOTE_BATCH_SIZE
            if self._is_downstream_cluster(cluster_index)
            else ALARM_PARAMETER_LOCAL_BATCH_SIZE
        )
        data_ids = [
            self._alarm_parameter_data_id(definition.alarm_id, field.index)
            for definition in self.alarm_parameter_definitions
            for field in (
                ALARM_PARAMETER_FIELDS_BY_KEY[key]
                for key in ALARM_PARAMETER_SUMMARY_KEYS
            )
        ]
        raw_values = self.read_data_u16_many(
            cluster_index,
            data_ids,
            timeout_s=effective_timeout_s,
            retries=retries,
            batch_size=batch_size,
            settle_delay_s=settle_delay_s,
        )
        records = []
        for definition in self.alarm_parameter_definitions:
            values = {}
            for key in ALARM_PARAMETER_SUMMARY_KEYS:
                field = ALARM_PARAMETER_FIELDS_BY_KEY[key]
                data_id = self._alarm_parameter_data_id(definition.alarm_id, field.index)
                raw_value = raw_values[data_id]
                values[key] = self._decode_alarm_parameter_value(field, raw_value)
            records.append(
                AlarmParameterRecord(
                    alarm_id=definition.alarm_id,
                    code=definition.code,
                    name=definition.name,
                    values=values,
                    is_complete=False,
                )
            )
        return records

    def read_alarm_parameter_record(self, cluster_index, alarm_id, timeout_s=1.0):
        definition = self._get_alarm_parameter_definition(alarm_id)
        self._prepare_diag_exchange(cluster_index, aggressive=True)
        values = {}
        for field in self.alarm_parameter_fields:
            raw_value = self._read_alarm_parameter_field_value(
                cluster_index,
                alarm_id,
                field,
                timeout_s,
                full_record=True,
            )
            values[field.key] = self._decode_alarm_parameter_value(field, raw_value)
        return AlarmParameterRecord(
            alarm_id=definition.alarm_id,
            code=definition.code,
            name=definition.name,
            values=values,
            is_complete=True,
        )

    def write_alarm_parameter_record(self, cluster_index, record, timeout_s=1.0):
        if not isinstance(record, AlarmParameterRecord):
            raise TypeError("record must be an AlarmParameterRecord")

        for field in self.alarm_parameter_fields:
            if field.key not in record.values:
                continue
            data_id = self._alarm_parameter_data_id(record.alarm_id, field.index)
            raw_value = self._encode_alarm_parameter_value(field, record.values[field.key])
            self.write_data_u16(cluster_index, data_id, raw_value, timeout_s=timeout_s)
        return True

    def save_alarm_parameters_to_flash(self, cluster_index, timeout_s=1.0):
        payload = (
            CTRL_PARA_CONFIG.to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
            + CTRL_PARA_CONFIG_SAVE_ALL_TO_FLASH.to_bytes(
                2,
                byteorder="little",
                signed=False,
            )
            + b"\x00\x00"
        )
        result = self.send_control(cluster_index, payload)
        if result <= 0:
            raise RuntimeError("Save parameters to FLASH request send failed")

        response = self._wait_for_can_frame(
            self._build_response_frame_id(RESP_CTRL_HARDWARE, cluster_index),
            lambda frame: frame.data_len >= 1,
            timeout_s,
            "save_para_to_flash_response",
        )
        if response is None:
            raise RuntimeError("Save parameters to FLASH response timed out")
        if response.data[0] != 1:
            raise RuntimeError(
                "Save parameters to FLASH was rejected; confirm factory mode is enabled and wait 5 seconds before retrying"
            )
        return True

    def read_history_log_count(self, cluster_index, log_type=HISTORY_LOG_TYPE_ALARM, timeout_s=1.5, retries=1):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        log_type = int(log_type) & 0xFF
        expected_response_id = self._build_response_frame_id(RESP_READ_LOG, cluster_index)
        payload = b"\x00\x00" + bytes((log_type,)) + b"\x00\x00\x00\x00\x00"
        attempt_count = max(int(retries), 0) + 1
        for attempt_index in range(attempt_count):
            self._prepare_diag_exchange(
                cluster_index,
                aggressive=self._is_downstream_cluster(cluster_index),
            )
            result = self._send_diag_request(
                "history_log_count",
                cluster_index,
                CMD_READ_LOG,
                payload,
            )
            if result <= 0:
                raise RuntimeError("Read history log count request send failed")

            response = self._wait_for_can_frame(
                expected_response_id,
                lambda frame: (
                    frame.data_len >= 4
                    and frame.data[0] == 0xFF
                    and frame.data[1] == log_type
                ),
                timeout_s,
                "history_log_count_response",
            )
            if response is not None:
                return int.from_bytes(response.data[2:4], byteorder="little", signed=False)
            if attempt_index + 1 < attempt_count:
                time.sleep(0.03)
        raise RuntimeError("Read history log count response timed out")

    def read_history_log_entry(self, cluster_index, log_index, log_type=HISTORY_LOG_TYPE_ALARM, timeout_s=2.0, retries=1):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")
        log_index = int(log_index)
        if log_index <= 0:
            raise RuntimeError(f"Invalid history log index: {log_index}")

        log_type = int(log_type) & 0xFF
        payload = (
            (log_index & 0xFFFF).to_bytes(2, byteorder="little", signed=False)
            + bytes((log_type,))
            + b"\x00\x00\x00\x00\x00"
        )
        expected_response_id = self._build_response_frame_id(RESP_READ_LOG, cluster_index)
        attempt_count = max(int(retries), 0) + 1
        last_error = None
        for attempt_index in range(attempt_count):
            self._prepare_diag_exchange(
                cluster_index,
                aggressive=self._is_downstream_cluster(cluster_index),
            )
            result = self._send_diag_request(
                "history_log_entry",
                cluster_index,
                CMD_READ_LOG,
                payload,
            )
            if result <= 0:
                raise RuntimeError("Read history log request send failed")

            try:
                payload_bytes = self._collect_history_log_payload(
                    expected_response_id,
                    timeout_s,
                )
                return self.decode_history_log_payload(payload_bytes)
            except RuntimeError as exc:
                last_error = exc
                if attempt_index + 1 < attempt_count:
                    time.sleep(0.03)
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Read history log response timed out")

    def _collect_history_log_payload(self, expected_response_id, timeout_s):
        deadline = time.monotonic() + max(float(timeout_s), 0.0)
        chunks = {}
        while len(chunks) < HISTORY_LOG_CHUNK_COUNT and time.monotonic() <= deadline:
            remaining_s = max(deadline - time.monotonic(), 0.0)
            response = self._wait_for_can_frame(
                expected_response_id,
                lambda frame: (
                    frame.data_len >= 1
                    and (
                        frame.data[0] == 0xFE
                        or 1 <= frame.data[0] <= HISTORY_LOG_CHUNK_COUNT
                    )
                ),
                remaining_s,
                "history_log_entry_response",
            )
            if response is None:
                break
            chunk_index = response.data[0]
            if chunk_index == 0xFE:
                raise RuntimeError("History log entry was rejected")
            chunks[chunk_index] = response.data[1:8].ljust(HISTORY_LOG_CHUNK_SIZE, b"\x00")

        if len(chunks) < HISTORY_LOG_CHUNK_COUNT:
            missing = [
                str(index)
                for index in range(1, HISTORY_LOG_CHUNK_COUNT + 1)
                if index not in chunks
            ]
            raise RuntimeError(
                "Read history log response timed out"
                + (f" (missing chunks: {', '.join(missing)})" if missing else "")
            )
        return b"".join(
            chunks[index]
            for index in range(1, HISTORY_LOG_CHUNK_COUNT + 1)
        )[:HISTORY_LOG_PAYLOAD_SIZE]

    def clear_history_logs(self, cluster_index, timeout_s=1.0):
        return self._execute_control_command(
            cluster_index,
            CTRL_PARA_CONFIG,
            para2=CTRL_PARA_CONFIG_CLEAR_HISTORY_LOG,
            timeout_s=timeout_s,
            action_name="Clear history logs",
        )

    def decode_history_log_payload(self, payload):
        payload = bytes(payload)
        if len(payload) < HISTORY_LOG_PAYLOAD_SIZE:
            raise RuntimeError(
                f"History log payload too short: {len(payload)} < {HISTORY_LOG_PAYLOAD_SIZE}"
            )

        sequence = self._u16(payload, 0)
        subtype = payload[2]
        run_status = payload[3]
        time_text = self._decode_history_time(self._u32(payload, 4))
        relay_byte = payload[8]
        alarm_count = payload[9]
        raw_word = self._u16(payload, 10)
        alarm_info = self._u32(payload, 12)
        alarm_id = (alarm_info >> 24) & 0x3F
        alarm_level = (alarm_info >> 18) & 0x3F
        alarm_position = self._decode_history_alarm_position(alarm_info)
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
            timestamp=time_text,
            log_type="告警日志",
            log_subtype=self._history_log_subtype_text(subtype),
            run_status=run_status,
            relay_status=self._decode_relay_status(relay_byte),
            alarm_count=alarm_count,
            raw_word=raw_word,
            alarm_id=alarm_id,
            alarm_name=self._history_log_alarm_name(alarm_id),
            alarm_level=alarm_level,
            alarm_position=alarm_position,
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
            raw_payload=payload[:HISTORY_LOG_PAYLOAD_SIZE],
        )

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
            if relay_byte & (1 << (index - 1))
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
        code = f"{int(alarm_id):03d}"
        if int(alarm_id) <= 0:
            return "-"
        if code in self.alarm_display_names:
            return self.alarm_display_names[code]
        for definition in self.alarm_parameter_definitions:
            if definition.code == code or definition.alarm_id == int(alarm_id) - 1:
                return definition.name
        if int(alarm_id) - 1 < len(ALARM_PARAMETER_NAMES):
            return ALARM_PARAMETER_NAMES[int(alarm_id) - 1]
        return f"告警{code}"

    def control_channel(self, cluster_index, channel_id, enabled, timeout_s=1.0):
        return self._execute_control_command(
            cluster_index,
            CTRL_CHNNEL,
            para1=int(channel_id),
            para2=1 if enabled else 0,
            timeout_s=timeout_s,
            action_name="Control channel",
        )

    def restore_factory_parameters(self, cluster_index, timeout_s=1.0):
        return self._execute_control_command(
            cluster_index,
            CTRL_PARA_CONFIG,
            para2=CTRL_PARA_CONFIG_RESET_FACTORY,
            timeout_s=timeout_s,
            action_name="Restore factory parameters",
        )

    def restore_run_parameters(self, cluster_index, timeout_s=1.0):
        return self._execute_control_command(
            cluster_index,
            CTRL_PARA_CONFIG,
            para2=CTRL_PARA_CONFIG_RESET_RUN,
            timeout_s=timeout_s,
            action_name="Restore run parameters",
        )

    def restore_product_info(self, cluster_index, timeout_s=1.0):
        return self._execute_control_command(
            cluster_index,
            CTRL_PARA_CONFIG,
            para2=CTRL_PARA_CONFIG_RESET_PRODUCT_INFO,
            timeout_s=timeout_s,
            action_name="Restore product info",
        )

    def save_all_parameters_to_flash(self, cluster_index, timeout_s=1.0):
        return self.save_alarm_parameters_to_flash(cluster_index, timeout_s=timeout_s)

    def read_hvil_pwm_config(self, cluster_index, timeout_s=1.0):
        return {
            "freq": self.read_data_u16(
                cluster_index,
                PAR_SYS_OUTPUT_HVIL_FREQ,
                timeout_s=timeout_s,
            ),
            "duty": self.read_data_u16(
                cluster_index,
                PAR_SYS_OUTPUT_HVIL_DUTY_RATIO,
                timeout_s=timeout_s,
            ),
        }

    def write_hvil_pwm_config(self, cluster_index, freq, duty, timeout_s=1.0):
        self.write_data_u16(
            cluster_index,
            PAR_SYS_OUTPUT_HVIL_FREQ,
            freq,
            timeout_s=timeout_s,
        )
        self.write_data_u16(
            cluster_index,
            PAR_SYS_OUTPUT_HVIL_DUTY_RATIO,
            duty,
            timeout_s=timeout_s,
        )
        return True

    def read_user_set_soc(self, cluster_index, timeout_s=1.0):
        return self.read_data_u16(
            cluster_index,
            VAR_SYS_USER_SET_SOC,
            timeout_s=timeout_s,
        )

    def write_user_set_soc(self, cluster_index, soc_value, timeout_s=1.0):
        return self.write_data_u16(
            cluster_index,
            VAR_SYS_USER_SET_SOC,
            soc_value,
            timeout_s=timeout_s,
        )

    def sync_system_time(self, cluster_index, dt=None, timeout_s=1.0):
        if not self.is_open:
            raise RuntimeError("CANFD not connected")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"Invalid cluster index: {cluster_index}")

        current_time = dt or datetime.now()
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
                0x00,
            )
        )
        result = self._send_diag_request(
            "set_time",
            cluster_index,
            CMD_SET_TIME,
            payload,
        )
        if result <= 0:
            raise RuntimeError("Set system time request send failed")

        response = self._wait_for_can_frame(
            self._build_response_frame_id(RESP_SET_TIME, cluster_index),
            lambda frame: frame.data_len >= 7 and frame.data[:6] == payload[:6],
            timeout_s,
            "set_time_response",
        )
        if response is None:
            raise RuntimeError("Set system time response timed out")
        if not response.data[6]:
            raise RuntimeError("Set system time was rejected")
        self._set_device_time_anchor(cluster_index, current_time, force=True)
        return True

    def send_next_monitor_query(self, cluster_index):
        if not self.is_open:
            return 0
        if cluster_index not in self.cluster_index_to_address:
            return 0
        if not self.index_monitor_signal_ids:
            return 0

        cursor = self.monitor_query_cursors[cluster_index]
        data_id = self.index_monitor_signal_ids[cursor]
        payload = data_id.to_bytes(4, byteorder="little", signed=False)
        result = self._send_diag_request(
            "monitor_query",
            cluster_index,
            CMD_READ_VAR,
            payload,
        )
        self.monitor_query_cursors[cluster_index] = (
            cursor + 1
        ) % len(self.index_monitor_signal_ids)
        return result

    def send_signal_query(self, cluster_index, data_id):
        if not self.is_open:
            return 0
        if cluster_index not in self.cluster_index_to_address:
            return 0
        payload = int(data_id).to_bytes(4, byteorder="little", signed=False)
        return self._send_diag_request(
            "active_page_query",
            cluster_index,
            CMD_READ_VAR,
            payload,
        )

    def send_next_power_diagnostic_query(self, cluster_index):
        if not self.is_open:
            return 0
        if cluster_index not in self.cluster_index_to_address:
            return 0
        if not self.power_diagnostic_poll_sequence:
            return 0
        cursor = self.power_diagnostic_query_cursors[cluster_index]
        data_id = self.power_diagnostic_poll_sequence[cursor]
        result = self.send_signal_query(cluster_index, data_id)
        self.power_diagnostic_query_cursors[cluster_index] = (
            cursor + 1
        ) % len(self.power_diagnostic_poll_sequence)
        return result

    def reset_power_diagnostic_query(self, cluster_index):
        if cluster_index in self.power_diagnostic_query_cursors:
            self.power_diagnostic_query_cursors[cluster_index] = 0

    def get_power_diagnostic_snapshot(self, cluster_index):
        return dict(self.power_diagnostic_raw_values.get(int(cluster_index), {}))

    def _get_legacy_index_monitor_snapshot(self, cluster_index):
        """Return the historical name-based snapshot during protocol migration."""
        legacy = self.legacy_request_raw_values.get(cluster_index, {})
        extra = self.index_monitor_values.get(cluster_index, {})
        return {
            "work_mode": extra.get("work_mode"),
            "run_status": legacy.get("系统运行状态"),
            "system_current": legacy.get("系统电流[0.1A]"),
            "hall_current": legacy.get("霍尔电流[0.1A]"),
            "shunt_current": legacy.get("分流器电流[0.1A]"),
            "battery_voltage": legacy.get("B端电压[0.1V]"),
            "system_voltage": legacy.get("累计总压"),
            "pack_voltage": legacy.get("P端电压[0.1V]"),
            "soc": legacy.get("系统SOC"),
            "display_soc": legacy.get("显示SOC"),
            "soh": legacy.get("系统SOH"),
            "pure_soc": legacy.get("PURE_SOC"),
            "revise_soc": legacy.get("REVISE_SOC"),
            "revise_soc_temp": legacy.get("REVISE_SOC_TEMP"),
            "fuzzy_soc": legacy.get("FUZZY_SOC"),
            "cell_max_soc": legacy.get("CELL_MAX_SOC"),
            "cell_min_soc": legacy.get("CELL_MIN_SOC"),
            "cell_max_soc_temp": legacy.get("CELL_MAX_SOC_TEMP"),
            "cell_min_soc_temp": legacy.get("CELL_MIN_SOC_TEMP"),
            "diff_voltage": legacy.get("系统压差[mV]"),
            "diff_temp": legacy.get("系统温差[0.1℃]"),
            "avg_voltage": extra.get("avg_voltage"),
            "avg_temp": extra.get("avg_temp"),
            "module_count": legacy.get("系统模组个数"),
            "afe_count": legacy.get("每个模组AFE数"),
            "online_lecu_num": extra.get("online_lecu_num"),
            "max_cell_voltage": legacy.get("最大单体电压[mV]"),
            "max_cell_voltage_module": legacy.get("最大单体电压模组位置"),
            "max_cell_voltage_index": legacy.get("最大单体电压模组内位置"),
            "min_cell_voltage": legacy.get("最小单体电压[mV]"),
            "min_cell_voltage_module": legacy.get("最小单体电压模组位置"),
            "min_cell_voltage_index": legacy.get("最小单体电压模组内位置"),
            "max_cell_temp": legacy.get("最大单体温度[0.1℃]"),
            "max_cell_temp_module": legacy.get("最大单体温度模组位置"),
            "max_cell_temp_index": legacy.get("最大单体温度模组内位置"),
            "min_cell_temp": legacy.get("最小单体温度[0.1℃]"),
            "min_cell_temp_module": legacy.get("最小单体温度模组位置"),
            "min_cell_temp_index": legacy.get("最小单体温度模组内位置"),
            "remaining_discharge_kwh": legacy.get("剩余可放电[0.01KWH]"),
            "remaining_charge_kwh": legacy.get("剩余可充电[0.01KWH]"),
            "single_charge_kwh": legacy.get("单次充电电量[0.1KWH]"),
            "single_discharge_kwh": legacy.get("单次放电电量[0.1KWH]"),
            "total_charge_kwh": self._combine_words(
                legacy.get("累计充电电量高字节[0.01KWH]"),
                legacy.get("累计充电电量低字节[0.01KWH]"),
            ),
            "total_discharge_kwh": self._combine_words(
                legacy.get("累计放电电量高字节[0.01KWH]"),
                legacy.get("累计放电电量低字节[0.01KWH]"),
            ),
            "continuous_discharge_power": legacy.get("持续最大允许放电功率[w]"),
            "continuous_charge_power": legacy.get("持续最大允许充电功率[w]"),
            "continuous_discharge_current": legacy.get("持续最大允许放电电流[0.1A]"),
            "continuous_charge_current": legacy.get("持续最大允许充电电流[0.1A]"),
            "user_set_soc": extra.get("user_set_soc"),
            "hvil_pwm_freq": extra.get("hvil_pwm_freq"),
            "hvil_pwm_duty": extra.get("hvil_pwm_duty"),
            "board_temp1": extra.get("board_temp1"),
            "board_temp2": extra.get("board_temp2"),
            "rt_values": [
                extra.get(f"rt{index}")
                for index in range(1, 11)
            ],
            "di_states": [
                self._to_input_state(extra.get(f"di{index}"))
                for index in range(1, 13)
            ],
            "relay_states": [
                bool(extra.get(f"relay{index}", 0))
                for index in range(1, 11)
            ],
        }

    def get_index_monitor_snapshot(self, cluster_index):
        extra = self.index_monitor_values.get(cluster_index, {})
        return {
            "device_time": self._device_system_time_text(cluster_index, extra),
            "work_mode": extra.get("work_mode"),
            "run_status": self._raw_word_value(cluster_index, VAR_SYS_RUN_STATUS),
            "system_current": self._raw_word_value(cluster_index, 0x0E, signed=True),
            "hall_current": self._raw_word_value(cluster_index, 0x315, signed=True),
            "shunt_current": self._raw_word_value(cluster_index, 0x316, signed=True),
            "battery_voltage": self._raw_word_value(cluster_index, 0x5B),
            "system_voltage": self._raw_word_value(cluster_index, 0x0D),
            "pack_voltage": self._raw_word_value(cluster_index, 0x5C),
            "soc": self._raw_word_value(cluster_index, VAR_SYS_SOC),
            "display_soc": self._raw_word_value(cluster_index, 0x12),
            "soh": self._raw_word_value(cluster_index, 0x11),
            "pure_soc": self._raw_word_value(cluster_index, 0x1C2),
            "revise_soc": self._raw_word_value(cluster_index, 0x1C3),
            "revise_soc_temp": self._raw_word_value(cluster_index, 0x1C4),
            "fuzzy_soc": self._raw_word_value(cluster_index, 0x1C7),
            "cell_max_soc": self._raw_word_value(cluster_index, 0x1C0),
            "cell_min_soc": self._raw_word_value(cluster_index, 0x1C1),
            "cell_max_soc_temp": self._raw_word_value(cluster_index, 0x1C6),
            "cell_min_soc_temp": self._raw_word_value(cluster_index, 0x1C5),
            "diff_voltage": self._raw_word_value(cluster_index, 0x141),
            "diff_temp": self._raw_word_value(cluster_index, 0x142),
            "avg_voltage": extra.get("avg_voltage"),
            "avg_temp": extra.get("avg_temp"),
            "module_count": extra.get("module_count"),
            "afe_count": extra.get("afe_count"),
            "online_lecu_num": extra.get("online_lecu_num"),
            "max_cell_voltage": self._raw_word_value(cluster_index, 0x148),
            "max_cell_voltage_module": self._raw_word_high_byte(cluster_index, 0x149),
            "max_cell_voltage_index": self._raw_word_low_byte(cluster_index, 0x149),
            "min_cell_voltage": self._raw_word_value(cluster_index, 0x14B),
            "min_cell_voltage_module": self._raw_word_high_byte(cluster_index, 0x14C),
            "min_cell_voltage_index": self._raw_word_low_byte(cluster_index, 0x14C),
            "max_cell_temp": self._raw_word_value(cluster_index, 0x14E, signed=True),
            "max_cell_temp_module": self._raw_word_high_byte(cluster_index, 0x14F),
            "max_cell_temp_index": self._raw_word_low_byte(cluster_index, 0x14F),
            "min_cell_temp": self._raw_word_value(cluster_index, 0x151, signed=True),
            "min_cell_temp_module": self._raw_word_high_byte(cluster_index, 0x152),
            "min_cell_temp_index": self._raw_word_low_byte(cluster_index, 0x152),
            "remaining_discharge_kwh": self._raw_word_value(cluster_index, 0x252),
            "remaining_charge_kwh": self._raw_word_value(cluster_index, 0x253),
            "single_charge_kwh": self._raw_word_value(cluster_index, 0x1FD),
            "single_discharge_kwh": self._raw_word_value(cluster_index, 0x1FE),
            "total_charge_kwh": self._combine_words(
                self._raw_word_value(cluster_index, 0x90886),
                self._raw_word_value(cluster_index, 0x90885),
            ),
            "total_discharge_kwh": self._combine_words(
                self._raw_word_value(cluster_index, 0x90888),
                self._raw_word_value(cluster_index, 0x90887),
            ),
            "continuous_discharge_power": self._raw_word_value(
                cluster_index, VAR_SYS_ALLOW_DSCH_60S_POWER
            ),
            "continuous_charge_power": self._raw_word_value(
                cluster_index, VAR_SYS_ALLOW_CHRG_60S_POWER
            ),
            "continuous_discharge_current": self._raw_word_value(
                cluster_index, VAR_SYS_ALLOW_DSCH_60S_CURR
            ),
            "continuous_charge_current": self._raw_word_value(
                cluster_index, VAR_SYS_ALLOW_CHRG_60S_CURR
            ),
            "user_set_soc": extra.get("user_set_soc"),
            "hvil_pwm_freq": extra.get("hvil_pwm_freq"),
            "hvil_pwm_duty": extra.get("hvil_pwm_duty"),
            "board_temp1": extra.get("board_temp1"),
            "board_temp2": extra.get("board_temp2"),
            "rt_values": [
                extra.get(f"rt{index}")
                for index in range(1, 11)
            ],
            "di_states": [
                self._to_input_state(extra.get(f"di{index}"))
                for index in range(1, 13)
            ],
            "relay_states": [
                bool(extra.get(f"relay{index}", 0))
                for index in range(1, 11)
            ],
        }

    def send_next_query(self, active_tab_index):
        if not self.is_open:
            return 0
        if active_tab_index not in self.cluster_index_to_address:
            return 0
        if not self.request_query_signal_ids:
            return 0

        signal_id = self.request_query_signal_ids[self.query_cursors[active_tab_index]]
        payload = signal_id.to_bytes(4, byteorder="little", signed=False) + b"\x00\x00\x00\x00"
        result = self._send_diag_request(
            "query",
            active_tab_index,
            CMD_READ_VAR,
            payload,
        )
        self.query_cursors[active_tab_index] = (
            self.query_cursors[active_tab_index] + 1
        ) % len(self.request_query_signal_ids)
        return result

    def send_next_balance_query(self, active_tab_index):
        if not self.is_open:
            return 0
        if active_tab_index not in self.cluster_index_to_address:
            return 0
        if not self.balance_request_signal_ids:
            return 0

        cursor = self.balance_query_cursors[active_tab_index]
        signal_id = self.balance_request_signal_ids[cursor]
        payload = signal_id.to_bytes(4, byteorder="little", signed=False) + b"\x00\x00\x00\x00"
        result = self._send_diag_request(
            "balance_query",
            active_tab_index,
            CMD_READ_VAR,
            payload,
        )
        self.balance_query_cursors[active_tab_index] = (
            cursor + 1
        ) % len(self.balance_request_signal_ids)
        return result

    def send_control(self, cluster_index, payload):
        if not self.is_open:
            return 0
        return self._send_diag_request("control", cluster_index, CMD_CTRL_HARDWARE, payload)

    def set_factory_test_mode(self, cluster_index, enabled, timeout_s=1.0):
        if not self.is_open:
            raise RuntimeError("CANFD 未连接")
        if cluster_index not in self.cluster_index_to_address:
            raise RuntimeError(f"无效簇号: {cluster_index}")

        self._authorize_control(cluster_index, timeout_s, retries=1)

        work_mode = WORK_MODE_GZ_TEST if enabled else WORK_MODE_NORMAL
        payload = (
            CTRL_WORK_MODE.to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
            + work_mode.to_bytes(2, byteorder="little", signed=False)
            + b"\x00\x00"
        )
        result = self.send_control(cluster_index, payload)
        if result <= 0:
            raise RuntimeError("工装模式控制请求发送失败")

        response = self._wait_for_can_frame(
            self._build_response_frame_id(RESP_CTRL_HARDWARE, cluster_index),
            lambda frame: frame.data_len >= 1,
            timeout_s,
            "work_mode_response",
        )
        if response is None:
            raise RuntimeError("工装模式控制响应超时")
        if response.data[0] != 1:
            raise RuntimeError("工装模式控制被设备拒绝")
        actual_work_mode = self.read_factory_test_mode(cluster_index, timeout_s=timeout_s)
        if actual_work_mode != work_mode:
            raise RuntimeError(
                f"Factory mode readback mismatch: expected {work_mode}, got {actual_work_mode}"
            )
        return actual_work_mode

    def write_legacy_snapshots(self, cluster_index=None):
        if not self.snapshot_logging_enabled:
            return

        target_clusters = (
            [int(cluster_index)]
            if cluster_index is not None
            else list(self.cluster_indices)
        )
        for current_cluster_index in target_clusters:
            if current_cluster_index not in self.cluster_index_to_address:
                continue
            self.log_manager.write_cluster_snapshot(
                current_cluster_index,
                self.legacy_signal_state[current_cluster_index],
            )
            self.legacy_signal_dirty[current_cluster_index] = False

        target_addresses = (
            [self.cluster_index_to_address[int(cluster_index)]]
            if cluster_index is not None and int(cluster_index) in self.cluster_index_to_address
            else list(self.cluster_addresses)
        )
        for address in target_addresses:
            if self.periodic_voltage_dirty[address] and self.periodic_voltage_values[address]:
                self.log_manager.write_voltage_snapshot(
                    address,
                    self._ordered_values(self.periodic_voltage_values[address]),
                )
                self.periodic_voltage_dirty[address] = False

            if (
                self.periodic_temperature_dirty[address]
                and self.periodic_temperature_values[address]
            ):
                self.log_manager.write_temperature_snapshot(
                    address,
                    self._ordered_values(self.periodic_temperature_values[address]),
                )
                self.periodic_temperature_dirty[address] = False

            if self.legacy_balance_dirty[address] and any(
                value is not None for value in self.legacy_balance_values[address]
            ):
                self.log_manager.write_balance_snapshot(
                    address,
                    self.legacy_balance_values[address],
                )
                self.legacy_balance_dirty[address] = False

            balance_temperature_values = self.get_periodic_balance_temperature_values(address)
            if (
                self.periodic_balance_temperature_dirty[address]
                and balance_temperature_values
            ):
                self.log_manager.write_balance_temperature_snapshot(
                    address,
                    balance_temperature_values,
                )
                self.periodic_balance_temperature_dirty[address] = False

        flush_logger = getattr(self.log_manager, "flush", None)
        if callable(flush_logger):
            flush_logger()

    def set_snapshot_logging_enabled(self, enabled):
        enabled = bool(enabled)
        self.snapshot_logging_enabled = enabled
        self.runtime_config["SAVE_LOG"] = 1 if enabled else 0
        if hasattr(self.log_manager, "set_enabled"):
            self.log_manager.set_enabled(enabled)
        else:
            self.log_manager.enabled = enabled

    def _debug_print(self, message):
        if self.debug_enabled:
            print(message, flush=True)

    def _rebuild_dbc_catalogs(self):
        self.dbc_catalogs = {
            address: self.dbc_runtime.get_catalog(address) if self.dbc_runtime else []
            for address in self.cluster_addresses
        }

    def _clear_periodic_decode_caches(self):
        self.periodic_voltage_values = {address: {} for address in self.cluster_addresses}
        self.periodic_temperature_values = {address: {} for address in self.cluster_addresses}
        self.periodic_balance_temperature_values = {
            address: {}
            for address in self.cluster_addresses
        }
        self.periodic_balance_values = {address: {} for address in self.cluster_addresses}
        self.periodic_alarm_values = {address: {} for address in self.cluster_addresses}
        self.periodic_terminal_temperature_values = {
            address: {}
            for address in self.cluster_addresses
        }
        self.periodic_voltage_dirty = {
            address: False
            for address in self.cluster_addresses
        }
        self.periodic_temperature_dirty = {
            address: False
            for address in self.cluster_addresses
        }
        self.periodic_balance_temperature_dirty = {
            address: False
            for address in self.cluster_addresses
        }

    def _reset_runtime_state(self):
        self.legacy_signal_state = {
            cluster_index: {
                signal_name: "0"
                for signal_name in self.snapshot_log_signal_names
            }
            for cluster_index in self.cluster_indices
        }
        self.legacy_request_raw_values = {
            cluster_index: {}
            for cluster_index in self.cluster_indices
        }
        self.legacy_request_raw_words = {
            cluster_index: {}
            for cluster_index in self.cluster_indices
        }

        self.index_monitor_values = {
            cluster_index: {}
            for cluster_index in self.cluster_indices
        }
        self.device_time_anchors = {
            cluster_index: None
            for cluster_index in self.cluster_indices
        }
        self.power_diagnostic_raw_values = {
            cluster_index: {}
            for cluster_index in self.cluster_indices
        }
        self.pending_can_frames = deque()
        self.pending_canfd_frames = deque()
        self.tx_attempt_count = 0
        self.tx_frame_count = 0
        self.tx_failure_count = 0
        self.rx_frame_count = 0
        self.rx_handled_frame_count = 0
        self.last_tx_monotonic = None
        self.last_rx_monotonic = None
        self.last_tx_time_text = ""
        self.last_rx_time_text = ""
        self.last_rx_frame_id = None
        self.tx_attempt_count_by_cluster = {
            cluster_index: 0 for cluster_index in self.cluster_indices
        }
        self.tx_frame_count_by_cluster = {
            cluster_index: 0 for cluster_index in self.cluster_indices
        }
        self.tx_failure_count_by_cluster = {
            cluster_index: 0 for cluster_index in self.cluster_indices
        }
        self.rx_frame_count_by_cluster = {
            cluster_index: 0 for cluster_index in self.cluster_indices
        }
        self.rx_handled_frame_count_by_cluster = {
            cluster_index: 0 for cluster_index in self.cluster_indices
        }
        self.last_tx_monotonic_by_cluster = {
            cluster_index: None for cluster_index in self.cluster_indices
        }
        self.last_rx_monotonic_by_cluster = {
            cluster_index: None for cluster_index in self.cluster_indices
        }
        self.last_tx_time_text_by_cluster = {
            cluster_index: "" for cluster_index in self.cluster_indices
        }
        self.last_rx_time_text_by_cluster = {
            cluster_index: "" for cluster_index in self.cluster_indices
        }
        self.last_rx_frame_id_by_cluster = {
            cluster_index: None for cluster_index in self.cluster_indices
        }
        self.legacy_signal_dirty = {
            cluster_index: True
            for cluster_index in self.cluster_indices
        }
        self._clear_periodic_decode_caches()
        self.legacy_balance_values = {
            address: [None] * (self.balance_module_count * self.balance_cells_per_module)
            for address in self.cluster_addresses
        }
        self.legacy_balance_dirty = {
            address: False
            for address in self.cluster_addresses
        }
        self.balance_control_words = {
            address: {}
            for address in self.cluster_addresses
        }
        self.balance_query_cursors = {
            cluster_index: 0
            for cluster_index in self.cluster_indices
        }
        self.query_cursors = {
            cluster_index: 0
            for cluster_index in self.cluster_indices
        }
        self.monitor_query_cursors = {
            cluster_index: 0
            for cluster_index in self.cluster_indices
        }
        self.power_diagnostic_query_cursors = {
            cluster_index: 0
            for cluster_index in self.cluster_indices
        }
