import re

from PyQt6.QtWidgets import QApplication

from .conf import config
from .module_value_page import ModuleValuePage


BALANCE_LABEL_PATTERN = re.compile(r"^M(?P<module>\d+)-(?P<cell>\d+)$")


class BatteryMonitorBAL(ModuleValuePage):
    def __init__(self, group_count=None, values_per_group=None):
        super().__init__(
            title="\u5747\u8861\u72b6\u6001",
            group_title="\u5747\u8861\u6a21\u7ec4",
            group_count=int(
                group_count
                if group_count is not None
                else config.get("BALANCE_MODULE_COUNT", config.get("LECU_NUM", 4))
            ),
            values_per_group=int(
                values_per_group
                if values_per_group is not None
                else config.get("BALANCE_CELLS_PER_MODULE", config["CELL_NUM"])
            ),
            items_per_row=10,
            highlight_mode="binary",
            group_columns=1,
        )

    def setSignalValues(self, items):
        if not items:
            self.clearValues()
            return

        mapped_items = []
        fallback_values = []
        total_group_count = self.group_count

        for label, value in items:
            match = BALANCE_LABEL_PATTERN.match(str(label))
            if not match:
                fallback_values.append(value)
                continue

            module_index = int(match.group("module")) - 1
            cell_index = int(match.group("cell")) - 1
            if module_index < 0 or cell_index < 0:
                continue

            total_group_count = max(total_group_count, module_index + 1)
            mapped_items.append((module_index, cell_index, value))

        if not mapped_items:
            self.setValues(fallback_values)
            return

        values = [None] * (total_group_count * self.values_per_group)
        for module_index, cell_index, value in mapped_items:
            if cell_index >= self.values_per_group:
                continue
            absolute_index = module_index * self.values_per_group + cell_index
            values[absolute_index] = value

        self.setValues(values)

    def setVoltageValues(self, values):
        self.setValues(values)


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorBAL()
    window.show()
    app.exec()
