from pathlib import Path
import random
import sys

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from .conf import config


def resource_path(relative_path):
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        bundle_dir = Path(sys._MEIPASS)
        candidates.extend(
            [
                bundle_dir / relative_path,
                bundle_dir / "CANFD" / relative_path,
            ]
        )

    module_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            module_dir / relative_path,
            module_dir.parent / relative_path,
            Path.cwd() / relative_path,
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(module_dir.parent / relative_path)


class BatteryMonitorBAL(QWidget):
    def __init__(self):
        super().__init__()
        self.blink_timers = {}
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Battery Balance Alarm (mV)")

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.lineEdits = []

        self.comboBox = QComboBox(self)
        self.comboBox.addItems([str(i) for i in range(0, 16)])

        total_cells = int(config["LECU_NUM"]) * int(config["CELL_NUM"])
        for index in range(total_cells):
            row = (index // int(config["CELL_NUM"])) + 1
            column = (index % int(config["CELL_NUM"])) * 2

            label = QLabel(f"{index + 1}")
            self.grid.addWidget(label, row, column)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText("0")
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setMinimumHeight(30)
            line_edit.setStyleSheet("padding: 4px;")
            self.lineEdits.append(line_edit)
            self.grid.addWidget(line_edit, row, column + 1)

        self.setLayout(self.grid)

        self.sound = QSoundEffect()
        alarm_file = self.find_alarm_sound()
        if alarm_file:
            self.sound.setSource(QUrl.fromLocalFile(alarm_file))
            self.sound.setLoopCount(1)
            self.sound.setVolume(0.8)

    def find_alarm_sound(self):
        for name in ["alarm.wav", "techno_alarm.wav", "techno_alarm_alt.wav"]:
            full_path = resource_path(name)
            if Path(full_path).exists():
                return full_path
        return ""

    def setVoltageValues(self, voltages):
        if not voltages:
            return

        has_critical = False
        for index, voltage in enumerate(voltages):
            if index >= len(self.lineEdits):
                continue

            self.lineEdits[index].setText(f"{voltage}")
            if index in self.blink_timers:
                self.blink_timers[index].stop()
                del self.blink_timers[index]

            if voltage == 0:
                self.lineEdits[index].setStyleSheet(
                    "background-color: #C8E6C9; color: black;"
                )
            elif 0 < voltage < 10:
                self.lineEdits[index].setStyleSheet(
                    "background-color: #FFF59D; color: black;"
                )
            elif voltage > 10:
                self.lineEdits[index].setStyleSheet(
                    "background-color: #EF5350; color: white; font-weight: bold;"
                )
                self.startBlinking(self.lineEdits[index], index)
                has_critical = True
            else:
                self.lineEdits[index].setStyleSheet("")

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
            lineEdit.setStyleSheet(
                "background-color: #EF5350; color: white; font-weight: bold;"
            )


if __name__ == "__main__":
    app = QApplication([])

    window = BatteryMonitorBAL()
    window.resize(1200, 600)
    window.show()

    voltages = [
        0 if index % 7 != 0 else random.randint(11, 100)
        for index in range(int(config["LECU_NUM"]) * int(config["CELL_NUM"]))
    ]
    window.setVoltageValues(voltages)

    app.exec()
