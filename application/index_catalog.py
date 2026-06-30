import json
from dataclasses import dataclass, field, replace
from pathlib import Path
import sys

import yaml

from .configuration import project_root


ACCESS_LABELS = {"read_only": "只读", "read_write": "可读写"}
CUSTOM_CONFIG_VERSION = 1


def _parse_data_id(value):
    if isinstance(value, int):
        return value
    return int(str(value).strip(), 0)


def _resource_candidates(*parts):
    candidates = [project_root().joinpath(*parts)]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS).joinpath(*parts))
    candidates.append(Path(__file__).resolve().parents[1].joinpath(*parts))
    return candidates


def default_catalog_path():
    for candidate in _resource_candidates("resources", "index_catalog.json"):
        if candidate.exists():
            return candidate
    return _resource_candidates("resources", "index_catalog.json")[-1]


def default_custom_config_path():
    return project_root() / "index_custom.yaml"


def default_custom_template_path():
    for candidate in _resource_candidates("resources", "index_custom_template.yaml"):
        if candidate.exists():
            return candidate
    return _resource_candidates("resources", "index_custom_template.yaml")[-1]


@dataclass(frozen=True)
class IndexResolution:
    data_id: int
    symbol: str
    name: str
    description: str
    unit: str
    signed: bool
    category: str
    category_label: str
    access: str
    location: str = ""
    reserved: bool = False
    known: bool = True
    source_file: str = ""
    source_line: int = 0
    scale: float = 1.0
    value_offset: float = 0.0
    display_unit: str = ""
    value_map: dict = field(default_factory=dict)
    custom: bool = False

    @property
    def hex_id(self):
        return f"0x{self.data_id:X}"

    @property
    def access_label(self):
        return ACCESS_LABELS.get(self.access, "未知")

    @property
    def type_label(self):
        return "S16" if self.signed else "U16"

    @property
    def short_name(self):
        return f"{self.location} {self.name}".strip() if self.location else self.name

    @property
    def source_label(self):
        if not self.source_file:
            return ""
        if self.source_line > 0:
            return f"{self.source_file}:{self.source_line}"
        return self.source_file

    @property
    def search_text(self):
        return " ".join(
            (
                str(self.data_id),
                self.hex_id,
                self.symbol,
                self.name,
                self.description,
                self.category_label,
                self.location,
                self.unit,
                self.display_unit,
            )
        ).lower()

    def signed_raw(self, raw_value):
        raw_word = int(raw_value) & 0xFFFF
        if self.signed and raw_word & 0x8000:
            return raw_word - 0x10000
        return raw_word

    def physical_value(self, raw_value):
        return self.signed_raw(raw_value) * float(self.scale) + float(self.value_offset)

    def format_physical_value(self, raw_value):
        signed_value = self.signed_raw(raw_value)
        mapped = self.value_map.get(str(signed_value), self.value_map.get(str(int(raw_value) & 0xFFFF)))
        if mapped is not None:
            return str(mapped)
        value = self.physical_value(raw_value)
        if abs(value - round(value)) < 1e-9:
            text = str(int(round(value)))
        else:
            text = f"{value:.6f}".rstrip("0").rstrip(".")
        unit = self.display_unit or self.unit
        return f"{text} {unit}".strip()


class IndexCatalog:
    FIXED_CATEGORIES = (
        "system_variable",
        "vms_variable",
        "charger_variable",
        "coefficient_parameter",
        "system_parameter",
        "runtime_parameter",
        "byte_parameter",
        "rtc_parameter",
    )

    def __init__(self, payload=None, custom_path=None):
        payload = dict(payload or {})
        self.schema_version = int(payload.get("schema_version", 1))
        self.source = dict(payload.get("source", {}))
        self.constants = {key: int(value) for key, value in payload.get("constants", {}).items()}
        self.enums = {category: list(entries) for category, entries in payload.get("enums", {}).items()}
        self.alarm_ids = list(payload.get("alarm_ids", []))
        self.custom_path = Path(custom_path or default_custom_config_path())
        self.custom_entries = []
        self._custom_by_id = {}
        self._by_offset = {}
        for category, entries in self.enums.items():
            category_map = {}
            for entry in entries:
                offset = int(entry.get("offset", -1))
                current = category_map.get(offset)
                if current is None or (current.get("reserved") and not entry.get("reserved")):
                    category_map[offset] = entry
            self._by_offset[category] = category_map
        self._alarm_names = {
            int(entry.get("offset", -1)): str(entry.get("name", ""))
            for entry in self.alarm_ids
            if int(entry.get("offset", -1)) >= 0
        }

    @classmethod
    def from_json(cls, path, custom_path=None):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload, custom_path=custom_path)

    @classmethod
    def load_default(cls):
        try:
            catalog = cls.from_json(default_catalog_path())
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            catalog = cls()
        catalog.reload_custom_config(ignore_errors=True)
        return catalog

    @property
    def is_empty(self):
        return not any(self.enums.values()) and not self.custom_entries

    @property
    def custom_count(self):
        return len(self.custom_entries)

    @property
    def source_summary(self):
        name = str(self.source.get("name", "索引目录"))
        digest = str(self.source.get("sha256", ""))
        base = f"{name} / {digest[:12]}" if digest else name
        if self.custom_count:
            return f"{base} / 自定义 {self.custom_count} 项"
        return base

    def category_options(self):
        options = []
        seen = set()
        for entries in self.enums.values():
            if not entries:
                continue
            category = str(entries[0].get("category", ""))
            label = str(entries[0].get("category_label", category or "其他"))
            if category and category not in seen:
                options.append((label, category))
                seen.add(category)
        for entry in self.custom_entries:
            category = str(entry.get("category", "custom"))
            label = str(entry.get("category_label", "自定义"))
            if category and category not in seen:
                options.append((label, category))
                seen.add(category)
        return options

    def resolve(self, data_id, runtime_config=None):
        try:
            data_id = int(data_id)
        except (TypeError, ValueError):
            return None
        config = runtime_config or {}
        c = self.constants
        if not c:
            base = self._unknown(data_id)
        elif 0 <= data_id < c["ID_VAR_LECU_START"]:
            base = self._from_offset(data_id, data_id, "system_variable")
        elif c["ID_VAR_LECU_START"] <= data_id < c["ID_VAR_BCU_START"]:
            base = self._resolve_lecu(data_id)
        elif c["ID_VAR_BCU_START"] <= data_id < c["ID_VAR_VMS_START"]:
            relative = data_id - c["ID_VAR_BCU_START"]
            unit_index, offset = divmod(relative, c["BCU_DATA_LENGTH"])
            if unit_index >= max(1, int(config.get("BCU_NUM", 1))):
                base = self._unknown(data_id, "BCU变量范围外")
            else:
                base = self._from_offset(data_id, offset, "bcu_variable", f"BCU{unit_index + 1}")
        elif c["ID_VAR_VMS_START"] <= data_id < c["ID_VAR_CHR_START"]:
            base = self._from_offset(data_id, data_id - c["ID_VAR_VMS_START"], "vms_variable")
        elif c["ID_VAR_CHR_START"] <= data_id < c["ID_VAR_OTHER_START"]:
            base = self._from_offset(data_id, data_id - c["ID_VAR_CHR_START"], "charger_variable")
        else:
            base = self._resolve_parameter(data_id, config) or self._unknown(data_id)
        return self._apply_custom(base)

    def _resolve_lecu(self, data_id):
        c = self.constants
        relative = data_id - c["ID_VAR_LECU_START"]
        module_index, local_offset = divmod(relative, c["LECU_DATA_LENGTH"])
        unit_count = c["VAR_LECU_UINT_MAX_NUM"]
        if local_offset < unit_count:
            return self._from_offset(data_id, local_offset, "lecu_variable", f"模组{module_index + 1}")
        cell_relative = local_offset - unit_count
        cell_index, field_offset = divmod(cell_relative, c["VAR_LECU_CELL_MAX_NUM"])
        if cell_index >= c["LECU_CELL_MAX_NUM"]:
            return self._unknown(data_id, f"模组{module_index + 1}单体范围外")
        return self._from_offset(
            data_id,
            field_offset,
            "lecu_cell_variable",
            f"模组{module_index + 1}/单体{cell_index + 1}",
        )

    def _resolve_parameter(self, data_id, config):
        c = self.constants
        fixed_ranges = (
            ("ID_PAR_COEF_START", "ID_PAR_SYS_START", "coefficient_parameter"),
            ("ID_PAR_SYS_START", "ID_PAR_RUN_START", "system_parameter"),
            ("ID_PAR_RUN_START", "ID_PAR_RUN_CELL_START", "runtime_parameter"),
        )
        for start_key, end_key, category in fixed_ranges:
            if c[start_key] <= data_id < c[end_key]:
                return self._from_offset(data_id, data_id - c[start_key], category)
        if c["ID_PAR_RUN_CELL_START"] <= data_id < c["ID_PAR_LECU_START"]:
            relative = data_id - c["ID_PAR_RUN_CELL_START"]
            unit_index, offset = divmod(relative, c["PAR_RUN_CELL_MAX_NUM"])
            return self._from_offset(data_id, offset, "runtime_cell_parameter", f"运行单元{unit_index + 1}")
        if c["ID_PAR_LECU_START"] <= data_id < c["ID_PAR_BYTE_START"]:
            relative = data_id - c["ID_PAR_LECU_START"]
            module_index, offset = divmod(relative, c["PAR_LECU_MAX_NUM"])
            return self._from_offset(data_id, offset, "lecu_parameter", f"模组{module_index + 1}")
        if c["ID_PAR_BYTE_START"] <= data_id < c["ID_PAR_ALARM_START"]:
            return self._from_offset(data_id, data_id - c["ID_PAR_BYTE_START"], "byte_parameter")
        if c["ID_PAR_ALARM_START"] <= data_id < c["ID_PAR_OTHER_START"]:
            relative = data_id - c["ID_PAR_ALARM_START"]
            alarm_index, offset = divmod(relative, c["PAR_ALM_MAX_NUM"])
            alarm_name = self._runtime_alarm_name(alarm_index, config)
            return self._from_offset(
                data_id,
                offset,
                "alarm_parameter",
                f"告警{alarm_index + 1:03d} {alarm_name}".strip(),
            )
        if c["ID_PAR_RTC_START"] <= data_id < c["ID_PAR_RTC_END"]:
            return self._from_offset(data_id, data_id - c["ID_PAR_RTC_START"], "rtc_parameter")
        return None

    def _runtime_alarm_name(self, alarm_index, config):
        names = config.get("Alarm_name_key", {}) if isinstance(config, dict) else {}
        value = names.get(f"{alarm_index + 1:03d}") if isinstance(names, dict) else None
        return str(value or self._alarm_names.get(alarm_index, ""))

    def _from_offset(self, data_id, offset, category, location=""):
        entry = self._by_offset.get(category, {}).get(int(offset))
        if entry is None:
            return self._unknown(data_id, location, category)
        return IndexResolution(
            data_id=int(data_id),
            symbol=str(entry.get("symbol", "")),
            name=str(entry.get("name", entry.get("symbol", ""))),
            description=str(entry.get("description", "")),
            unit=str(entry.get("unit", "")),
            signed=bool(entry.get("signed", False)),
            category=str(entry.get("category", category)),
            category_label=str(entry.get("category_label", category)),
            access=str(entry.get("access", "read_only")),
            location=str(location),
            reserved=bool(entry.get("reserved", False)),
            source_file=str(entry.get("source_file", "")),
            source_line=int(entry.get("source_line", 0)),
            scale=float(entry.get("scale", 1.0)),
            display_unit=str(entry.get("display_unit", "")),
        )

    def _unknown(self, data_id, location="", category="unknown"):
        return IndexResolution(
            data_id=int(data_id),
            symbol="--",
            name="未识别索引",
            description="当前索引目录中没有匹配项，仍可按原始索引读取。",
            unit="",
            signed=False,
            category=category,
            category_label="未知",
            access="read_only",
            location=str(location),
            known=False,
        )

    def _apply_custom(self, base):
        custom = self._custom_by_id.get(base.data_id)
        if custom is None:
            return base
        defaults = {
            "symbol": base.symbol if base.known else f"CUSTOM_INDEX_{base.data_id:X}",
            "name": base.name if base.known else "自定义索引",
            "description": base.description if base.known else "用户自定义索引。",
            "unit": base.unit,
            "signed": base.signed,
            "category": base.category if base.known else "custom",
            "category_label": base.category_label if base.known else "自定义",
            "access": base.access if base.known else "read_only",
            "location": base.location,
            "scale": base.scale,
            "value_offset": base.value_offset,
            "display_unit": base.display_unit,
            "value_map": base.value_map,
        }
        values = {key: custom.get(key, value) for key, value in defaults.items()}
        return replace(
            base,
            **values,
            known=True,
            reserved=bool(custom.get("reserved", False)),
            source_file=str(self.custom_path),
            source_line=0,
            custom=True,
        )

    def iter_entries(self, runtime_config=None):
        config = runtime_config or {}
        entries = {}

        def add(data_id):
            resolution = self.resolve(data_id, config)
            if resolution is not None and resolution.known and not resolution.reserved:
                entries[resolution.data_id] = resolution

        for definition in self.enums.get("system_variable", []):
            add(int(definition["offset"]))
        c = self.constants
        if c:
            lecu_count = max(1, int(config.get("LECU_NUM", 1)))
            cell_count = min(max(0, int(config.get("CELL_NUM", c["LECU_CELL_MAX_NUM"]))), c["LECU_CELL_MAX_NUM"])
            for module_index in range(lecu_count):
                module_base = c["ID_VAR_LECU_START"] + module_index * c["LECU_DATA_LENGTH"]
                for definition in self.enums.get("lecu_variable", []):
                    add(module_base + int(definition["offset"]))
                for cell_index in range(cell_count):
                    cell_base = module_base + c["VAR_LECU_UINT_MAX_NUM"] + cell_index * c["VAR_LECU_CELL_MAX_NUM"]
                    for field_offset in range(c["VAR_LECU_CELL_MAX_NUM"]):
                        add(cell_base + field_offset)
            bcu_count = max(1, int(config.get("BCU_NUM", 1)))
            for unit_index in range(bcu_count):
                base = c["ID_VAR_BCU_START"] + unit_index * c["BCU_DATA_LENGTH"]
                for definition in self.enums.get("bcu_variable", []):
                    add(base + int(definition["offset"]))
            fixed_bases = {
                "vms_variable": "ID_VAR_VMS_START",
                "charger_variable": "ID_VAR_CHR_START",
                "coefficient_parameter": "ID_PAR_COEF_START",
                "system_parameter": "ID_PAR_SYS_START",
                "runtime_parameter": "ID_PAR_RUN_START",
                "byte_parameter": "ID_PAR_BYTE_START",
                "rtc_parameter": "ID_PAR_RTC_START",
            }
            for category, base_key in fixed_bases.items():
                for definition in self.enums.get(category, []):
                    add(c[base_key] + int(definition["offset"]))
            for unit_index in range(bcu_count):
                for definition in self.enums.get("runtime_cell_parameter", []):
                    add(c["ID_PAR_RUN_CELL_START"] + unit_index * c["PAR_RUN_CELL_MAX_NUM"] + int(definition["offset"]))
            for module_index in range(lecu_count):
                for definition in self.enums.get("lecu_parameter", []):
                    add(c["ID_PAR_LECU_START"] + module_index * c["PAR_LECU_MAX_NUM"] + int(definition["offset"]))
            alarm_names = config.get("Alarm_name_key", {}) if isinstance(config, dict) else {}
            alarm_count = max(len(self.alarm_ids), len(alarm_names) if isinstance(alarm_names, dict) else 0)
            for alarm_index in range(alarm_count):
                for definition in self.enums.get("alarm_parameter", []):
                    add(c["ID_PAR_ALARM_START"] + alarm_index * c["PAR_ALM_MAX_NUM"] + int(definition["offset"]))
        for custom in self.custom_entries:
            add(int(custom["id"]))
        return sorted(entries.values(), key=lambda item: item.data_id)

    def reload_custom_config(self, path=None, ignore_errors=False):
        source = Path(path or self.custom_path)
        if not source.exists():
            self.custom_entries = []
            self._custom_by_id = {}
            return 0
        try:
            payload = self._read_config_payload(source)
            entries = self._normalize_custom_entries(payload)
        except (OSError, ValueError, TypeError, yaml.YAMLError, json.JSONDecodeError):
            if ignore_errors:
                return 0
            raise
        self.custom_path = source
        self.custom_entries = entries
        self._custom_by_id = {int(entry["id"]): entry for entry in entries}
        return len(entries)

    def import_custom_config(self, source_path):
        source = Path(source_path)
        payload = self._read_config_payload(source)
        entries = self._normalize_custom_entries(payload)
        self._write_custom_config(self.custom_path, entries)
        self.custom_entries = entries
        self._custom_by_id = {int(entry["id"]): entry for entry in entries}
        return len(entries)

    def clear_custom_config(self):
        self._write_custom_config(self.custom_path, [])
        self.custom_entries = []
        self._custom_by_id = {}

    def export_custom_template(self, target_path):
        template = default_custom_template_path()
        if template.exists():
            payload = yaml.safe_load(template.read_text(encoding="utf-8"))
        else:
            payload = {"version": CUSTOM_CONFIG_VERSION, "entries": []}
        target = Path(target_path)
        if target.suffix.lower() == ".json":
            content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        else:
            content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        target.write_text(content, encoding="utf-8")

    def _read_config_payload(self, path):
        path = Path(path)
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        return yaml.safe_load(text)

    def _normalize_custom_entries(self, payload):
        if isinstance(payload, list):
            raw_entries = payload
        elif isinstance(payload, dict):
            version = int(payload.get("version", CUSTOM_CONFIG_VERSION))
            if version != CUSTOM_CONFIG_VERSION:
                raise ValueError(f"不支持的自定义索引配置版本: {version}")
            raw_entries = payload.get("entries", [])
        else:
            raise ValueError("自定义索引配置必须是对象或数组。")
        if not isinstance(raw_entries, list):
            raise ValueError("entries 必须是数组。")
        normalized = []
        seen = set()
        allowed_access = {"read_only", "read_write"}
        for row, raw in enumerate(raw_entries, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"第 {row} 项不是对象。")
            if not bool(raw.get("enabled", True)):
                continue
            try:
                data_id = _parse_data_id(raw.get("id"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"第 {row} 项 id 无效。") from exc
            if data_id < 0 or data_id > 0xFFFFFFFF:
                raise ValueError(f"第 {row} 项 id 超出 32 位范围。")
            if data_id in seen:
                raise ValueError(f"索引 {data_id} 重复。")
            seen.add(data_id)
            entry = {key: value for key, value in raw.items() if key != "enabled"}
            entry["id"] = data_id
            entry["signed"] = bool(entry.get("signed", False))
            entry["scale"] = float(entry.get("scale", 1.0))
            entry["value_offset"] = float(entry.get("value_offset", 0.0))
            access = str(entry.get("access", "read_only"))
            if access not in allowed_access:
                raise ValueError(f"第 {row} 项 access 必须是 read_only 或 read_write。")
            entry["access"] = access
            value_map = entry.get("value_map", {})
            if value_map is not None and not isinstance(value_map, dict):
                raise ValueError(f"第 {row} 项 value_map 必须是对象。")
            entry["value_map"] = {str(key): str(value) for key, value in (value_map or {}).items()}
            normalized.append(entry)
        return normalized

    def _write_custom_config(self, path, entries):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": CUSTOM_CONFIG_VERSION, "entries": entries}
        path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
