"""703 firmware cluster-overview broadcast and index decoding."""


RUN_STATUS_TEXT = {
    0: "初始",
    1: "自测",
    2: "准备",
    3: "预充",
    4: "高压待机",
    5: "放电",
    6: "充电",
    7: "放空",
    8: "充满",
    9: "错误",
    10: "切断",
    11: "休眠",
}


CLUSTER_OVERVIEW_INDEX_IDS = (
    12,   # VAR_SYS_RUN_STATUS
    14,   # VAR_SYS_CURR
    16,   # VAR_SYS_SOC
    17,   # VAR_SYS_SOH
    18,   # VAR_SYS_DIS_SOC
    91,   # VAR_SYS_ANALOG_BAT_VOLT
    92,   # VAR_SYS_ANALOG_PACK_VOLT
    321,  # VAR_SYS_DIFF_VOLT
    322,  # VAR_SYS_DIFF_TEMP
    323,  # VAR_SYS_AVG_VOLT
    324,  # VAR_SYS_AVG_TEMP
    325,  # VAR_SYS_ONLINE_LECU_NUM
    328,  # VAR_SYS_CELL_VOLT_MAX
    329,  # VAR_SYS_MAXV_POSI
    331,  # VAR_SYS_CELL_VOLT_MIN
    332,  # VAR_SYS_MINV_POSI
    334,  # VAR_SYS_CELL_TEMP_MAX
    335,  # VAR_SYS_MAXT_POSI
    337,  # VAR_SYS_CELL_TEMP_MIN
    338,  # VAR_SYS_MINT_POSI
)


def _u16(data, offset):
    return int(data[offset]) | (int(data[offset + 1]) << 8)


def _s16(data, offset):
    value = _u16(data, offset)
    return value - 0x10000 if value & 0x8000 else value


def _u32(data, offset):
    return _u16(data, offset) | (_u16(data, offset + 2) << 16)


def _position_text(value):
    value = int(value or 0) & 0xFFFF
    module = (value >> 8) & 0xFF
    channel = value & 0xFF
    if module == 0 and channel == 0:
        return "--"
    return f"模组{module} / 点位{channel}"


def _active_labels(mask, prefix, count):
    labels = [f"{prefix}{index + 1}" for index in range(count) if mask & (1 << index)]
    return "、".join(labels) if labels else "无"


class ClusterOverviewDecoder:
    """Decode the BAU broadcast frames defined by 703 ``BAU_Comm.c``."""

    def __init__(self, has_neutral=False):
        self.has_neutral = bool(has_neutral)

    def set_has_neutral(self, has_neutral):
        self.has_neutral = bool(has_neutral)

    def decode_broadcast(self, frame_id, payload):
        data = bytes(payload or b"")
        if len(data) < 8:
            return {}
        key = int(frame_id) & 0xFFFFFF00
        decoder = getattr(self, f"_decode_{key:08x}", None)
        return decoder(data) if decoder is not None else {}

    def decode_index(self, data_id, raw_word):
        data_id = int(data_id)
        raw_word = int(raw_word) & 0xFFFF
        signed = raw_word - 0x10000 if raw_word & 0x8000 else raw_word
        mapping = {
            12: ("run_status", raw_word),
            14: ("system_current", signed / 10.0),
            16: ("soc", raw_word / 10.0),
            17: ("soh", raw_word / 10.0),
            18: ("display_soc", raw_word / 10.0),
            91: ("battery_voltage", raw_word / 10.0),
            92: ("pack_voltage", raw_word / 10.0),
            321: ("voltage_delta", raw_word),
            322: ("temperature_delta", signed / 10.0),
            323: ("average_cell_voltage", raw_word),
            324: ("average_cell_temperature", signed / 10.0),
            325: ("online_module_count", raw_word),
            328: ("max_cell_voltage", raw_word),
            329: ("max_cell_voltage_position", _position_text(raw_word)),
            331: ("min_cell_voltage", raw_word),
            332: ("min_cell_voltage_position", _position_text(raw_word)),
            334: ("max_cell_temperature", signed / 10.0),
            335: ("max_cell_temperature_position", _position_text(raw_word)),
            337: ("min_cell_temperature", signed / 10.0),
            338: ("min_cell_temperature_position", _position_text(raw_word)),
        }
        item = mapping.get(data_id)
        return {item[0]: item[1]} if item is not None else {}

    def display_snapshot(self, snapshot):
        result = dict(snapshot or {})
        if self.has_neutral:
            upper_soc = result.get("upper_soc")
            lower_soc = result.get("lower_soc")
            if isinstance(upper_soc, (int, float)) and isinstance(lower_soc, (int, float)):
                result["soc"] = (upper_soc + lower_soc) / 2.0
            result["run_status"] = result.get("upper_run_status", result.get("lower_run_status"))
            result["system_current"] = result.get("hall_current", result.get("shunt_current"))
            upper_allow = result.get("upper_allow_high_voltage")
            lower_allow = result.get("lower_allow_high_voltage")
            if upper_allow is not None and lower_allow is not None:
                result["allow_high_voltage"] = bool(upper_allow and lower_allow)
            result["full_charge_discharge"] = max(
                int(result.get("upper_full_charge_discharge", 0) or 0),
                int(result.get("lower_full_charge_discharge", 0) or 0),
            )
            for suffix in (
                "remaining_charge_energy",
                "remaining_discharge_energy",
                "single_charge_energy",
                "single_discharge_energy",
            ):
                upper = result.get(f"upper_{suffix}")
                lower = result.get(f"lower_{suffix}")
                if isinstance(upper, (int, float)) and isinstance(lower, (int, float)):
                    result[suffix] = upper + lower
            result["max_charge_current"] = min(
                value
                for value in (
                    result.get("upper_max_charge_current"),
                    result.get("lower_max_charge_current"),
                )
                if isinstance(value, (int, float))
            ) if any(
                isinstance(value, (int, float))
                for value in (
                    result.get("upper_max_charge_current"),
                    result.get("lower_max_charge_current"),
                )
            ) else None
            result["max_discharge_current"] = min(
                value
                for value in (
                    result.get("upper_max_discharge_current"),
                    result.get("lower_max_discharge_current"),
                )
                if isinstance(value, (int, float))
            ) if any(
                isinstance(value, (int, float))
                for value in (
                    result.get("upper_max_discharge_current"),
                    result.get("lower_max_discharge_current"),
                )
            ) else None
        result["alarm_level"] = max(
            int(result.get("upper_alarm_level", 0) or 0),
            int(result.get("lower_alarm_level", 0) or 0),
        )
        bounded_fields = {
            "run_status": (0, 11),
            "soc": (0, 100),
            "display_soc": (0, 100),
            "soh": (0, 200),
            "system_current": (-5000, 5000),
            "hall_current": (-5000, 5000),
            "shunt_current": (-5000, 5000),
            "battery_voltage": (0, 2000),
            "pack_voltage": (0, 2000),
            "upper_battery_voltage": (0, 2000),
            "upper_pack_voltage": (0, 2000),
            "lower_battery_voltage": (0, 2000),
            "lower_pack_voltage": (0, 2000),
            "max_cell_voltage": (0, 6000),
            "min_cell_voltage": (0, 6000),
            "average_cell_voltage": (0, 6000),
            "upper_max_cell_voltage": (0, 6000),
            "upper_min_cell_voltage": (0, 6000),
            "lower_max_cell_voltage": (0, 6000),
            "lower_min_cell_voltage": (0, 6000),
            "max_cell_temperature": (-100, 200),
            "min_cell_temperature": (-100, 200),
            "average_cell_temperature": (-100, 200),
            "max_terminal_temperature": (-100, 200),
            "alarm_level": (0, 5),
        }
        for key, (minimum, maximum) in bounded_fields.items():
            value = result.get(key)
            if isinstance(value, (int, float)) and not minimum <= value <= maximum:
                result[key] = None
        return result

    def _decode_1201ef00(self, data):
        if self.has_neutral:
            return {
                "upper_battery_voltage": _u16(data, 0) / 10.0,
                "hall_current": _s16(data, 2) / 10.0,
                "upper_run_status": data[4],
                "lower_run_status": data[5],
                "upper_pack_voltage": _u16(data, 6) / 10.0,
            }
        return {
            "battery_voltage": _u16(data, 0) / 10.0,
            "system_current": _s16(data, 2) / 10.0,
            "run_status": data[4],
            "insulation_finished": bool(data[5]),
        }

    def _decode_1301ef00(self, data):
        if not self.has_neutral:
            return {}
        return {
            "lower_battery_voltage": _u16(data, 0) / 10.0,
            "shunt_current": _s16(data, 2) / 10.0,
            "battery_voltage": _u16(data, 4) / 10.0,
            "lower_pack_voltage": _u16(data, 6) / 10.0,
        }

    def _decode_1202ef00(self, data):
        prefix = "upper_" if self.has_neutral else ""
        return {
            "positive_insulation_resistance": _u16(data, 0) / 10.0,
            "negative_insulation_resistance": _u16(data, 2) / 10.0,
            f"{prefix}allow_high_voltage": bool(data[4]),
            f"{prefix}full_charge_discharge": data[5],
            f"{prefix}soc": _u16(data, 6) / 10.0,
        }

    def _decode_1302ef00(self, data):
        if not self.has_neutral:
            return {}
        return {
            "positive_insulation_resistance": _u16(data, 0) / 10.0,
            "negative_insulation_resistance": _u16(data, 2) / 10.0,
            "lower_allow_high_voltage": bool(data[4]),
            "lower_full_charge_discharge": data[5],
            "lower_soc": _u16(data, 6) / 10.0,
        }

    def _decode_1203ef00(self, data):
        result = {
            "soh": _u16(data, 0) / 10.0,
            "pack_voltage": _u16(data, 4) / 10.0,
        }
        prefix = "upper_" if self.has_neutral else ""
        result[f"{prefix}max_cell_voltage"] = _u16(data, 2)
        result[f"{prefix}min_cell_voltage"] = _u16(data, 6)
        return result

    def _energy_side(self, data, prefix):
        return {
            f"{prefix}remaining_charge_energy": _u16(data, 0) / 100.0,
            f"{prefix}remaining_discharge_energy": _u16(data, 2) / 100.0,
            f"{prefix}single_charge_energy": _u16(data, 4) / 100.0,
            f"{prefix}single_discharge_energy": _u16(data, 6) / 100.0,
        }

    def _decode_1204ef00(self, data):
        return self._energy_side(data, "upper_" if self.has_neutral else "")

    def _decode_1304ef00(self, data):
        return self._energy_side(data, "lower_") if self.has_neutral else {}

    def _decode_1205ef00(self, data):
        return {
            "total_charge_energy": _u32(data, 0) / 10.0,
            "total_discharge_energy": _u32(data, 4) / 10.0,
        }

    def _decode_1206ef00(self, data):
        result = {
            "charge_cycle_count": _u16(data, 0),
            "rated_capacity": _u16(data, 6) / 10.0,
        }
        if self.has_neutral:
            result["lower_max_cell_voltage"] = _u16(data, 2)
            result["lower_min_cell_voltage"] = _u16(data, 4)
        return result

    def _current_limit_side(self, data, prefix):
        return {
            f"{prefix}max_charge_current": _u16(data, 0) / 10.0,
            f"{prefix}max_discharge_current": _u16(data, 2) / 10.0,
            f"{prefix}remaining_charge_time": _u16(data, 4),
        }

    def _decode_1207ef00(self, data):
        return self._current_limit_side(data, "upper_" if self.has_neutral else "")

    def _decode_1307ef00(self, data):
        return self._current_limit_side(data, "lower_") if self.has_neutral else {}

    def _decode_1208ef00(self, data):
        return {
            "valid_cell_voltage_count": _u16(data, 0),
            "valid_cell_temperature_count": _u16(data, 2),
            "online_module_count": _u16(data, 4),
            "configured_cell_count": _u16(data, 6),
        }

    def _decode_1209ef00(self, data):
        return {
            "max_cell_voltage": _u16(data, 0),
            "min_cell_voltage": _u16(data, 2),
            "max_cell_voltage_position": _position_text(_u16(data, 4)),
            "min_cell_voltage_position": _position_text(_u16(data, 6)),
        }

    def _decode_120aef00(self, data):
        return {
            "max_cell_temperature": _s16(data, 0) / 10.0,
            "min_cell_temperature": _s16(data, 2) / 10.0,
            "max_cell_temperature_position": _position_text(_u16(data, 4)),
            "min_cell_temperature_position": _position_text(_u16(data, 6)),
        }

    def _decode_120bef00(self, data):
        return {
            "average_cell_voltage": _u16(data, 0),
            "average_cell_temperature": _s16(data, 2) / 10.0,
            "remaining_discharge_time": _u16(data, 4),
        }

    def _decode_120cef00(self, data):
        di_mask = _u16(data, 2)
        fire_mask = _u16(data, 4)
        return {
            "max_terminal_temperature": _s16(data, 0) / 10.0,
            "di_mask": di_mask,
            "di_active_text": _active_labels(di_mask, "DI", 12),
            "fire_module_mask": fire_mask,
            "fire_module_text": _active_labels(fire_mask, "模组", 16),
            "max_terminal_temperature_position": _position_text(_u16(data, 6)),
        }

    def _decode_1228ef00(self, data):
        return {
            "upper_alarm_level": _u16(data, 0),
            "lower_alarm_level": _u16(data, 2),
            "history_log_count": _u16(data, 4),
            "active_alarm_count": _u16(data, 6),
        }
