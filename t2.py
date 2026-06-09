from PyQt6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLineEdit, QLabel, QVBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QUrl
import sys
import os

from .conf import config  # 使用你的配置，确保 config["LECU_NUM"], config["CELL_NUM"]

class BatteryMonitorBAL(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('单体电芯异常监控 (单位: mV)')

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.grid.setContentsMargins(10, 10, 10, 10)

        self.lineEdits = []

        # 电池簇选择
        self.comboBox = QComboBox(self)
        self.comboBox.addItems([str(i) for i in range(0, 16)])
        self.grid.addWidget(self.comboBox, 0, 0, 1, 2)

        total_cells = int(config["LECU_NUM"]) * int(config["CELL_NUM"])

        for i in range(total_cells):
            row = (i // int(config["CELL_NUM"])) + 1
            col = (i % int(config["CELL_NUM"])) * 2

            label = QLabel(f'{i + 1}')
            self.grid.addWidget(label, row, col)

            lineEdit = QLineEdit()
            lineEdit.setPlaceholderText('0')
            lineEdit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lineEdit.setMinimumHeight(30)
            lineEdit.setStyleSheet("padding: 4px;")
            self.lineEdits.append(lineEdit)
            self.grid.addWidget(lineEdit, row, col + 1)

        self.setLayout(self.grid)

        # 加载报警声音
        self.sound = QSoundEffect()
        alarm_file = self.find_alarm_sound()
        if alarm_file:
            self.sound.setSource(QUrl.fromLocalFile(alarm_file))
            self.sound.setLoopCount(1)
            self.sound.setVolume(0.8)

    def find_alarm_sound(self):
        for name in ['alarm.wav', 'techno_alarm.wav', 'techno_alarm_alt.wav']:
            if os.path.exists(name):
                return name
        return ""

    def setVoltageValues(self, voltages):
        if not voltages:
            return

        has_critical = False

        for i, voltage in enumerate(voltages):
            if i < len(self.lineEdits):
                self.lineEdits[i].setText(f'{voltage}')

                if voltage == 0:
                    self.lineEdits[i].setStyleSheet("background-color: #C8E6C9; color: black;")  # 绿色
                elif 0 < voltage < 10:
                    self.lineEdits[i].setStyleSheet("background-color: #FFF59D; color: black;")  # 黄色
                else:
                    self.lineEdits[i].setStyleSheet("background-color: #EF5350; color: white; font-weight: bold;")
                    has_critical = True

        if has_critical and self.sound.source().isValid():
            self.sound.play()

if __name__ == '__main__':
    app = QApplication([])

    window = BatteryMonitorBAL()
    window.resize(1200, 600)
    window.show()

    # 示例：每7个随机一个异常
    import random
    voltages = [0 if i % 7 != 0 else random.randint(10, 100) for i in range(int(config["LECU_NUM"]) * int(config["CELL_NUM"]))]
    window.setVoltageValues(voltages)

    app.exec()
