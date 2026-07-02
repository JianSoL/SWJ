from dataclasses import dataclass
from datetime import datetime


RUN_STATE_NAMES = {
    0: "初始",
    1: "自检",
    2: "准备",
    3: "预充",
    4: "高压待机",
    5: "放电",
    6: "充电",
    7: "放空",
    8: "充满",
    9: "故障",
    10: "切断",
    11: "休眠",
}

HIGH_VOLTAGE_STATES = {3, 4, 5, 6, 7, 8}
POWER_DOWN_STATES = {0, 1, 2, 9, 10, 11}


@dataclass(frozen=True)
class DiagnosticSignal:
    key: str
    data_id: int
    signed: bool = False
    scale: float = 1.0
    unit: str = ""


POWER_DIAGNOSTIC_SIGNAL_DEFINITIONS = (
    DiagnosticSignal("run_status", 12),
    DiagnosticSignal("task_run_flag", 23),
    DiagnosticSignal("addressing_addr", 28),
    DiagnosticSignal("breaker_di4", 39),
    *(DiagnosticSignal(f"relay{number}_status", 47 + number) for number in range(1, 11)),
    *(DiagnosticSignal(f"relay{number}_feedback", 57 + number) for number in range(1, 11)),
    DiagnosticSignal("battery_voltage", 91, scale=0.1, unit="V"),
    DiagnosticSignal("pack_voltage", 92, scale=0.1, unit="V"),
    DiagnosticSignal("severe_level", 276),
    DiagnosticSignal("hvil_fault", 280),
    DiagnosticSignal("relay_stick_test", 289),
    DiagnosticSignal("current_sensor_error", 290),
    DiagnosticSignal("inner_fault", 296),
    DiagnosticSignal("csu_addressing", 404),
    DiagnosticSignal("current_abs", 617, scale=0.1, unit="A"),
    DiagnosticSignal("hall_current", 818, signed=True, scale=0.1, unit="A"),
    DiagnosticSignal("shunt_current", 819, signed=True, scale=0.1, unit="A"),
    DiagnosticSignal("severe_level_up", 894),
    DiagnosticSignal("severe_level_down", 895),
    DiagnosticSignal("battery_voltage_up", 900, scale=0.1, unit="V"),
    DiagnosticSignal("battery_voltage_down", 901, scale=0.1, unit="V"),
    DiagnosticSignal("pack_voltage_up", 902, scale=0.1, unit="V"),
    DiagnosticSignal("pack_voltage_down", 903, scale=0.1, unit="V"),
    DiagnosticSignal("insulation_finished", 904),
    DiagnosticSignal("vms_ctrl_relay", 0x83001),
    DiagnosticSignal("vms_ctrl_relay_req", 0x83002),
    DiagnosticSignal("vms_shutdown_req", 0x83004),
    DiagnosticSignal("vms_ctrl_relay_req_up", 0x8301B),
    DiagnosticSignal("vms_ctrl_relay_req_down", 0x8301C),
    DiagnosticSignal("relay_precharge_channel", 0x9041F),
    DiagnosticSignal("relay_positive_channel", 0x90420),
    DiagnosticSignal("relay_negative_channel", 0x90421),
    DiagnosticSignal("precharge_timeout", 0x90479, scale=0.1, unit="s"),
    DiagnosticSignal("precharge_voltage_rate", 0x9047A),
    DiagnosticSignal("precharge_min_time", 0x9047C, scale=0.1, unit="s"),
    DiagnosticSignal("precharge_current_max", 0x9047D, scale=0.1, unit="A"),
)

POWER_DIAGNOSTIC_SIGNAL_IDS = tuple(
    dict.fromkeys(signal.data_id for signal in POWER_DIAGNOSTIC_SIGNAL_DEFINITIONS)
)
POWER_DIAGNOSTIC_CRITICAL_SIGNAL_IDS = (
    12,
    23,
    39,
    91,
    92,
    276,
    280,
    289,
    290,
    296,
    404,
    617,
    818,
    819,
    894,
    895,
    900,
    901,
    902,
    903,
    904,
    0x83001,
    0x83002,
    0x83004,
    0x8301B,
    0x8301C,
)
POWER_DIAGNOSTIC_STATIC_SIGNAL_IDS = tuple(
    data_id
    for data_id in POWER_DIAGNOSTIC_SIGNAL_IDS
    if data_id not in POWER_DIAGNOSTIC_CRITICAL_SIGNAL_IDS
)
POWER_DIAGNOSTIC_SIGNALS_BY_ID = {
    signal.data_id: signal for signal in POWER_DIAGNOSTIC_SIGNAL_DEFINITIONS
}

STATUS_LABELS = {
    "ok": "正常",
    "blocked": "阻断",
    "warning": "注意",
    "unknown": "待数据",
    "bypassed": "固件屏蔽",
}


def signed_u16(value):
    value = int(value) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def decode_signal_value(data_id, raw_word):
    signal = POWER_DIAGNOSTIC_SIGNALS_BY_ID.get(int(data_id))
    if signal is None:
        return int(raw_word) & 0xFFFF
    value = signed_u16(raw_word) if signal.signed else int(raw_word) & 0xFFFF
    return value * signal.scale


def _state_name(value):
    if value is None:
        return "--"
    value = int(value)
    return RUN_STATE_NAMES.get(value, f"未知({value})")


def _alarm_levels(word):
    if word is None:
        return None
    word = int(word) & 0xFFFF
    return {
        "discharge": word & 0x03,
        "common": (word >> 2) & 0x03,
        "charge": (word >> 4) & 0x03,
    }


def _alarm_summary(word):
    levels = _alarm_levels(word)
    if levels is None:
        return "--"
    return (
        f"放电L{levels['discharge']} / 通用L{levels['common']} / "
        f"充电L{levels['charge']}"
    )


def _cutoff_alarm(word):
    levels = _alarm_levels(word)
    if levels is None:
        return False
    return levels["common"] >= 2 or (
        levels["discharge"] >= 2 and levels["charge"] >= 2
    )


def _format_word(value, *, scale=1.0, unit="", signed=False):
    if value is None:
        return "--"
    number = signed_u16(value) if signed else int(value) & 0xFFFF
    number *= scale
    text = f"{number:g}" if isinstance(number, float) else str(number)
    return f"{text} {unit}".strip()


def _condition(category, name, value, status, evidence, advice, source):
    return {
        "category": category,
        "name": name,
        "value": value,
        "status": status,
        "status_text": STATUS_LABELS[status],
        "evidence": evidence,
        "advice": advice,
        "source": source,
    }


class PowerDiagnosticAnalyzer:
    """Interprets the effective 701 battery-management state-machine inputs."""

    def __init__(self, has_neutral=False):
        self.has_neutral = bool(has_neutral)

    def analyze(self, raw_values, now=None):
        raw = {int(key): int(value) & 0xFFFF for key, value in (raw_values or {}).items()}
        now = datetime.now() if now is None else now
        conditions = []

        def word(data_id):
            return raw.get(int(data_id))

        run_status = word(12)
        task_flag = word(23)
        conditions.append(
            _condition(
                "启动",
                "电池管理任务",
                _format_word(task_flag),
                "unknown" if task_flag is None else ("ok" if task_flag >= 4 else "blocked"),
                "VAR_SYS_TASK_RUN_FLAG >= BattManage_Task_Enable(4)",
                "检查采样、数据处理和告警任务是否依次完成初始化。",
                "Task_Batt_Manage.c:1228/3936",
            )
        )

        severe_ids = (894, 895) if self.has_neutral else (276,)
        severe_names = ("上半簇严重告警", "下半簇严重告警") if self.has_neutral else ("系统严重告警",)
        for data_id, name in zip(severe_ids, severe_names):
            severe = word(data_id)
            levels = _alarm_levels(severe)
            if severe is None:
                status = "unknown"
            elif _cutoff_alarm(severe) or levels["discharge"] >= 1:
                status = "blocked"
            elif any(levels.values()):
                status = "warning"
            else:
                status = "ok"
            conditions.append(
                _condition(
                    "告警",
                    name,
                    _alarm_summary(severe),
                    status,
                    "准备态要求放电方向等级为0；切断条件检查通用及充/放电方向等级。",
                    "转到实时告警页确认具体告警ID、等级和继电器关联。",
                    "Task_Batt_Manage.c:281-283/3970-3973",
                )
            )

        current_error = word(290)
        current_bits = None if current_error is None else current_error & 0x07
        conditions.append(
            _condition(
                "自检",
                "电流传感器",
                "--" if current_bits is None else f"故障位 0x{current_bits:X}",
                "unknown" if current_bits is None else ("ok" if current_bits == 0 else "blocked"),
                "VAR_SYS_CURR_SENSOR_ERROR & 0x07",
                "检查霍尔、分流器供电、采样线和传感器通信。",
                "Task_Batt_Manage_In_Interface.c:42-46",
            )
        )

        insulation = word(904)
        conditions.append(
            _condition(
                "自检",
                "绝缘检测完成",
                "--" if insulation is None else ("已完成" if insulation else "未完成"),
                "unknown" if insulation is None else ("ok" if insulation else "blocked"),
                "固件将 VAR_SYS_INSU_FINISH_FLAG == 0 作为自检失败。",
                "检查绝缘模块通信、测量流程和高压采样稳定性。",
                "Task_Batt_Manage_In_Interface.c:48-60/399-411",
            )
        )

        inner_fault = word(296)
        high_voltage_fault = None if inner_fault is None else (inner_fault >> 5) & 0x01
        conditions.append(
            _condition(
                "自检",
                "高压采样异常",
                "--" if high_voltage_fault is None else ("异常" if high_voltage_fault else "正常"),
                "unknown" if high_voltage_fault is None else ("blocked" if high_voltage_fault else "ok"),
                "VAR_SYS_INNER_FAULT bit5",
                "检查总压、母线电压采样及高压采样芯片状态。",
                "Task_Batt_Manage_In_Interface.c:119-123/470-474",
            )
        )

        stick_test = word(289)
        relay_commands = [word(47 + number) for number in range(1, 11)]
        feedback_words = [word(57 + number) for number in range(1, 11)]
        sticky = [index + 1 for index, value in enumerate(feedback_words) if value is not None and value & 0x0100]
        state_machine_sticky = [number for number in sticky if number <= 8]
        if stick_test is None:
            stick_status = "unknown"
        elif stick_test != 0xAAAA or state_machine_sticky:
            stick_status = "blocked"
        else:
            stick_status = "ok"
        relay_value = "--" if stick_test is None else f"索引289=0x{stick_test:04X}"
        if state_machine_sticky:
            relay_value += f" / 粘连 R{','.join(map(str, state_machine_sticky))}"
        conditions.append(
            _condition(
                "自检",
                "继电器粘连自检（索引289）",
                relay_value,
                stick_status,
                "状态机要求索引289为0xAAAA，并仅统计继电器1～8反馈高字节bit0粘连。",
                "检查粘连检测流程、继电器辅助触点和母线电压回采。",
                "Task_Batt_Manage.c:132-137; Task_Batt_Manage_In_Interface.c:890-903",
            )
        )

        feedback_bits = (
            (0x0001, "断线"),
            (0x0002, "对地短路"),
            (0x0004, "对电源短路"),
            (0x0008, "芯片反馈错误"),
            (0x0010, "其他驱动故障"),
            (0x0100, "粘连"),
            (0x0200, "无法闭合"),
            (0x0400, "异常断开"),
        )
        feedback_faults = []
        for number, value in enumerate(feedback_words, start=1):
            if value is None or value == 0:
                continue
            labels = [label for mask, label in feedback_bits if value & mask]
            detail = "/".join(labels) if labels else "未定义位"
            feedback_faults.append(f"R{number}=0x{value:04X}({detail})")
        if all(value is None for value in feedback_words):
            feedback_status = "unknown"
            feedback_value = "索引58～67未读取"
        elif feedback_faults:
            feedback_status = "warning"
            feedback_value = "；".join(feedback_faults)
        else:
            feedback_status = "ok"
            feedback_value = "索引58～67均为0x0000"
        conditions.append(
            _condition(
                "反馈",
                "继电器反馈诊断（索引58～67）",
                feedback_value,
                feedback_status,
                "低字节bit0～4依次为断线、对地短路、对电源短路、芯片错误、其他故障；高字节bit0～2依次为粘连、无法闭合、异常断开。",
                "结合对应继电器通道检查线圈、驱动输出和辅助触点；是否阻断上电由粘连自检及严重告警单独判定。",
                "Var_Macro.h:98-107; Task_Batt_Manage_In_Interface.c:890-903",
            )
        )

        active_relays = [
            index + 1
            for index, value in enumerate(relay_commands)
            if value is not None and value != 0
        ]
        channel_values = {
            "预充": word(0x9041F),
            "总正": word(0x90420),
            "总负": word(0x90421),
        }
        mapping_text = " / ".join(
            f"{name}=R{value}" for name, value in channel_values.items() if value not in (None, 0)
        )
        conditions.append(
            _condition(
                "继电器",
                "高压继电器命令",
                f"闭合 R{','.join(map(str, active_relays)) or '--'} / {mapping_text or '映射未读取'}",
                "unknown" if all(value is None for value in relay_commands) else "ok",
                "显示10路输出命令及预充、总正、总负参数映射。",
                "命令与反馈不一致时，检查继电器映射和输出驱动。",
                "Var_Macro.h:88-107; Par_Macro.h:140-142",
            )
        )

        breaker = word(39)
        if breaker is None:
            breaker_status = "unknown"
            breaker_text = "--"
        elif breaker > 0x3FFF:
            breaker_status = "ok"
            breaker_text = "闭合"
        elif breaker < 0x003F:
            breaker_status = "blocked"
            breaker_text = "断开"
        else:
            breaker_status = "warning"
            breaker_text = "不稳定"
        conditions.append(
            _condition(
                "高压允许",
                "断路器/脱扣器",
                f"{breaker_text} ({'--' if breaker is None else f'0x{breaker:04X}'})",
                breaker_status,
                "DI4 > 0x3FFF为闭合，DI4 < 0x003F为断开。",
                "确认断路器机械位置、DI4接线和输入滤波状态。",
                "Task_Batt_Manage_In_Interface.c:212-228",
            )
        )

        address = word(28)
        address_valid = address is not None and 0xA0 <= address <= 0xBF
        conditions.append(
            _condition(
                "编址",
                "BCU编址",
                "--" if address is None else f"0x{address:02X}",
                "unknown" if address is None else ("ok" if address_valid else "bypassed"),
                "701固件 Get_BcuAddrSt 在范围判断后直接 return TRUE。",
                "仍建议修正编址至0xA0-0xBF，当前固件不会以此阻断上电。",
                "Task_Batt_Manage_In_Interface.c:230-245",
            )
        )

        csu = word(404)
        conditions.append(
            _condition(
                "编址",
                "CSU编址",
                "--" if csu is None else f"状态 0x{csu:04X}",
                "unknown" if csu is None else ("ok" if (csu & 0xFF) == 1 else "warning"),
                "低字节1表示编址、通信和总压校验完成。",
                "检查失败位置、CSU通信和分段总压；当前生成状态机未直接引用此项。",
                "Task_Batt_Manage_In_Interface.c:200-208",
            )
        )

        hvil = word(280)
        conditions.append(
            _condition(
                "高压允许",
                "HVIL互锁",
                "--" if hvil is None else ("故障" if hvil else "正常"),
                "unknown" if hvil is None else ("ok" if hvil == 0 else "bypassed"),
                "701固件读取HVIL后提前 return false，当前不参与状态机阻断。",
                "即使固件屏蔽，现场仍应检查互锁回路并评估恢复该保护。",
                "Task_Batt_Manage_In_Interface.c:125-131/476-482",
            )
        )

        self._append_precharge_conditions(raw, conditions)

        blocked = [item for item in conditions if item["status"] == "blocked"]
        warning = [item for item in conditions if item["status"] in ("warning", "bypassed")]
        bypassed = [item for item in conditions if item["status"] == "bypassed"]
        unknown = [item for item in conditions if item["status"] == "unknown"]
        if run_status in {4, 5, 6, 7, 8}:
            summary_status = "ok"
            summary_title = "系统已处于高压运行状态"
        elif run_status == 3:
            summary_status = "warning" if not blocked else "blocked"
            summary_title = "系统正在预充" if not blocked else "预充被条件阻断"
        elif blocked:
            summary_status = "blocked"
            summary_title = f"无法上电：{blocked[0]['name']}"
        elif unknown:
            summary_status = "unknown"
            summary_title = "等待诊断数据完整"
        else:
            summary_status = "warning" if warning else "ok"
            if not warning:
                summary_title = "具备上电条件"
            elif bypassed:
                summary_title = "具备条件，存在固件屏蔽项"
            else:
                summary_title = "具备条件，存在注意项"

        shutdown_reasons = self.shutdown_reasons(raw)
        return {
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "run_status": run_status,
            "run_status_name": _state_name(run_status),
            "summary_status": summary_status,
            "summary_title": summary_title,
            "primary_reason": blocked[0]["evidence"] if blocked else "",
            "blocked_count": len(blocked),
            "warning_count": len(warning),
            "unknown_count": len(unknown),
            "conditions": conditions,
            "shutdown_status": "abnormal" if run_status in (9, 10) else "normal",
            "shutdown_title": shutdown_reasons[0] if shutdown_reasons else "未发现异常下电证据",
            "shutdown_reasons": shutdown_reasons,
            "firmware_source": "701/01.bcu_app_01v01",
        }

    def _append_precharge_conditions(self, raw, conditions):
        mode = raw.get(0x90479)
        rate = raw.get(0x9047A)
        min_time = raw.get(0x9047C)
        max_current = raw.get(0x9047D)
        current = raw.get(617)
        if current is None:
            candidates = [raw.get(818), raw.get(819)]
            signed_values = [abs(signed_u16(value)) for value in candidates if value is not None]
            current = max(signed_values) if signed_values else None

        pairs = (
            ((900, 902, "上半簇"), (901, 903, "下半簇"))
            if self.has_neutral
            else ((91, 92, "整簇"),)
        )
        for battery_id, pack_id, label in pairs:
            battery = raw.get(battery_id)
            pack = raw.get(pack_id)
            if mode is None:
                status = "unknown"
                value = "参数未读取"
                evidence = "等待预充参数。"
            elif mode == 0:
                status = "ok"
                value = "预充已禁用"
                evidence = "PAR_SYS_PRECHARGE_MODE == 0，状态机直接闭合高压继电器。"
            elif None in (rate, max_current, battery, pack, current):
                status = "unknown"
                value = "电压/电流数据不完整"
                evidence = "等待总压、母线电压、预充阈值和电流限制。"
            else:
                threshold = rate & 0x7FFF
                delta = abs(int(battery) - int(pack))
                allowed = threshold if rate & 0x8000 else int(battery) * threshold / 1000.0
                voltage_ok = battery > 100 and pack > 100 and delta <= allowed
                current_ok = current < max_current
                status = "ok" if voltage_ok and current_ok else "blocked"
                value = (
                    f"B={battery / 10:g} V, P={pack / 10:g} V, "
                    f"差={delta / 10:g} V, 电流={current / 10:g} A"
                )
                evidence = (
                    f"允许压差 {allowed / 10:g} V；电流上限 {max_current / 10:g} A；"
                    f"最大时间 {mode / 10:g} s；最小时间 "
                    f"{'--' if min_time is None else f'{min_time / 10:g} s'}。"
                )
            conditions.append(
                _condition(
                    "预充",
                    f"{label}预充完成条件",
                    value,
                    status,
                    evidence,
                    "检查预充继电器、母线负载、总压采样、预充电阻和回路电流。",
                    "Task_Batt_Manage.c:917-1033/3628-3739",
                )
            )

    def shutdown_reasons(self, raw_values):
        raw = {int(key): int(value) & 0xFFFF for key, value in (raw_values or {}).items()}
        reasons = []
        severe_ids = (894, 895) if self.has_neutral else (276,)
        if any(_cutoff_alarm(raw.get(data_id)) for data_id in severe_ids):
            reasons.append("严重告警达到状态机切断条件")
        breaker = raw.get(39)
        if breaker is not None and breaker < 0x003F:
            reasons.append("断路器/脱扣器反馈为断开")
        abnormal_relays = [
            number
            for number in range(1, 11)
            if raw.get(57 + number) is not None and raw[57 + number] & 0x0400
        ]
        if abnormal_relays:
            reasons.append(f"继电器异常断开 R{','.join(map(str, abnormal_relays))}")
        if raw.get(296) is not None and (raw[296] >> 5) & 0x01:
            reasons.append("高压采样异常")
        if raw.get(290) is not None and raw[290] & 0x07:
            reasons.append("电流传感器故障")
        if raw.get(904) == 0:
            reasons.append("绝缘检测未完成")
        if raw.get(280):
            reasons.append("HVIL互锁故障（701固件状态机当前屏蔽）")
        return reasons

    def build_transition_event(self, previous_state, current_state, raw_values, when=None):
        if previous_state is None or current_state is None:
            return None
        previous_state = int(previous_state)
        current_state = int(current_state)
        if previous_state == current_state:
            return None
        if previous_state not in HIGH_VOLTAGE_STATES or current_state not in POWER_DOWN_STATES:
            return None

        raw = {int(key): int(value) & 0xFFFF for key, value in (raw_values or {}).items()}
        when = datetime.now() if when is None else when
        request_values = [raw.get(0x83002), raw.get(0x8301B), raw.get(0x8301C)]
        requested = bool(raw.get(0x83004)) or any(value == 2 for value in request_values)
        reasons = self.shutdown_reasons(raw)
        if previous_state == 3 and current_state in (2, 9, 10):
            reasons.insert(0, "预充未完成或预充超时")
        if reasons or current_state in (9, 10):
            event_type = "异常下电"
            severity = "danger"
            cause = reasons[0] if reasons else f"状态机进入{_state_name(current_state)}"
        elif requested:
            event_type = "正常请求下电"
            severity = "normal"
            cause = "VMS关机/断开继电器请求"
        else:
            event_type = "非预期状态回退"
            severity = "warning"
            cause = "未捕获到明确请求或故障证据"
        return {
            "time": when.strftime("%Y-%m-%d %H:%M:%S"),
            "previous_state": previous_state,
            "current_state": current_state,
            "transition": f"{_state_name(previous_state)} -> {_state_name(current_state)}",
            "type": event_type,
            "severity": severity,
            "cause": cause,
            "evidence": "；".join(reasons) if reasons else "--",
        }
