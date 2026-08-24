from PyQt6.QtWidgets import QApplication

from .conf import config
from .module_value_page import ModuleValuePage


class BatteryMonitor(ModuleValuePage):
    def __init__(self, group_count=None, values_per_group=None):
        super().__init__(
            title="\u5355\u4f53\u7535\u538b",
            group_title="\u91c7\u96c6\u5355\u5143",
            group_count=int(
                group_count
                if group_count is not None
                else config["LECU_NUM"]
            ),
            values_per_group=int(
                values_per_group
                if values_per_group is not None
                else config["CELL_NUM"]
            ),
            items_per_row=10,
            highlight_mode="extrema",
            group_columns=1,
        )

    def setVoltageValues(self, voltages):
        self.setValues(voltages)


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitor()
    window.show()
    app.exec()
