from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QSizePolicy, QSpacerItem, QWidgetItem


class FlowLayout(QLayout):
    """A compact wrapping layout for dense desktop toolbars."""

    def __init__(self, parent=None, margin=0, horizontal_spacing=8, vertical_spacing=8):
        super().__init__(parent)
        self._items = []
        self._horizontal_spacing = int(horizontal_spacing)
        self._vertical_spacing = int(vertical_spacing)
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, widget):
        self.addItem(QWidgetItem(widget))

    def addSpacing(self, size):
        self.addItem(
            QSpacerItem(
                int(size),
                0,
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Minimum,
            )
        )

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        margins = self.contentsMargins()
        content_width = max(0, int(width) - margins.left() - margins.right())
        return (
            self._do_layout(QRect(0, 0, content_width, 0), test_only=True)
            + margins.top()
            + margins.bottom()
        )

    def setGeometry(self, rect):
        super().setGeometry(rect)
        margins = self.contentsMargins()
        content_rect = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )
        self._do_layout(content_rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _item_width(self, index):
        item = self._items[index]
        width = item.sizeHint().width()
        widget = item.widget()
        if widget is not None and widget.property("flowKeepNext") and index + 1 < len(self._items):
            width += self._horizontal_spacing + self._items[index + 1].sizeHint().width()
        return width

    def _do_layout(self, rect, test_only):
        available_width = max(0, rect.width())
        lines = []
        line_items = []
        line_width = 0
        line_height = 0
        for index, item in enumerate(self._items):
            hint = item.sizeHint()
            item_width = hint.width()
            required_width = self._item_width(index)
            spacing = self._horizontal_spacing if line_items else 0
            if line_items and line_width + spacing + required_width > available_width:
                lines.append((line_items, line_height))
                line_items = []
                line_width = 0
                line_height = 0
                spacing = 0
            line_items.append(item)
            line_width += spacing + item_width
            line_height = max(line_height, hint.height())
        if line_items:
            lines.append((line_items, line_height))

        y = rect.y()
        for items, current_line_height in lines:
            x = rect.x()
            for item_index, item in enumerate(items):
                hint = item.sizeHint()
                if item_index:
                    x += self._horizontal_spacing
                if not test_only:
                    centered_y = y + max(0, (current_line_height - hint.height()) // 2)
                    item.setGeometry(QRect(QPoint(x, centered_y), hint))
                x += hint.width()
            y += current_line_height + self._vertical_spacing

        if lines:
            y -= self._vertical_spacing
        return y - rect.y()
