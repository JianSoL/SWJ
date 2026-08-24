import json
from dataclasses import dataclass
from pathlib import Path


ACCESS_LABELS = {
    "read_only": "只读",
    "read_write": "可读写",
}


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
        if self.location:
            return f"{self.location} {self.name}"
        return self.name

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
            )
        ).lower()


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

    def __init__(self, payload=None):
        payload = dict(payload or {})
        self.schema_version = int(payload.get("schema_version", 1))
        self.source = dict(payload.get("source", {}))
        self.constants = {key: int(value) for key, value in payload.get("constants", {}).items()}
        self.enums = {
            category: list(entries)
            for category, entries in payload.get("enums", {}).items()
        }
        self.alarm_ids = list(payload.get("alarm_ids", []))
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
    def from_json(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload)

    @classmethod
    def empty(cls):
        return cls({"schema_version": 1, "constants": {}, "enums": {}})

    @property
    def is_empty(self):
        return not any(self.enums.values())

    @property
    def source_summary(self):
        name = str(self.source.get("name", "索引目录"))
        digest = str(self.source.get("sha256", ""))
        if digest:
            return f"{name} / {digest[:12]}"
        return name

    def category_options(self):
        options = []
        seen = set()
        for entries in self.enums.values():
            if not entries:
                continue
            label = str(entries[0].get("category_label", entries[0].get("category", "其他")))
            category = str(entries[0].get("category", ""))
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
        constants = self.constants
        if not constants:
            return self._unknown(data_id)

        lecu_start = constants["ID_VAR_LECU_START"]
        bcu_start = constants["ID_VAR_BCU_START"]
        vms_start = constants["ID_VAR_VMS_START"]
        chr_start = constants["ID_VAR_CHR_START"]
        other_start = constants["ID_VAR_OTHER_START"]

        if 0 <= data_id < lecu_start:
            return self._from_offset(data_id, data_id, "system_variable")
        if lecu_start <= data_id < bcu_start:
            return self._resolve_lecu(data_id)
        if bcu_start <= data_id < vms_start:
            relative = data_id - bcu_start
            stride = constants["BCU_DATA_LENGTH"]
            unit_index, offset = divmod(relative, stride)
            bcu_count = max(1, int(config.get("BCU_NUM", 1)))
            if unit_index >= bcu_count:
                return self._unknown(data_id, "BCU变量范围外")
            return self._from_offset(
                data_id,
                offset,
                "bcu_variable",
                location=f"BCU{unit_index + 1}",
            )
        if vms_start <= data_id < chr_start:
            return self._from_offset(data_id, data_id - vms_start, "vms_variable")
        if chr_start <= data_id < other_start:
            return self._from_offset(data_id, data_id - chr_start, "charger_variable")

        parameter = self._resolve_parameter(data_id, config)
        if parameter is not None:
            return parameter
        return self._unknown(data_id)

    def _resolve_lecu(self, data_id):
        constants = self.constants
        relative = data_id - constants["ID_VAR_LECU_START"]
        module_index, local_offset = divmod(relative, constants["LECU_DATA_LENGTH"])
        unit_count = constants["VAR_LECU_UINT_MAX_NUM"]
        if local_offset < unit_count:
            return self._from_offset(
                data_id,
                local_offset,
                "lecu_variable",
                location=f"模组{module_index + 1}",
            )

        cell_relative = local_offset - unit_count
        cell_index, field_offset = divmod(
            cell_relative,
            constants["VAR_LECU_CELL_MAX_NUM"],
        )
        if cell_index >= constants["LECU_CELL_MAX_NUM"]:
            return self._unknown(data_id, f"模组{module_index + 1}单体范围外")
        resolution = self._from_offset(
            data_id,
            field_offset,
            "lecu_cell_variable",
            location=f"模组{module_index + 1}/单体{cell_index + 1}",
        )
        if resolution.known:
            return resolution
        return IndexResolution(
            data_id=data_id,
            symbol=f"VAR_LECU_CELL_FIELD_{field_offset}",
            name=f"单体扩展字段{field_offset + 1}",
            description="下位机索引结构可识别，但当前目录中没有该字段的符号说明。",
            unit="",
            signed=False,
            category="lecu_cell_variable",
            category_label="LECU单体变量",
            access="read_write",
            location=f"模组{module_index + 1}/单体{cell_index + 1}",
            known=False,
        )

    def _resolve_parameter(self, data_id, config):
        c = self.constants
        if c["ID_PAR_COEF_START"] <= data_id < c["ID_PAR_SYS_START"]:
            return self._from_offset(
                data_id,
                data_id - c["ID_PAR_COEF_START"],
                "coefficient_parameter",
            )
        if c["ID_PAR_SYS_START"] <= data_id < c["ID_PAR_RUN_START"]:
            return self._from_offset(
                data_id,
                data_id - c["ID_PAR_SYS_START"],
                "system_parameter",
            )
        if c["ID_PAR_RUN_START"] <= data_id < c["ID_PAR_RUN_CELL_START"]:
            return self._from_offset(
                data_id,
                data_id - c["ID_PAR_RUN_START"],
                "runtime_parameter",
            )
        if c["ID_PAR_RUN_CELL_START"] <= data_id < c["ID_PAR_LECU_START"]:
            relative = data_id - c["ID_PAR_RUN_CELL_START"]
            unit_index, offset = divmod(relative, c["PAR_RUN_CELL_MAX_NUM"])
            return self._from_offset(
                data_id,
                offset,
                "runtime_cell_parameter",
                location=f"运行单元{unit_index + 1}",
            )
        if c["ID_PAR_LECU_START"] <= data_id < c["ID_PAR_BYTE_START"]:
            relative = data_id - c["ID_PAR_LECU_START"]
            module_index, offset = divmod(relative, c["PAR_LECU_MAX_NUM"])
            return self._from_offset(
                data_id,
                offset,
                "lecu_parameter",
                location=f"模组{module_index + 1}",
            )
        if c["ID_PAR_BYTE_START"] <= data_id < c["ID_PAR_ALARM_START"]:
            return self._from_offset(
                data_id,
                data_id - c["ID_PAR_BYTE_START"],
                "byte_parameter",
            )
        if c["ID_PAR_ALARM_START"] <= data_id < c["ID_PAR_OTHER_START"]:
            relative = data_id - c["ID_PAR_ALARM_START"]
            alarm_index, offset = divmod(relative, c["PAR_ALM_MAX_NUM"])
            alarm_name = self._runtime_alarm_name(alarm_index, config)
            return self._from_offset(
                data_id,
                offset,
                "alarm_parameter",
                location=f"告警{alarm_index + 1:03d} {alarm_name}".strip(),
            )
        if c["ID_PAR_RTC_START"] <= data_id < c["ID_PAR_RTC_END"]:
            return self._from_offset(
                data_id,
                data_id - c["ID_PAR_RTC_START"],
                "rtc_parameter",
            )
        return None

    def _runtime_alarm_name(self, alarm_index, config):
        names = config.get("Alarm_name_key", {}) if isinstance(config, dict) else {}
        key = f"{alarm_index + 1:03d}"
        value = names.get(key) if isinstance(names, dict) else None
        if value:
            return str(value)
        return self._alarm_names.get(alarm_index, "")

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
            known=True,
            source_file=str(entry.get("source_file", "")),
            source_line=int(entry.get("source_line", 0)),
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

    def iter_entries(self, runtime_config=None):
        config = runtime_config or {}
        entries = {}

        def add(resolution):
            if resolution is not None and resolution.known:
                entries.setdefault(resolution.data_id, resolution)

        for definition in self.enums.get("system_variable", []):
            add(self.resolve(int(definition["offset"]), config))

        lecu_count = max(1, int(config.get("LECU_NUM", 1)))
        cell_count = min(
            max(0, int(config.get("CELL_NUM", self.constants.get("LECU_CELL_MAX_NUM", 0)))),
            self.constants.get("LECU_CELL_MAX_NUM", 0),
        )
        lecu_start = self.constants.get("ID_VAR_LECU_START", 0x1000)
        lecu_stride = self.constants.get("LECU_DATA_LENGTH", 1)
        unit_count = self.constants.get("VAR_LECU_UINT_MAX_NUM", 0)
        field_count = self.constants.get("VAR_LECU_CELL_MAX_NUM", 0)
        for module_index in range(lecu_count):
            module_base = lecu_start + module_index * lecu_stride
            for definition in self.enums.get("lecu_variable", []):
                add(self.resolve(module_base + int(definition["offset"]), config))
            for cell_index in range(cell_count):
                cell_base = module_base + unit_count + cell_index * field_count
                for field_offset in range(field_count):
                    add(self.resolve(cell_base + field_offset, config))

        bcu_count = max(1, int(config.get("BCU_NUM", 1)))
        bcu_start = self.constants.get("ID_VAR_BCU_START", 0x10000)
        bcu_stride = self.constants.get("BCU_DATA_LENGTH", 1)
        for unit_index in range(bcu_count):
            for definition in self.enums.get("bcu_variable", []):
                add(
                    self.resolve(
                        bcu_start + unit_index * bcu_stride + int(definition["offset"]),
                        config,
                    )
                )

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
            base = self.constants.get(base_key)
            if base is None:
                continue
            for definition in self.enums.get(category, []):
                add(self.resolve(base + int(definition["offset"]), config))

        run_cell_base = self.constants.get("ID_PAR_RUN_CELL_START", 0)
        run_cell_stride = self.constants.get("PAR_RUN_CELL_MAX_NUM", 1)
        for unit_index in range(bcu_count):
            for definition in self.enums.get("runtime_cell_parameter", []):
                add(
                    self.resolve(
                        run_cell_base + unit_index * run_cell_stride + int(definition["offset"]),
                        config,
                    )
                )

        lecu_parameter_base = self.constants.get("ID_PAR_LECU_START", 0)
        lecu_parameter_stride = self.constants.get("PAR_LECU_MAX_NUM", 1)
        for module_index in range(lecu_count):
            for definition in self.enums.get("lecu_parameter", []):
                add(
                    self.resolve(
                        lecu_parameter_base
                        + module_index * lecu_parameter_stride
                        + int(definition["offset"]),
                        config,
                    )
                )

        alarm_base = self.constants.get("ID_PAR_ALARM_START", 0)
        alarm_stride = self.constants.get("PAR_ALM_MAX_NUM", 1)
        alarm_names = config.get("Alarm_name_key", {}) if isinstance(config, dict) else {}
        alarm_count = max(len(self.alarm_ids), len(alarm_names) if isinstance(alarm_names, dict) else 0)
        for alarm_index in range(alarm_count):
            for definition in self.enums.get("alarm_parameter", []):
                add(
                    self.resolve(
                        alarm_base + alarm_index * alarm_stride + int(definition["offset"]),
                        config,
                    )
                )

        return list(sorted(entries.values(), key=lambda item: item.data_id))
