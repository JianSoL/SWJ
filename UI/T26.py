from PyQt6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLineEdit, QLabel, QPushButton, QVBoxLayout,QComboBox
)
from PyQt6.QtCore import Qt

from .conf import config

class BatteryMonitorBAL(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('均衡监控')
        self.grid = QGridLayout()

        self.lineEdits = []

        # 创建下拉框选择电池包
        self.comboBox = QComboBox(self)
        self.comboBox.addItems([str(i) for i in range(0,16)])
        #self.comboBox.currentIndexChanged.connect(self.updateBatteryMonitor)


        # 动态创建 40 个 QLineEdit，8 行 5 列
        for i in range(int(config["LECU_NUM"]*int(config["CELL_NUM"]))):
            label = QLabel(f' {i + 1} ')
            self.grid.addWidget(label, i // int(config["CELL_NUM"]), (i % int(config["CELL_NUM"])) * 2)

            lineEdit = QLineEdit()
            lineEdit.setPlaceholderText('0')
            lineEdit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lineEdits.append(lineEdit)
            self.grid.addWidget(lineEdit, i // int(config["CELL_NUM"]), (i % int(config["CELL_NUM"])) * 2 + 1)

        self.setLayout(self.grid)

    def setVoltageValues(self, voltages):
        """ 给每个 QLineEdit 赋值，并高亮显示最高和最低电压 """
        if not voltages:
            return

        max_voltage = max(voltages)
        min_voltage = min(voltages)

        for i, voltage in enumerate(voltages):
            if i < len(self.lineEdits):  # 确保不会超出范围
                self.lineEdits[i].setText(f'{voltage} ')  # 添加单位
                # 设置颜色
                if voltage == max_voltage:
                    self.lineEdits[i].setStyleSheet("background-color: red;")
                elif voltage == min_voltage:
                    self.lineEdits[i].setStyleSheet("background-color: green;")
                else:
                    self.lineEdits[i].setStyleSheet("")  # 恢复默认颜色


if __name__ == '__main__':
    app = QApplication([])
    window = BatteryMonitorBAL()
    window.show()
    app.exec()
