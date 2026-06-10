from PyQt6.QtWidgets import QApplication

from .module_cell_grid import ModuleCellGrid


class BatteryMonitor(ModuleCellGrid):
    def __init__(self):
        super().__init__("单体电压", "mV", mode="numeric")


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitor()
    window.show()
    app.exec()
