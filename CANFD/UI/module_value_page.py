from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _format_default_value(value):
    if value is None or value == "":
        return ""
    return str(value)


class ModuleValuePage(QWidget):
    def __init__(
        self,
        title,
        group_title,
        group_count,
        values_per_group,
        items_per_row,
        value_formatter=None,
        highlight_mode="none",
        group_columns=2,
    ):
        super().__init__()
        self.title = title
        self.group_title = group_title
        self.group_count = int(group_count)
        self.values_per_group = int(values_per_group)
        self.max_value_count = self.group_count * self.values_per_group
        self.items_per_row = int(items_per_row)
        self.group_columns = int(group_columns)
        self.value_formatter = value_formatter or _format_default_value
        self.highlight_mode = highlight_mode

        self.groups = []
        self.lineEdits = []
        self._build_ui()
        self.ensure_capacity(self.max_value_count)

    def _build_ui(self):
        self.setWindowTitle(self.title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title_label = QLabel(self.title, self)
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.scroll_area)

        self.content = QWidget(self.scroll_area)
        self.content_layout = QGridLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setHorizontalSpacing(12)
        self.content_layout.setVerticalSpacing(12)
        self.scroll_area.setWidget(self.content)

    def ensure_capacity(self, count):
        count = min(max(int(count), 0), self.max_value_count)
        while len(self.lineEdits) < count:
            index = len(self.lineEdits)
            group_index = index // self.values_per_group
            group_offset = index % self.values_per_group
            _, group_layout = self._ensure_group(group_index)

            row = group_offset // self.items_per_row
            column = (group_offset % self.items_per_row) * 2

            label = QLabel(f"{group_offset + 1:02d}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(32)
            group_layout.addWidget(label, row, column)

            line_edit = QLineEdit()
            line_edit.setReadOnly(True)
            line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line_edit.setMinimumWidth(72)
            line_edit.setMinimumHeight(30)
            group_layout.addWidget(line_edit, row, column + 1)

            self.lineEdits.append(line_edit)

    def _ensure_group(self, group_index):
        while len(self.groups) <= group_index:
            current_group_index = len(self.groups)
            group_box = QGroupBox(f"{self.group_title} {current_group_index + 1}", self.content)
            group_box.setObjectName("moduleGroupCard")
            group_layout = QGridLayout(group_box)
            group_layout.setContentsMargins(12, 16, 12, 12)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(10)

            row = current_group_index // self.group_columns
            column = current_group_index % self.group_columns
            self.content_layout.addWidget(group_box, row, column)
            self.groups.append((group_box, group_layout))

        return self.groups[group_index]

    def setStatusText(self, text):
        text = "" if text is None else str(text)
        if self.status_label.text() != text:
            self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def setValues(self, values):
        if not values:
            self.clearValues()
            return

        display_values = list(values[: self.max_value_count])
        self.ensure_capacity(len(display_values))
        group_extrema = {}
        if self.highlight_mode == "extrema":
            group_count = (len(display_values) + self.values_per_group - 1) // self.values_per_group
            for group_index in range(group_count):
                start = group_index * self.values_per_group
                end = start + self.values_per_group
                numeric_values = [
                    value
                    for value in display_values[start:end]
                    if isinstance(value, (int, float))
                ]
                group_extrema[group_index] = (
                    max(numeric_values) if numeric_values else None,
                    min(numeric_values) if numeric_values else None,
                )

        self.setUpdatesEnabled(False)
        for index, line_edit in enumerate(self.lineEdits):
            value = display_values[index] if index < len(display_values) else None
            if value is None or value == "":
                if line_edit.text():
                    line_edit.setText("")
                if line_edit.styleSheet():
                    line_edit.setStyleSheet("")
                continue

            value_text = self.value_formatter(value)
            if line_edit.text() != value_text:
                line_edit.setText(value_text)
            group_index = index // self.values_per_group
            max_value, min_value = group_extrema.get(group_index, (None, None))
            self._apply_style(line_edit, value, max_value, min_value)
        self.setUpdatesEnabled(True)

    def clearValues(self):
        self.setUpdatesEnabled(False)
        for line_edit in self.lineEdits:
            if line_edit.text():
                line_edit.setText("")
            if line_edit.styleSheet():
                line_edit.setStyleSheet("")
        self.setUpdatesEnabled(True)

    def _apply_style(self, line_edit, value, max_value, min_value):
        style = ""
        if self.highlight_mode == "extrema" and isinstance(value, (int, float)):
            if max_value is not None and value == max_value:
                style = "background-color: #ef5350; color: white;"
            elif min_value is not None and value == min_value:
                style = "background-color: #fde68a; color: #0f172a;"
        elif self.highlight_mode == "binary" and isinstance(value, (int, float)):
            if value != 0:
                style = "background-color: #86efac; color: #0f172a;"
        if line_edit.styleSheet() != style:
            line_edit.setStyleSheet(style)
