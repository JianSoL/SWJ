from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


class SignalGridPage(QWidget):
    def __init__(self, title, items_per_row=8, color_mode="plain"):
        super().__init__()
        self.title = title
        self.items_per_row = items_per_row
        self.color_mode = color_mode
        self.entries = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title_label = QLabel(self.title, self)
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        self.content = QWidget(self.scroll_area)
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(10)
        self.scroll_area.setWidget(self.content)

    def setStatusText(self, text):
        if self.status_label.text() != text:
            self.status_label.setText(text)

    def clearValues(self):
        self.setUpdatesEnabled(False)
        for label_widget, value_widget in self.entries:
            if label_widget.text():
                label_widget.setText("")
            if value_widget.text():
                value_widget.setText("")
            if value_widget.styleSheet():
                value_widget.setStyleSheet("")
            if label_widget.isVisible():
                label_widget.hide()
            if value_widget.isVisible():
                value_widget.hide()
        self.setUpdatesEnabled(True)

    def setSignalValues(self, items):
        self.ensure_capacity(len(items))
        numeric_values = [
            value
            for _, value in items
            if isinstance(value, (int, float))
        ]
        max_value = max(numeric_values) if numeric_values else None
        min_value = min(numeric_values) if numeric_values else None

        self.setUpdatesEnabled(False)
        for index, (label_text, value) in enumerate(items):
            label_widget, value_widget = self.entries[index]
            label_text = str(label_text)
            value_text = _format_value(value)
            if label_widget.text() != label_text:
                label_widget.setText(label_text)
            if not label_widget.isVisible():
                label_widget.show()
            if value_widget.text() != value_text:
                value_widget.setText(value_text)
            if not value_widget.isVisible():
                value_widget.show()
            self._apply_style(value_widget, value, max_value, min_value)

        for index in range(len(items), len(self.entries)):
            label_widget, value_widget = self.entries[index]
            if label_widget.text():
                label_widget.setText("")
            if value_widget.text():
                value_widget.setText("")
            if value_widget.styleSheet():
                value_widget.setStyleSheet("")
            if label_widget.isVisible():
                label_widget.hide()
            if value_widget.isVisible():
                value_widget.hide()
        self.setUpdatesEnabled(True)

    def ensure_capacity(self, count):
        while len(self.entries) < count:
            index = len(self.entries)
            if self.color_mode == "alarm":
                row = (index // self.items_per_row) * 2
                column = index % self.items_per_row

                label_widget = QLabel("", self.content)
                label_widget.setWordWrap(True)
                label_widget.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                label_widget.setMinimumWidth(220)
                self.grid.addWidget(label_widget, row, column)

                value_widget = QLineEdit(self.content)
                value_widget.setReadOnly(True)
                value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                value_widget.setMinimumWidth(140)
                value_widget.setMinimumHeight(30)
                self.grid.addWidget(value_widget, row + 1, column)
            else:
                row = index // self.items_per_row
                column = (index % self.items_per_row) * 2

                label_widget = QLabel("", self.content)
                label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_widget.setMinimumWidth(72)
                self.grid.addWidget(label_widget, row, column)

                value_widget = QLineEdit(self.content)
                value_widget.setReadOnly(True)
                value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                value_widget.setMinimumWidth(84)
                value_widget.setMinimumHeight(30)
                self.grid.addWidget(value_widget, row, column + 1)

            self.entries.append((label_widget, value_widget))

    def _apply_style(self, widget, value, max_value, min_value):
        style = ""
        if self.color_mode == "extrema" and isinstance(value, (int, float)):
            if max_value is not None and value == max_value:
                style = "background-color: #ef4444; color: white;"
            elif min_value is not None and value == min_value:
                style = "background-color: #fde68a; color: #0f172a;"
        elif self.color_mode == "alarm" and isinstance(value, (int, float)):
            if value >= 3:
                style = "background-color: #ef4444; color: white;"
            elif value == 2:
                style = "background-color: #fb923c; color: #0f172a;"
            elif value == 1:
                style = "background-color: #fde68a; color: #0f172a;"
        elif self.color_mode == "binary" and isinstance(value, (int, float)):
            if value != 0:
                style = "background-color: #86efac; color: #0f172a;"
        if widget.styleSheet() != style:
            widget.setStyleSheet(style)
