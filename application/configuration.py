import json
from pathlib import Path
import sys


DEFAULT_CAN_BOARD_CONFIG = {
    "can_type": "usb_can_2eu",
    "can_idx": 0,
    "chn": 1,
    "baud_rate": 500,
    "Has_N": 0,
    "BCU_NUM": 2,
    "LECU_NUM": 6,
    "CELL_NUM": 16,
    "CELL_Tem_NUM": 16,
}

RUNTIME_SYSTEM_CONFIG_KEYS = (
    "BCU_NUM",
    "LECU_NUM",
    "CELL_NUM",
    "CELL_Tem_NUM",
)

RUNTIME_SYSTEM_CONFIG_LIMITS = {
    "BCU_NUM": (1, 15),
    "LECU_NUM": (1, 32),
    "CELL_NUM": (1, 32),
    "CELL_Tem_NUM": (1, 32),
}


def project_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve_project_path(*parts):
    return project_root().joinpath(*parts)


def _default_config_path(file_name="config.json"):
    return resolve_project_path(file_name)


def _normalize_binary_flag(value):
    if isinstance(value, bool):
        return 1 if value else 0
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return 1
    return 0


def _normalize_int(value, fallback, min_value=None, max_value=None):
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(fallback)
    if min_value is not None:
        normalized = max(int(min_value), normalized)
    if max_value is not None:
        normalized = min(int(max_value), normalized)
    return normalized


def _normalize_can_board_config(values):
    normalized = dict(DEFAULT_CAN_BOARD_CONFIG)
    if isinstance(values, dict):
        normalized.update({key: values[key] for key in normalized.keys() & values.keys()})
    normalized["can_idx"] = _normalize_int(normalized["can_idx"], DEFAULT_CAN_BOARD_CONFIG["can_idx"], 0, 31)
    normalized["chn"] = _normalize_int(normalized["chn"], DEFAULT_CAN_BOARD_CONFIG["chn"], 0, 7)
    normalized["baud_rate"] = _normalize_int(normalized["baud_rate"], DEFAULT_CAN_BOARD_CONFIG["baud_rate"], 5, 1000)
    normalized["Has_N"] = _normalize_binary_flag(normalized.get("Has_N", 0))
    for key in RUNTIME_SYSTEM_CONFIG_KEYS:
        min_value, max_value = RUNTIME_SYSTEM_CONFIG_LIMITS[key]
        normalized[key] = _normalize_int(normalized.get(key), DEFAULT_CAN_BOARD_CONFIG[key], min_value, max_value)
    return normalized


def _load_config_json(file_name="config.json"):
    config_path = Path(file_name)
    if not config_path.is_absolute():
        config_path = _default_config_path(file_name)
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return config_path, {}
    if not isinstance(loaded, dict):
        return config_path, {}
    return config_path, loaded


def load_can_board_config(file_name="config.json"):
    _config_path, loaded = _load_config_json(file_name)
    if not loaded:
        return dict(DEFAULT_CAN_BOARD_CONFIG)
    return _normalize_can_board_config(loaded)


def save_can_board_config(can_config, file_name="config.json"):
    config_path, saved = _load_config_json(file_name)

    normalized = _normalize_can_board_config(can_config)
    saved.update(normalized)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(saved, config_file, ensure_ascii=False, indent=2)
        config_file.write("\n")
    return normalized


def load_runtime_config_overrides(file_name="config.json"):
    _config_path, loaded = _load_config_json(file_name)
    if not loaded:
        return {}
    normalized = _normalize_can_board_config(loaded)
    return {
        key: normalized[key]
        for key in ("Has_N",) + RUNTIME_SYSTEM_CONFIG_KEYS
        if key in loaded
    }


def build_cluster_indices(runtime_config):
    addresses = list(runtime_config.get("ADDRESLIST", []))
    cluster_count = min(len(addresses) - 1, int(runtime_config.get("BCU_NUM", 0)))
    return list(range(1, cluster_count + 1))


def build_cluster_addresses(runtime_config):
    addresses = list(runtime_config.get("ADDRESLIST", []))
    return [
        str(addresses[index]).upper()
        for index in build_cluster_indices(runtime_config)
        if index < len(addresses)
    ]
