from PyQt6.QtWidgets import QApplication

from .conf import config
from .module_cell_grid import ModuleCellGrid


class BatteryMonitorTem(ModuleCellGrid):
    def __init__(self):
        super().__init__(
            "单体温度",
            "℃",
            mode="numeric",
            cells_per_module=int(config["CELL_Tem_NUM"]),
        )


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorTem()
    window.show()
    app.exec()
