from PyQt6.QtWidgets import QApplication

from .conf import config
from .module_value_page import ModuleValuePage


def _format_temperature(value):
    if isinstance(value, (int, float)):
        return f"{float(value):.1f}"
    return str(value)


class BatteryMonitorTem(ModuleValuePage):
    def __init__(self, group_count=None, values_per_group=None):
        super().__init__(
            title="\u5355\u4f53\u6e29\u5ea6",
            group_title="\u91c7\u96c6\u5355\u5143",
            group_count=int(
                group_count
                if group_count is not None
                else config["LECU_NUM"]
            ),
            values_per_group=int(
                values_per_group
                if values_per_group is not None
                else config["CELL_Tem_NUM"]
            ),
            items_per_row=10,
            value_formatter=_format_temperature,
            highlight_mode="extrema",
            group_columns=1,
        )

    def setVoltageValues(self, voltages):
        self.setValues(voltages)


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorTem()
    window.show()
    app.exec()
