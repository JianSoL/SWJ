from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
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
        self.module_columns = 1
        self.cells_per_row = min(4, max(1, self.cells_per_module))
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
        rows = QVBoxLayout(content)
        rows.setContentsMargins(4, 4, 4, 4)
        rows.setSpacing(12)
        scroll_area.setWidget(content)

        row_layout = None
        for module_index in range(self.module_count):
            if module_index % self.module_columns == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(12)
                rows.addLayout(row_layout)
            group = QGroupBox(f"模组 {module_index + 1}", content)
            group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            group_layout = QGridLayout(group)
            group_layout.setContentsMargins(12, 18, 12, 12)
            group_layout.setHorizontalSpacing(8)
            group_layout.setVerticalSpacing(8)
            row_layout.addWidget(group, 1)

            for cell_index in range(self.cells_per_module):
                cell = QWidget(group)
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(6)
                label = QLabel(f"{cell_index + 1:02d}", group)
                label.setObjectName("metricLabel")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit = QLineEdit(group)
                edit.setPlaceholderText("0")
                edit.setReadOnly(True)
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit.setMinimumWidth(72)
                edit.setMinimumHeight(28)
                edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self.lineEdits.append(edit)
                cell_layout.addWidget(label)
                cell_layout.addWidget(edit, 1)
                row = cell_index // self.cells_per_row
                column = cell_index % self.cells_per_row
                group_layout.addWidget(cell, row, column)
                group_layout.setColumnStretch(column, 1)

            if module_index % self.module_columns == self.module_columns - 1:
                row_layout = None

        if self.module_count % self.module_columns and row_layout is not None:
            row_layout.addStretch(1)
        rows.addStretch(1)

    def setVoltageValues(self, values):
        if values is None:
            return
        values = list(values)
        module_extremes = self._module_extremes(values)
        for index, edit in enumerate(self.lineEdits):
            value = values[index] if index < len(values) else ""
            module_index = index // self.cells_per_module if self.cells_per_module else 0
            max_value, min_value = module_extremes.get(module_index, (None, None))
            edit.setText(self._format_value(value))
            edit.setStyleSheet(self._style_for_value(value, max_value, min_value))

    def _module_extremes(self, values):
        module_extremes = {}
        if self.cells_per_module <= 0:
            return module_extremes
        for module_index in range(self.module_count):
            start = module_index * self.cells_per_module
            end = start + self.cells_per_module
            numeric_values = [
                numeric_value
                for numeric_value in (self._numeric_value(value) for value in values[start:end])
                if numeric_value is not None
            ]
            if numeric_values:
                module_extremes[module_index] = (max(numeric_values), min(numeric_values))
        return module_extremes

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

    def _numeric_value(self, value):
        if value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _style_for_value(self, value, max_value, min_value):
        numeric_value = self._numeric_value(value)
        if self.mode == "balance":
            if int(numeric_value or 0):
                return "background-color: #dcfce7; color: #166534; font-weight: 800;"
            return "background-color: #f8fafc; color: #475569;"
        if self.mode == "abnormal":
            abnormal_value = int(numeric_value or 0)
            if abnormal_value > 10:
                return "background-color: #ef5350; color: white; font-weight: 800;"
            if abnormal_value > 0:
                return "background-color: #fff59d; color: #172033;"
            return "background-color: #c8e6c9; color: #172033;"
        if numeric_value is None:
            return ""
        if max_value is not None and min_value is not None and max_value != min_value and numeric_value == max_value:
            return "background-color: #fee2e2; color: #991b1b; font-weight: 800;"
        if max_value is not None and min_value is not None and max_value != min_value and numeric_value == min_value:
            return "background-color: #fef9c3; color: #854d0e; font-weight: 800;"
        return ""
