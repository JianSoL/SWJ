"""Persistent configuration for the cluster page's indexed monitor."""

from pathlib import Path

import yaml

from .configuration import project_root


CONFIG_VERSION = 1
MAX_FIELDS = 64
DEFAULT_FIELDS = (
    {"data_id": 12, "label": "运行状态", "enabled": True},
    {"data_id": 14, "label": "系统电流", "enabled": True},
    {"data_id": 16, "label": "系统SOC", "enabled": True},
    {"data_id": 17, "label": "系统SOH", "enabled": True},
    {"data_id": 91, "label": "B端电压", "enabled": True},
    {"data_id": 92, "label": "P端电压", "enabled": True},
    {"data_id": 321, "label": "单体压差", "enabled": True},
    {"data_id": 322, "label": "单体温差", "enabled": True},
    {"data_id": 323, "label": "平均单体电压", "enabled": True},
    {"data_id": 324, "label": "平均单体温度", "enabled": True},
    {"data_id": 328, "label": "最高单体电压", "enabled": True},
    {"data_id": 331, "label": "最低单体电压", "enabled": True},
    {"data_id": 334, "label": "最高单体温度", "enabled": True},
    {"data_id": 337, "label": "最低单体温度", "enabled": True},
)


def default_cluster_view_path():
    return project_root() / "cluster_view.yaml"


def _normalize_field(field):
    if not isinstance(field, dict):
        return None
    try:
        data_id = int(str(field.get("data_id", "")).strip(), 0)
    except (TypeError, ValueError):
        return None
    if data_id < 0 or data_id > 0xFFFFFFFF:
        return None
    return {
        "data_id": data_id,
        "label": str(field.get("label", "")).strip(),
        "enabled": bool(field.get("enabled", True)),
    }


def normalize_cluster_view_fields(fields):
    result = []
    seen = set()
    for field in fields or ():
        normalized = _normalize_field(field)
        if normalized is None or normalized["data_id"] in seen:
            continue
        result.append(normalized)
        seen.add(normalized["data_id"])
        if len(result) >= MAX_FIELDS:
            break
    return result


def default_cluster_view_fields():
    return [dict(field) for field in DEFAULT_FIELDS]


def load_cluster_view_fields(path=None):
    config_path = Path(path or default_cluster_view_path())
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return default_cluster_view_fields()
    if not isinstance(payload, dict) or int(payload.get("version", 0)) != CONFIG_VERSION:
        return default_cluster_view_fields()
    fields = normalize_cluster_view_fields(payload.get("fields"))
    return fields or default_cluster_view_fields()


def save_cluster_view_fields(fields, path=None):
    config_path = Path(path or default_cluster_view_path())
    normalized = normalize_cluster_view_fields(fields)
    payload = {"version": CONFIG_VERSION, "fields": normalized}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    temp_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temp_path.replace(config_path)
    return normalized
