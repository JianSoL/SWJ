from PyQt6.QtWidgets import QApplication

from .module_cell_grid import ModuleCellGrid


class BatteryMonitorBAL(ModuleCellGrid):
    def __init__(self):
        super().__init__("电芯异常", "", mode="abnormal")


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorBAL()
    window.show()
    app.exec()
