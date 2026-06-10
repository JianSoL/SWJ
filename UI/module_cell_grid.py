from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .conf import config


class ModuleCellGrid(QWidget):
    def __init__(self, title, unit="", mode="numeric", cells_per_module=None):
        super().__init__()
        self.title = title
        self.unit = unit
        self.mode = mode
        self.module_count = int(config["LECU_NUM"])
        self.cells_per_module = int(cells_per_module or config["CELL_NUM"])
        self.lineEdits = []
        self.comboBox = QComboBox(self)
        self.comboBox.addItems([str(i) for i in range(0, 16)])
        self.comboBox.hide()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title_label = QLabel(self.title, self)
        title_label.setObjectName("pageTitle")
        root.addWidget(title_label)

        scroll_area = QScrollArea(self)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidgetResizable(True)
        root.addWidget(scroll_area, 1)

        content = QWidget(scroll_area)
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        scroll_area.setWidget(content)

        columns = 2 if self.module_count > 1 else 1
        for module_index in range(self.module_count):
            group = QGroupBox(f"模组 {module_index + 1}", content)
            group_layout = QGridLayout(group)
            group_layout.setContentsMargins(12, 18, 12, 12)
            group_layout.setHorizontalSpacing(8)
            group_layout.setVerticalSpacing(8)
            grid.addWidget(group, module_index // columns, module_index % columns)

            for cell_index in range(self.cells_per_module):
                label = QLabel(f"{cell_index + 1:02d}", group)
                label.setObjectName("metricLabel")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit = QLineEdit(group)
                edit.setPlaceholderText("0")
                edit.setReadOnly(True)
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit.setMinimumWidth(72)
                edit.setMinimumHeight(28)
                self.lineEdits.append(edit)
                row = cell_index // 4
                column = (cell_index % 4) * 2
                group_layout.addWidget(label, row, column)
                group_layout.addWidget(edit, row, column + 1)

    def setVoltageValues(self, values):
        if values is None:
            return
        values = list(values)
        numeric_values = [value for value in values if isinstance(value, (int, float))]
        max_value = max(numeric_values) if numeric_values else None
        min_value = min(numeric_values) if numeric_values else None
        for index, edit in enumerate(self.lineEdits):
            value = values[index] if index < len(values) else ""
            edit.setText(self._format_value(value))
            edit.setStyleSheet(self._style_for_value(value, max_value, min_value))

    def clearValues(self):
        for edit in self.lineEdits:
            edit.clear()
            edit.setStyleSheet("")

    def _format_value(self, value):
        if value == "":
            return ""
        if self.unit:
            return f"{value} {self.unit}"
        return str(value)

    def _style_for_value(self, value, max_value, min_value):
        if self.mode == "balance":
            if int(value or 0):
                return "background-color: #dcfce7; color: #166534; font-weight: 800;"
            return "background-color: #f8fafc; color: #475569;"
        if self.mode == "abnormal":
            if int(value or 0) > 10:
                return "background-color: #ef5350; color: white; font-weight: 800;"
            if int(value or 0) > 0:
                return "background-color: #fff59d; color: #172033;"
            return "background-color: #c8e6c9; color: #172033;"
        if max_value is not None and min_value is not None and max_value != min_value and value == max_value:
            return "background-color: #fee2e2; color: #991b1b; font-weight: 800;"
        if max_value is not None and min_value is not None and max_value != min_value and value == min_value:
            return "background-color: #fef9c3; color: #854d0e; font-weight: 800;"
        return ""
