# ---- PyQt6核心模块 ----
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLineEdit, QLabel, QVBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QSoundEffect

# ---- Python标准库 ----
import sys
import os
import random

# ---- 本地项目模块（配置）----
from .conf import config  # 包含 LECU_NUM、CELL_NUM 等配置信息

# ---- PyQt6核心模块 ----
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLineEdit, QLabel, QVBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QSoundEffect

# ---- Python标准库 ----
import sys
import os
import random

# ---- 本地配置模块 ----
#from conf import config  # LECU_NUM, CELL_NUM 配置


def resource_path(relative_path):
    """获取资源路径（兼容 PyInstaller 打包和开发环境）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class BatteryMonitorBAL(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.blink_timers = {}  # 每个闪烁框的定时器

    def initUI(self):
        self.setWindowTitle('单体电芯异常监控 (单位: mV)')

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.grid.setContentsMargins(10, 10, 10, 10)

        self.lineEdits = []

        # 电池簇选择（UI保留接口）
        self.comboBox = QComboBox(self)
        self.comboBox.addItems([str(i) for i in range(0, 16)])

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
            full_path = resource_path(name)
            if os.path.exists(full_path):
                return full_path
        return ""

    def setVoltageValues(self, voltages):
        if not voltages:
            return

        has_critical = False
        for i, voltage in enumerate(voltages):
            if i < len(self.lineEdits):
                self.lineEdits[i].setText(f'{voltage}')

                # 停止已有闪烁
                if i in self.blink_timers:
                    self.blink_timers[i].stop()
                    del self.blink_timers[i]

                if voltage == 0:
                    self.lineEdits[i].setStyleSheet("background-color: #C8E6C9; color: black;")
                elif 0 < voltage < 10:
                    self.lineEdits[i].setStyleSheet("background-color: #FFF59D; color: black;")
                elif voltage > 10:
                    self.lineEdits[i].setStyleSheet("background-color: #EF5350; color: white; font-weight: bold;")
                    self.startBlinking(self.lineEdits[i], i)
                    has_critical = True
                else:
                    self.lineEdits[i].setStyleSheet("")

        if has_critical and self.sound.source().isValid():
            self.sound.play()

    def startBlinking(self, lineEdit, idx):
        timer = QTimer(self)
        timer.timeout.connect(lambda: self.toggleBlink(lineEdit))
        timer.start(500)
        self.blink_timers[idx] = timer

    def toggleBlink(self, lineEdit):
        current_style = lineEdit.styleSheet()
        if "background-color: #EF5350" in current_style:
            lineEdit.setStyleSheet("background-color: transparent;")
        else:
            lineEdit.setStyleSheet("background-color: #EF5350; color: white; font-weight: bold;")


if __name__ == '__main__':
    app = QApplication([])

    window = BatteryMonitorBAL()
    window.resize(1200, 600)
    window.show()

    # 示例数据：每7个一个异常
    voltages = [
        0 if i % 7 != 0 else random.randint(11, 100)
        for i in range(int(config["LECU_NUM"]) * int(config["CELL_NUM"]))
    ]
    window.setVoltageValues(voltages)

    app.exec()
