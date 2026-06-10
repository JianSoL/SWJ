from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .conf import config


class BalanceControlPage(QWidget):
    moduleApplyRequested = pyqtSignal(int, list)
    moduleCloseRequested = pyqtSignal(int)
    allCloseRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.module_count = int(config["LECU_NUM"])
        self.cells_per_module = int(config["CELL_NUM"])
        self.checks = []
        self.state_labels = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("均衡控制", self)
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.close_all_button = QPushButton("关闭全部均衡", self)
        self.close_all_button.clicked.connect(self.allCloseRequested.emit)
        header.addWidget(self.close_all_button)
        root.addLayout(header)

        self.context_label = QLabel("当前簇: -", self)
        self.context_label.setObjectName("contextLabel")
        root.addWidget(self.context_label)

        self.status_label = QLabel("勾选单体后按模组发送均衡开启命令；关闭本模组会发送该模组全 0 bitmask。", self)
        self.status_label.setObjectName("sectionHint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        content = QWidget(scroll)
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        scroll.setWidget(content)

        columns = 2 if self.module_count > 1 else 1
        for module_index in range(self.module_count):
            group = QGroupBox(f"模组 {module_index + 1}", content)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(12, 18, 12, 12)
            group_layout.setSpacing(8)
            grid.addWidget(group, module_index // columns, module_index % columns)

            cell_grid = QGridLayout()
            cell_grid.setHorizontalSpacing(8)
            cell_grid.setVerticalSpacing(8)
            module_checks = []
            module_states = []
            for cell_index in range(self.cells_per_module):
                cell = QWidget(group)
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(4, 4, 4, 4)
                cell_layout.setSpacing(6)
                checkbox = QCheckBox(f"{cell_index + 1:02d}", cell)
                state = QLabel("--", cell)
                state.setObjectName("statusPill")
                state.setAlignment(Qt.AlignmentFlag.AlignCenter)
                state.setMinimumWidth(48)
                cell_layout.addWidget(checkbox)
                cell_layout.addWidget(state)
                module_checks.append(checkbox)
                module_states.append(state)
                cell_grid.addWidget(cell, cell_index // 4, cell_index % 4)
            group_layout.addLayout(cell_grid)

            buttons = QHBoxLayout()
            apply_button = QPushButton("发送选中", group)
            close_button = QPushButton("关闭本模组", group)
            apply_button.clicked.connect(
                lambda _checked=False, module_index=module_index: self._emit_apply(module_index)
            )
            close_button.clicked.connect(
                lambda _checked=False, module_index=module_index: self.moduleCloseRequested.emit(module_index)
            )
            buttons.addWidget(apply_button)
            buttons.addWidget(close_button)
            group_layout.addLayout(buttons)
            self.checks.append(module_checks)
            self.state_labels.append(module_states)

    def _emit_apply(self, module_index):
        values = [checkbox.isChecked() for checkbox in self.checks[module_index]]
        self.moduleApplyRequested.emit(module_index, values)

    def set_cluster_context(self, cluster_index, address):
        self.context_label.setText(f"当前簇: 簇{cluster_index} / 地址 {address}")

    def set_status_text(self, text):
        self.status_label.setText(str(text))

    def set_values(self, values):
        values = list(values or [])
        for module_index, module_states in enumerate(self.state_labels):
            for cell_index, label in enumerate(module_states):
                absolute_index = module_index * self.cells_per_module + cell_index
                value = int(values[absolute_index]) if absolute_index < len(values) else 0
                if value:
                    label.setText("开")
                    label.setStyleSheet("color: #166534; background: #dcfce7;")
                else:
                    label.setText("关")
                    label.setStyleSheet("color: #475569; background: #f8fafc;")
