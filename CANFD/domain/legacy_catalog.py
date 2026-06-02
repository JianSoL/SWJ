from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

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
    def from_excel(cls, workbook_path, sheet_name="Sheet1"):
        dataframe = pd.read_excel(Path(workbook_path), sheet_name=sheet_name)
        return cls.from_dataframe(dataframe)

    @classmethod
    def from_dataframe(cls, dataframe):
        definitions = []
        for _, row in dataframe.iterrows():
            definitions.append(
                LegacySignalDefinition(
                    signal_id=int(str(row.iloc[0]), 16),
                    name=str(row.iloc[1]),
                    unit=str(row.iloc[2]),
                    table_index=int(row.iloc[5]),
                    row_index=int(row.iloc[4]),
                    bit_start=int(row.iloc[9]),
                    bit_length=int(row.iloc[10]),
                    signed=bool(int(row.iloc[11])),
                    save_to_log=bool(int(row.iloc[6])),
                )
            )
        return cls(definitions)

    def get_definitions(self, signal_id):
        return list(self.definitions_by_id.get(signal_id, []))

    def create_cluster_log_state(self):
        return OrderedDict((signal_name, "0") for signal_name in self.logged_signal_names)
