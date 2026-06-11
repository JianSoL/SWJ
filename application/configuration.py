import json
from pathlib import Path
import sys


DEFAULT_CAN_BOARD_CONFIG = {
    "can_type": "usb_can_2eu",
    "can_idx": 0,
    "chn": 1,
    "baud_rate": 500,
    "Has_N": 0,
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


def _normalize_can_board_config(values):
    normalized = dict(DEFAULT_CAN_BOARD_CONFIG)
    if isinstance(values, dict):
        normalized.update({key: values[key] for key in normalized.keys() & values.keys()})
    normalized["can_idx"] = int(normalized["can_idx"])
    normalized["chn"] = int(normalized["chn"])
    normalized["baud_rate"] = int(normalized["baud_rate"])
    normalized["Has_N"] = _normalize_binary_flag(normalized.get("Has_N", 0))
    return normalized


def load_can_board_config(file_name="config.json"):
    config_path = Path(file_name)
    if not config_path.is_absolute():
        config_path = _default_config_path(file_name)
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return dict(DEFAULT_CAN_BOARD_CONFIG)
    return _normalize_can_board_config(loaded)


def save_can_board_config(can_config, file_name="config.json"):
    config_path = Path(file_name)
    if not config_path.is_absolute():
        config_path = _default_config_path(file_name)
    saved = {}
    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}

    normalized = _normalize_can_board_config(can_config)
    saved.update(normalized)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(saved, config_file, ensure_ascii=False, indent=2)
        config_file.write("\n")
    return normalized


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
