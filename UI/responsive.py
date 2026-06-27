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
        x = rect.x()
        y = rect.y()
        line_height = 0
        right_edge = rect.x() + max(0, rect.width())

        for index, item in enumerate(self._items):
            hint = item.sizeHint()
            item_width = hint.width()
            required_width = self._item_width(index)
            next_x = x + required_width
            if line_height > 0 and next_x > right_edge:
                x = rect.x()
                y += line_height + self._vertical_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += item_width + self._horizontal_spacing
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y()
