from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from presentation.cluster_display import format_cluster_context


class BalanceControlPage(QWidget):
    cellToggleRequested = pyqtSignal(int, int, bool)

    def __init__(
        self,
        group_count,
        values_per_group,
        items_per_row=8,
        group_columns=1,
    ):
        super().__init__()
        self.group_count = int(group_count)
        self.values_per_group = int(values_per_group)
        self.items_per_row = max(int(items_per_row), 1)
        self.group_columns = max(int(group_columns), 1)
        self.buttons = []
        self.open_buttons = []
        self.close_buttons = []
        self.cell_widgets = []
        self.state_labels = []
        self._manual_enabled = False

        self._build_ui()
        self._build_buttons()
        self.set_manual_enabled(False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        self.title_label = QLabel("\u5747\u8861\u63a7\u5236", self)
        self.title_label.setObjectName("pageTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        self.mode_label = QLabel("\u624b\u52a8\u63a7\u5236: \u672a\u5f00\u542f", self)
        self.mode_label.setObjectName("statusPill")
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_label.setMinimumWidth(150)
        header_layout.addWidget(self.mode_label)
        layout.addLayout(header_layout)

        self.context_label = QLabel("\u5f53\u524d\u7c07: -", self)
        self.context_label.setObjectName("contextLabel")
        layout.addWidget(self.context_label)

        self.status_label = QLabel(
            "\u672c\u9875\u9762\u53ef\u53d1\u9001\u5747\u8861\u5f00/\u5173"
            "\u63a7\u5236\u547d\u4ee4\uff0c\u5355\u4f53\u72b6\u6001\u6765\u81ea"
            "\u8bbe\u5907\u5747\u8861\u72b6\u6001\u56de\u8bfb\u3002",
            self,
        )
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.scroll_area, stretch=1)

        self.content = QWidget(self.scroll_area)
        self.content_layout = QGridLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setHorizontalSpacing(12)
        self.content_layout.setVerticalSpacing(12)
        self.scroll_area.setWidget(self.content)

    def _build_buttons(self):
        for group_index in range(self.group_count):
            group_box = QGroupBox(
                f"\u5747\u8861\u6a21\u7ec4 {group_index + 1}",
                self.content,
            )
            group_layout = QGridLayout(group_box)
            group_layout.setContentsMargins(12, 18, 12, 12)
            group_layout.setHorizontalSpacing(8)
            group_layout.setVerticalSpacing(8)
            row = group_index // self.group_columns
            column = group_index % self.group_columns
            self.content_layout.addWidget(group_box, row, column)

            for cell_index in range(self.values_per_group):
                cell_widget = QWidget(group_box)
                cell_widget.setObjectName("balanceControlCell")
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setContentsMargins(6, 6, 6, 6)
                cell_layout.setSpacing(6)

                cell_label = QLabel(f"{cell_index + 1:03d}", cell_widget)
                cell_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell_label.setMinimumWidth(34)
                cell_label.setObjectName("metricLabel")
                cell_layout.addWidget(cell_label)

                state_label = QLabel("--", cell_widget)
                state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                state_label.setMinimumWidth(58)
                state_label.setObjectName("statusPill")
                cell_layout.addWidget(state_label)

                open_button = QToolButton(cell_widget)
                open_button.setText("\u5f00")
                open_button.setCheckable(False)
                open_button.setToolTip(
                    f"\u6a21\u7ec4 {group_index + 1} / "
                    f"\u5355\u4f53 {cell_index + 1}: \u53d1\u9001\u5747\u8861\u5f00\u542f"
                )
                open_button.clicked.connect(
                    lambda _checked=False, group_index=group_index, cell_index=cell_index: (
                        self._emit_cell_command(group_index, cell_index, True)
                    )
                )
                cell_layout.addWidget(open_button)

                close_button = QToolButton(cell_widget)
                close_button.setText("\u5173")
                close_button.setCheckable(False)
                close_button.setToolTip(
                    f"\u6a21\u7ec4 {group_index + 1} / "
                    f"\u5355\u4f53 {cell_index + 1}: \u53d1\u9001\u5747\u8861\u5173\u95ed"
                )
                close_button.clicked.connect(
                    lambda _checked=False, group_index=group_index, cell_index=cell_index: (
                        self._emit_cell_command(group_index, cell_index, False)
                    )
                )
                cell_layout.addWidget(close_button)

                self.open_buttons.append(open_button)
                self.close_buttons.append(close_button)
                self.buttons.extend([open_button, close_button])
                self.cell_widgets.append(cell_widget)
                self.state_labels.append(state_label)
                self._set_cell_display_state(group_index, cell_index, None)

                button_row = cell_index // self.items_per_row
                button_column = cell_index % self.items_per_row
                group_layout.addWidget(cell_widget, button_row, button_column)

    def _emit_cell_command(self, group_index, cell_index, enabled):
        self.cellToggleRequested.emit(group_index, cell_index, bool(enabled))

    def set_cluster_context(self, cluster_index, address):
        if cluster_index is None:
            text = "\u5f53\u524d\u7c07: -"
        else:
            text = format_cluster_context(cluster_index, address)
        self.context_label.setText(text)

    def setStatusText(self, text):
        self.status_label.setText("" if text is None else str(text))

    def set_manual_enabled(self, enabled):
        self._manual_enabled = bool(enabled)
        if self._manual_enabled:
            self.mode_label.setText("\u624b\u52a8\u63a7\u5236: \u5df2\u5f00\u542f")
            self.mode_label.setStyleSheet("color: #15803d; font-weight: 700;")
        else:
            self.mode_label.setText("\u624b\u52a8\u63a7\u5236: \u672a\u5f00\u542f")
            self.mode_label.setStyleSheet("color: #b26a00; font-weight: 700;")
        for button in self.buttons:
            button.setEnabled(self._manual_enabled)
            self._apply_button_style(button)

    def setSignalValues(self, items):
        self.clearValues()
        for label, value in items or []:
            indices = self._indices_from_label(label)
            if indices is None:
                continue
            group_index, cell_index = indices
            if value is None:
                self._set_cell_display_state(group_index, cell_index, None)
                continue
            self.set_cell_state(group_index, cell_index, bool(int(value)))

    def setValues(self, values):
        self.clearValues()
        for absolute_index, value in enumerate(values or []):
            group_index = absolute_index // self.values_per_group
            cell_index = absolute_index % self.values_per_group
            if value is None:
                self._set_cell_display_state(group_index, cell_index, None)
                continue
            self.set_cell_state(group_index, cell_index, bool(int(value)))

    def clearValues(self):
        for group_index in range(self.group_count):
            for cell_index in range(self.values_per_group):
                self._set_cell_display_state(group_index, cell_index, None)

    def set_cell_state(self, group_index, cell_index, enabled):
        self._set_cell_display_state(group_index, cell_index, bool(enabled))

    def revert_cell_state(self, _group_index, _cell_index):
        return

    def _indices_from_label(self, label):
        text = str(label)
        if not text.startswith("M") or "-" not in text:
            return None
        module_text, cell_text = text[1:].split("-", 1)
        try:
            group_index = int(module_text) - 1
            cell_index = int(cell_text) - 1
        except ValueError:
            return None
        if group_index < 0 or group_index >= self.group_count:
            return None
        if cell_index < 0 or cell_index >= self.values_per_group:
            return None
        return group_index, cell_index

    def _set_cell_display_state(self, group_index, cell_index, enabled):
        absolute_index = int(group_index) * self.values_per_group + int(cell_index)
        if absolute_index < 0 or absolute_index >= len(self.state_labels):
            return
        state_label = self.state_labels[absolute_index]
        cell_widget = self.cell_widgets[absolute_index]
        if enabled is None:
            state_label.setText("--")
            state_label.setToolTip("\u6682\u672a\u6536\u5230\u8be5\u5355\u4f53\u5747\u8861\u72b6\u6001")
            state_style = (
                "QLabel { background: #f8fafc; color: #64748b; "
                "border: 1px solid #e2e8f0; border-radius: 7px; "
                "padding: 3px 8px; font-weight: 700; }"
            )
            cell_style = (
                "QWidget#balanceControlCell { background: #f8fafc; "
                "border: 1px solid #dbeafe; border-radius: 9px; }"
            )
        elif enabled:
            state_label.setText("\u5747\u8861\u4e2d")
            state_label.setToolTip("\u8bbe\u5907\u56de\u8bfb\uff1a\u8be5\u5355\u4f53\u5747\u8861\u5f00\u542f")
            state_style = (
                "QLabel { background: #dcfce7; color: #166534; "
                "border: 1px solid #86efac; border-radius: 7px; "
                "padding: 3px 8px; font-weight: 800; }"
            )
            cell_style = (
                "QWidget#balanceControlCell { background: #f0fdf4; "
                "border: 1px solid #86efac; border-radius: 9px; }"
            )
        else:
            state_label.setText("\u5173\u95ed")
            state_label.setToolTip("\u8bbe\u5907\u56de\u8bfb\uff1a\u8be5\u5355\u4f53\u5747\u8861\u5173\u95ed")
            state_style = (
                "QLabel { background: #f1f5f9; color: #475569; "
                "border: 1px solid #cbd5e1; border-radius: 7px; "
                "padding: 3px 8px; font-weight: 700; }"
            )
            cell_style = (
                "QWidget#balanceControlCell { background: #f8fafc; "
                "border: 1px solid #dbeafe; border-radius: 9px; }"
            )
        if state_label.styleSheet() != state_style:
            state_label.setStyleSheet(state_style)
        if cell_widget.styleSheet() != cell_style:
            cell_widget.setStyleSheet(cell_style)

    def _apply_button_style(self, button):
        if button in self.open_buttons:
            style = (
                "QToolButton { background: #ecfdf5; color: #166534; "
                "border: 1px solid #86efac; border-radius: 7px; font-weight: 700; "
                "min-width: 32px; min-height: 28px; }"
            )
        else:
            style = (
                "QToolButton { background: #fff1f2; color: #9f1239; "
                "border: 1px solid #fecdd3; border-radius: 7px; font-weight: 700; "
                "min-width: 32px; min-height: 28px; }"
            )
        if not self._manual_enabled:
            style += (
                " QToolButton:disabled { background: #f8fafc; color: #94a3b8; "
                "border-color: #e2e8f0; }"
            )
        if button.styleSheet() != style:
            button.setStyleSheet(style)
