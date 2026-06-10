from PyQt6.QtWidgets import QApplication

from .module_cell_grid import ModuleCellGrid


class BatteryMonitorBAL(ModuleCellGrid):
    def __init__(self):
        super().__init__("均衡状态", "", mode="balance")


if __name__ == "__main__":
    app = QApplication([])
    window = BatteryMonitorBAL()
    window.show()
    app.exec()
