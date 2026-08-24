from PyQt6.QtWidgets import QApplication

from .conf import config
from .module_value_page import ModuleValuePage


def _format_balance_temperature(value):
    if isinstance(value, (int, float)):
        return f"{float(value):.1f}"
    return str(value)


class BatteryMonitorBalanceTem(ModuleValuePage):
    def __init__(self, group_count=None, values_per_group=None):
        super().__init__(
            title="\u5747\u8861\u6e29\u5ea6",
            group_title="\u5747\u8861\u6a21\u7ec4",
            group_count=int(
                group_count
                if group_count is not None
                else config.get("BALANCE_MODULE_COUNT", config.get("LECU_NUM", 4))
            ),
            values_per_group=int(
                values_per_group
                if values_per_group is not None
                else config.get("BALANCE_TEMP_PER_MODULE", 8)
            ),
            items_per_row=10,
            value_formatter=_format_balance_temperature,
            highlight_mode="extrema",
            group_columns=1,
        )

    def setTemperatureValues(self, values):
        self.setValues(values)


class MainWindow(BatteryMonitorBalanceTem):
    pass


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorBalanceTem()
    window.show()
    app.exec()
