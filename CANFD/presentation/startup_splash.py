import math

from PyQt6.QtCore import QRectF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget


class StartupSplash(QWidget):
    def __init__(self, product_info=None):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(None, flags)
        self.product_info = product_info
        self._message = "\u542f\u52a8\u4e2d"
        self._progress = 0
        self._phase = 0.0
        self.setFixedSize(680, 390)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(32)
        self._animation_timer.timeout.connect(self._advance_animation)
        self._animation_timer.start()
        self._center_on_screen()

    def set_status(self, message, progress=None):
        if message:
            self._message = str(message)
        if progress is not None:
            self._progress = max(0, min(100, int(progress)))
        self.update()

    def finish(self, window=None):
        self.set_status("\u542f\u52a8\u5b8c\u6210", 100)
        QApplication.processEvents()
        self.close()
        if window is not None:
            window.raise_()
            window.activateWindow()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        screen_rect = screen.availableGeometry()
        x = screen_rect.x() + (screen_rect.width() - self.width()) // 2
        y = screen_rect.y() + (screen_rect.height() - self.height()) // 2
        self.move(x, y)

    def _advance_animation(self):
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        card_rect = QRectF(10, 10, self.width() - 20, self.height() - 20)
        self._draw_card(painter, card_rect)
        self._draw_grid(painter, card_rect)
        self._draw_energy_mark(painter, card_rect)
        self._draw_brand_text(painter, card_rect)
        self._draw_status(painter, card_rect)

    def _draw_card(self, painter, rect):
        shadow_rect = QRectF(rect)
        shadow_rect.translate(0, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 18, 45, 70))
        painter.drawRoundedRect(shadow_rect, 26, 26)

        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        background.setColorAt(0.0, QColor("#07101f"))
        background.setColorAt(0.48, QColor("#0d2346"))
        background.setColorAt(1.0, QColor("#0f4ccf"))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 26, 26)

        border = QPen(QColor(120, 190, 255, 115), 1)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 26, 26)

    def _draw_grid(self, painter, rect):
        painter.save()
        painter.setClipRect(rect)
        pen = QPen(QColor(122, 172, 255, 30), 1)
        painter.setPen(pen)
        spacing = 28
        offset = int(self._phase * spacing)
        left = int(rect.left()) - spacing
        right = int(rect.right()) + spacing
        top = int(rect.top()) - spacing
        bottom = int(rect.bottom()) + spacing
        for x in range(left + offset, right, spacing):
            painter.drawLine(x, top, x, bottom)
        for y in range(top + offset, bottom, spacing):
            painter.drawLine(left, y, right, y)
        painter.restore()

    def _draw_energy_mark(self, painter, rect):
        center_x = rect.right() - 148
        center_y = rect.top() + 154
        radius = 70
        base_pen = QPen(QColor(139, 190, 255, 70), 2)
        active_pen = QPen(QColor(38, 206, 255, 210), 4)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for index in range(3):
            inset = index * 15
            painter.setPen(base_pen)
            painter.drawArc(
                QRectF(
                    center_x - radius + inset,
                    center_y - radius + inset,
                    (radius - inset) * 2,
                    (radius - inset) * 2,
                ),
                22 * 16,
                270 * 16,
            )

        angle = self._phase * math.tau
        sweep_start = int((35 + self._phase * 360) * 16)
        painter.setPen(active_pen)
        painter.drawArc(
            QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2),
            sweep_start,
            82 * 16,
        )

        painter.setPen(QPen(QColor("#26ceff"), 2))
        painter.setBrush(QColor(38, 206, 255, 35))
        for index, height in enumerate((44, 74, 104, 68)):
            x = int(center_x - 42 + index * 28)
            y = int(center_y + 74 - height)
            painter.drawRoundedRect(QRectF(x, y, 15, height), 4, 4)

        dot_x = center_x + math.cos(angle) * (radius + 2)
        dot_y = center_y - math.sin(angle) * (radius + 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(dot_x - 4, dot_y - 4, 8, 8))

    def _draw_brand_text(self, painter, rect):
        display_name = (
            self.product_info.display_name
            if self.product_info is not None
            else "DCBMS CANFD Host"
        )
        version = (
            self.product_info.version
            if self.product_info is not None
            else "1.0.0"
        )

        painter.setPen(QColor(172, 207, 255))
        eyebrow_font = QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold)
        painter.setFont(eyebrow_font)
        painter.drawText(
            QRectF(rect.left() + 46, rect.top() + 38, 420, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{display_name}  v{version}",
        )

        painter.setPen(QColor("#ffffff"))
        title_font = QFont("Microsoft YaHei UI", 38, QFont.Weight.Black)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(rect.left() + 44, rect.top() + 82, 420, 70),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "DCBMS",
        )

        painter.setPen(QColor(205, 226, 255))
        subtitle_font = QFont("Microsoft YaHei UI", 14, QFont.Weight.DemiBold)
        painter.setFont(subtitle_font)
        painter.drawText(
            QRectF(rect.left() + 48, rect.top() + 152, 430, 32),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "\u5927\u50a8 BCU \u5de5\u7a0b\u4e0a\u4f4d\u673a",
        )

        painter.setPen(QPen(QColor(38, 206, 255, 190), 2))
        line_y = int(rect.top() + 212)
        painter.drawLine(int(rect.left() + 48), line_y, int(rect.left() + 290), line_y)
        scan_width = 74
        scan_x = int(rect.left() + 48 + self._phase * (242 - scan_width))
        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.drawLine(scan_x, line_y, scan_x + scan_width, line_y)

    def _draw_status(self, painter, rect):
        left = rect.left() + 48
        top = rect.bottom() - 104
        width = rect.width() - 96
        progress_width = width * (self._progress / 100.0)

        painter.setPen(QColor(188, 215, 255))
        status_font = QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold)
        painter.setFont(status_font)
        painter.drawText(
            QRectF(left, top - 34, width, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._message,
        )
        painter.drawText(
            QRectF(left, top - 34, width, 28),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self._progress}%",
        )

        rail_rect = QRectF(left, top + 4, width, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 36))
        painter.drawRoundedRect(rail_rect, 6, 6)

        if progress_width > 0:
            bar_rect = QRectF(left, top + 4, max(12, progress_width), 12)
            bar_gradient = QLinearGradient(bar_rect.topLeft(), bar_rect.topRight())
            bar_gradient.setColorAt(0.0, QColor("#26ceff"))
            bar_gradient.setColorAt(0.58, QColor("#4f8cff"))
            bar_gradient.setColorAt(1.0, QColor("#9ee7ff"))
            painter.setBrush(bar_gradient)
            painter.drawRoundedRect(bar_rect, 6, 6)

        painter.setPen(QColor(135, 176, 235, 155))
        footer_font = QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium)
        painter.setFont(footer_font)
        painter.drawText(
            QRectF(left, top + 30, width, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "\u6b63\u5728\u51c6\u5907 CAN FD \u901a\u4fe1\u3001DBC \u4fe1\u53f7\u4e0e\u5386\u53f2\u6570\u636e\u7cfb\u7edf",
        )
