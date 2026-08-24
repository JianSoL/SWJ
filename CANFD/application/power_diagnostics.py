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
    DiagnosticSignal("system_current", 14, signed=True, scale=0.1, unit="A"),
    DiagnosticSignal("task_run_flag", 23),
    DiagnosticSignal("addressing_addr", 28),
    DiagnosticSignal("main_positive_di", 36),
    DiagnosticSignal("main_negative_di", 37),
    *(DiagnosticSignal(f"relay{number}_status", 47 + number) for number in range(1, 11)),
    *(DiagnosticSignal(f"relay{number}_feedback", 57 + number) for number in range(1, 11)),
    DiagnosticSignal("battery_voltage", 91, scale=0.1, unit="V"),
    DiagnosticSignal("pack_voltage", 92, scale=0.1, unit="V"),
    DiagnosticSignal("severe_level", 276),
    DiagnosticSignal("precharge_error", 279),
    DiagnosticSignal("hvil_fault", 280),
    DiagnosticSignal("insulation_fault", 282),
    DiagnosticSignal("relay_close_fail", 288),
    DiagnosticSignal("relay_stick_test", 289),
    DiagnosticSignal("current_sensor_error", 290),
    DiagnosticSignal("inner_fault", 296),
    DiagnosticSignal("bcu_hv_request", 632),
    DiagnosticSignal("insulation_finished", 791),
    DiagnosticSignal("vms_ctrl_relay_req", 0x83002),
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
POWER_DIAGNOSTIC_SIGNALS_BY_ID = {
    signal.data_id: signal for signal in POWER_DIAGNOSTIC_SIGNAL_DEFINITIONS
}

_poll_sequence = []
for _offset, _data_id in enumerate(POWER_DIAGNOSTIC_SIGNAL_IDS):
    if _offset and _offset % 5 == 0:
        _poll_sequence.append(12)
    _poll_sequence.append(_data_id)
POWER_DIAGNOSTIC_POLL_SEQUENCE = tuple(_poll_sequence)

STATUS_LABELS = {
    "ok": "正常",
    "blocked": "阻断",
    "warning": "注意",
    "unknown": "待数据",
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


def _vms_request(raw_word):
    return None if raw_word is None else (int(raw_word) >> 8) & 0xFF


def _severe_levels(raw_word):
    if raw_word is None:
        return None
    state_word = (int(raw_word) >> 8) & 0x7F
    return {
        "discharge": state_word & 0x03,
        "common": (state_word >> 2) & 0x03,
        "charge": (state_word >> 4) & 0x03,
    }


def _severe_summary(raw_word):
    levels = _severe_levels(raw_word)
    if levels is None:
        return "--"
    display_level = int(raw_word) & 0xFF
    return (
        f"显示L{display_level} / 放电L{levels['discharge']} / "
        f"通用L{levels['common']} / 充电L{levels['charge']}"
    )


def _severe_blocks(raw_word):
    levels = _severe_levels(raw_word)
    return bool(levels and any(levels.values()))


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
    """Interprets the BCU615 power state-machine inputs and outputs."""

    firmware_source = "BCU615/06.bcu_app_02v01"

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
                "--" if task_flag is None else str(task_flag),
                "unknown" if task_flag is None else ("ok" if task_flag >= 4 else "blocked"),
                "VAR_SYS_TASK_RUN_FLAG >= BattManage_Task_Enable(4) 后进入自检。",
                "检查采样、数据处理和告警任务初始化顺序。",
                "Task_Batt_Manage.c:1703-1712",
            )
        )

        request = _vms_request(word(0x83002))
        request_names = {0: "无请求", 1: "请求上电", 2: "请求下电", 3: "请求休眠"}
        request_status = "unknown" if request is None else "ok"
        if request == 0 and run_status in (1, 2):
            request_status = "warning"
        conditions.append(
            _condition(
                "请求",
                "VMS上下电请求",
                "--" if request is None else request_names.get(request, f"未知({request})"),
                request_status,
                "VAR_VMS_CTRL_RELAY_REQ高字节：1上电、2下电、3休眠。",
                "无上电请求时检查BAU/VMS控制报文及转发链路。",
                "Task_Batt_Manage_In_Interface.c:29-33",
            )
        )

        insulation_finished = word(791)
        conditions.append(
            _condition(
                "自检",
                "绝缘检测完成",
                "--" if insulation_finished is None else ("已完成" if insulation_finished else "未完成"),
                "unknown" if insulation_finished is None else ("ok" if insulation_finished else "blocked"),
                "VAR_SYS_INSU_FINISH_FLAG为0时，PowOnSelfCheck判定自检失败。",
                "检查绝缘模块通信、测量流程和绝缘检测完成标志。",
                "Task_Batt_Manage_In_Interface.c:153-166; Task_Batt_Manage.c:1420-1454",
            )
        )

        conditions.append(
            _condition(
                "自检",
                "通用告警自检接口",
                "当前固件返回FALSE",
                "warning",
                "Get_ALARM_DISABLE_TO_RUN在Alm_DisableToRunSys调用前直接return FALSE。",
                "发布前确认是否需要恢复告警阻断接口；当前状态机自检不会由该接口阻断。",
                "Task_Batt_Manage_In_Interface.c:143-149",
            )
        )

        severe = word(276)
        conditions.append(
            _condition(
                "告警",
                "状态机最严重告警",
                _severe_summary(severe),
                "unknown" if severe is None else ("blocked" if _severe_blocks(severe) else "ok"),
                "状态机使用索引276高字节方向等级；当前充放电命令接口返回0，任一方向等级>=1均会切断。",
                "转到告警状态页确认具体告警ID、等级及继电器关联。",
                "Task_Batt_Manage_In_Interface.c:127-140; Task_Batt_Manage.c:1865-1879",
            )
        )

        main_negative = word(37)
        if main_negative is None:
            relay_status = "unknown"
            relay_text = "--"
        elif main_negative > 0x3FFF:
            relay_status = "ok"
            relay_text = "闭合"
        elif main_negative < 0x003F:
            relay_status = "blocked" if request == 1 and run_status == 2 else "warning"
            relay_text = "断开"
        else:
            relay_status = "warning"
            relay_text = "不稳定"
        conditions.append(
            _condition(
                "继电器",
                "主负反馈（DI2）",
                f"{relay_text} ({'--' if main_negative is None else f'0x{main_negative:04X}'})",
                relay_status,
                "准备态收到上电请求后先闭合主负，DI2有效后才能进入预充判断。",
                "检查主负接触器、辅助触点、DI2接线和输入滤波。",
                "Task_Batt_Manage_In_Interface.c:73-125; Task_Batt_Manage.c:210-255",
            )
        )

        feedback_words = [word(57 + number) for number in range(1, 11)]
        feedback_faults = []
        for number, value in enumerate(feedback_words, start=1):
            if value:
                feedback_faults.append(f"R{number}=0x{value:04X}")
        conditions.append(
            _condition(
                "反馈",
                "继电器驱动与高压侧诊断",
                "；".join(feedback_faults) if feedback_faults else (
                    "全部正常" if any(value is not None for value in feedback_words) else "--"
                ),
                "unknown" if all(value is None for value in feedback_words) else (
                    "warning" if feedback_faults else "ok"
                ),
                "索引58~67低字节为驱动故障，高字节为粘连/无法闭合/异常断开。",
                "结合继电器通道映射检查线圈、驱动输出和辅助触点。",
                "Var_Macro.h:98-107",
            )
        )

        current_error = word(290)
        conditions.append(
            _condition(
                "采样",
                "电流传感器",
                "--" if current_error is None else f"故障位 0x{current_error:04X}",
                "unknown" if current_error is None else ("warning" if current_error else "ok"),
                "索引290记录分流器/HALL断线、温度、零点及量程故障。",
                "检查分流器、HALL供电、采样线和零点标定。",
                "Var_Macro.h:330",
            )
        )

        self._append_precharge_condition(raw, conditions, run_status)

        hvil = word(280)
        conditions.append(
            _condition(
                "互锁",
                "HVIL高压互锁",
                "--" if hvil is None else ("正常" if hvil == 0 else f"故障位 0x{hvil:04X}"),
                "unknown" if hvil is None else ("warning" if hvil else "ok"),
                "索引280记录HVIL故障，但当前Batt_Manage输入接口未直接引用该变量。",
                "即使未直接阻断状态机，也应按高压安全要求检查互锁回路。",
                "Var_Macro.h:325; Task_Batt_Manage_In_Interface.h",
            )
        )

        bcu_request = word(632)
        bcu_request_names = {0: "默认", 1: "BCU请求上电", 2: "BCU请求下电", 3: "BCU请求休眠"}
        conditions.append(
            _condition(
                "输出",
                "BCU上下电请求",
                "--" if bcu_request is None else bcu_request_names.get(bcu_request, f"未知({bcu_request})"),
                "unknown" if bcu_request is None else "ok",
                "状态机通过索引632向外输出BCU上下电请求。",
                "与VMS请求和实际继电器状态不一致时检查状态机流转。",
                "Task_Batt_Manage_Out_Interface.c:61-64",
            )
        )

        blocked = [item for item in conditions if item["status"] == "blocked"]
        warnings = [item for item in conditions if item["status"] == "warning"]
        unknown = [item for item in conditions if item["status"] == "unknown"]
        if run_status in {4, 5, 6, 7, 8}:
            summary_status = "ok"
            summary_title = "BCU处于高压运行状态"
        elif run_status == 3:
            summary_status = "blocked" if blocked else "warning"
            summary_title = "预充异常" if blocked else "BCU正在预充"
        elif blocked:
            summary_status = "blocked"
            summary_title = f"上电受阻：{blocked[0]['name']}"
        elif unknown:
            summary_status = "unknown"
            summary_title = "等待诊断数据完整"
        else:
            summary_status = "warning" if warnings else "ok"
            summary_title = "具备上电条件" if not warnings else "具备条件，存在注意项"

        shutdown_reasons = self.shutdown_reasons(raw)
        normal_shutdown = request in (2, 3)
        shutdown_abnormal = run_status in (9, 10) and not normal_shutdown
        return {
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "run_status": run_status,
            "run_status_name": _state_name(run_status),
            "summary_status": summary_status,
            "summary_title": summary_title,
            "primary_reason": blocked[0]["evidence"] if blocked else "",
            "blocked_count": len(blocked),
            "warning_count": len(warnings),
            "unknown_count": len(unknown),
            "conditions": conditions,
            "shutdown_status": "abnormal" if shutdown_abnormal else "normal",
            "shutdown_title": shutdown_reasons[0] if shutdown_reasons else "未发现异常下电证据",
            "shutdown_reasons": shutdown_reasons,
            "firmware_source": self.firmware_source,
        }

    def _append_precharge_condition(self, raw, conditions, run_status):
        mode = raw.get(0x90479)
        rate = raw.get(0x9047A)
        min_time = raw.get(0x9047C)
        max_current = raw.get(0x9047D)
        battery = raw.get(91)
        pack = raw.get(92)
        current = None if raw.get(14) is None else abs(signed_u16(raw[14]))
        precharge_error = raw.get(279)

        if precharge_error:
            status = "blocked"
            value = "预充失败"
            evidence = "VAR_SYS_PRECHRG_EEROR != 0。"
        elif mode is None:
            status = "unknown"
            value = "参数未读取"
            evidence = "等待预充参数。"
        elif mode == 0:
            status = "ok"
            value = "预充已禁用"
            evidence = "PAR_SYS_PRECHARGE_MODE == 0，状态机满足条件时直接进入高压待机。"
        elif None in (rate, max_current, battery, pack, current):
            status = "unknown"
            value = "电压/电流数据不完整"
            evidence = "等待B端、P端电压及预充电流限制。"
        else:
            threshold = rate & 0x7FFF
            difference_mode = bool(rate & 0x8000)
            if difference_mode:
                voltage_ok = (
                    battery > 100 and pack > 100 and abs(battery - pack) < threshold
                )
                threshold_text = f"压差 < {threshold / 10:g} V"
            else:
                voltage_ok = (
                    battery > 100 and pack > 100 and pack > threshold * battery / 100.0
                )
                threshold_text = f"P端 > B端的 {threshold:g}%"
            current_ok = current < max_current
            complete = voltage_ok and current_ok
            status = "ok" if complete else ("warning" if run_status == 3 else "blocked")
            value = (
                f"B={battery / 10:g} V / P={pack / 10:g} V / "
                f"I={current / 10:g} A"
            )
            evidence = (
                f"{threshold_text}，电流 < {max_current / 10:g} A；"
                f"最小时间 {'--' if min_time is None else f'{min_time / 10:g} s'}，"
                f"最大时间 {mode / 10:g} s。"
            )

        conditions.append(
            _condition(
                "预充",
                "预充完成条件",
                value,
                status,
                evidence,
                "检查预充继电器、主负反馈、母线负载、总压采样、预充电阻和回路电流。",
                "Task_Batt_Manage.c:1143-1251",
            )
        )

    def shutdown_reasons(self, raw_values):
        raw = {int(key): int(value) & 0xFFFF for key, value in (raw_values or {}).items()}
        reasons = []
        request = _vms_request(raw.get(0x83002))
        if request == 2:
            reasons.append("VMS请求正常下电")
        elif request == 3:
            reasons.append("VMS请求休眠")
        if _severe_blocks(raw.get(276)):
            reasons.append("状态机最严重告警达到切断条件")
        if raw.get(279):
            reasons.append("预充失败或预充超时")
        abnormal_relays = [
            number
            for number in range(1, 11)
            if raw.get(57 + number) is not None and raw[57 + number] & 0x0400
        ]
        if abnormal_relays:
            reasons.append(f"继电器异常断开 R{','.join(map(str, abnormal_relays))}")
        if raw.get(280):
            reasons.append("HVIL互锁故障")
        if raw.get(296) is not None and raw[296] & (1 << 6):
            reasons.append("内部故障记录异常下电")
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
        request = _vms_request(raw.get(0x83002))
        reasons = self.shutdown_reasons(raw)
        abnormal_reasons = [
            reason for reason in reasons if not reason.startswith("VMS请求")
        ]
        if previous_state == 3 and current_state in (2, 9, 10):
            abnormal_reasons.insert(0, "预充未完成或预充超时")
        if abnormal_reasons or current_state in (9, 10) and request not in (2, 3):
            event_type = "异常下电"
            severity = "danger"
            cause = abnormal_reasons[0] if abnormal_reasons else f"状态机进入{_state_name(current_state)}"
        elif request in (2, 3):
            event_type = "正常请求下电"
            severity = "normal"
            cause = "VMS下电请求" if request == 2 else "VMS休眠请求"
        else:
            event_type = "非预期状态回退"
            severity = "warning"
            cause = "未捕获到明确下电请求或故障证据"
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
