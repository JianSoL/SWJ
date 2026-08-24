from collections import OrderedDict, defaultdict
from pathlib import Path

import yaml

from domain.models import LegacySignalDefinition


class LegacySignalCatalog:
    def __init__(self, definitions):
        self.definitions = list(definitions)
        self.definitions_by_id = defaultdict(list)
        self.logged_signal_names = []

        seen_log_names = set()
        for definition in self.definitions:
            self.definitions_by_id[definition.signal_id].append(definition)
            if definition.save_to_log and definition.name not in seen_log_names:
                self.logged_signal_names.append(definition.name)
                seen_log_names.add(definition.name)

    @classmethod
    def from_yaml(cls, catalog_path):
        catalog_path = Path(catalog_path)
        with catalog_path.open("r", encoding="utf-8") as catalog_file:
            payload = yaml.safe_load(catalog_file) or {}

        if not isinstance(payload, dict):
            raise ValueError(f"Legacy signal catalog must be a mapping: {catalog_path}")
        schema_version = payload.get("schema_version", 1)
        if int(schema_version) != 1:
            raise ValueError(
                f"Unsupported legacy signal catalog schema_version "
                f"{schema_version!r}: {catalog_path}"
            )

        signals = payload.get("signals")
        if not isinstance(signals, list):
            raise ValueError(
                f"Legacy signal catalog must contain a signals list: {catalog_path}"
            )

        definitions = []
        required_fields = (
            "id",
            "name",
            "unit",
            "table",
            "row",
            "bit_start",
            "bit_length",
            "signed",
            "save_to_log",
        )
        for item_index, item in enumerate(signals, start=1):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Legacy signal #{item_index} must be a mapping: {catalog_path}"
                )
            missing = [field for field in required_fields if field not in item]
            if missing:
                joined = ", ".join(missing)
                raise ValueError(
                    f"Legacy signal #{item_index} is missing {joined}: {catalog_path}"
                )
            definitions.append(
                LegacySignalDefinition(
                    signal_id=cls._parse_signal_id(item["id"], item_index, catalog_path),
                    name=str(item["name"]),
                    unit=str(item["unit"]),
                    table_index=int(item["table"]),
                    row_index=int(item["row"]),
                    bit_start=int(item["bit_start"]),
                    bit_length=int(item["bit_length"]),
                    signed=cls._parse_bool(item["signed"], "signed", item_index, catalog_path),
                    save_to_log=cls._parse_bool(
                        item["save_to_log"],
                        "save_to_log",
                        item_index,
                        catalog_path,
                    ),
                )
            )
        return cls(definitions)

    @staticmethod
    def _parse_signal_id(value, item_index, catalog_path):
        try:
            if isinstance(value, str):
                return int(value.strip(), 0)
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Legacy signal #{item_index} has invalid id {value!r}: {catalog_path}"
            ) from exc

    @staticmethod
    def _parse_bool(value, field, item_index, catalog_path):
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        raise ValueError(
            f"Legacy signal #{item_index} field {field} must be true or false: "
            f"{catalog_path}"
        )

    def get_definitions(self, signal_id):
        return list(self.definitions_by_id.get(signal_id, []))

    def create_cluster_log_state(self):
        return OrderedDict((signal_name, "0") for signal_name in self.logged_signal_names)
