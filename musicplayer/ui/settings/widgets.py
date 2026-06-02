from PySide6.QtWidgets import QPushButton, QWidget, QSlider, QStyleOptionSlider
from PySide6.QtWidgets import QStyle
from PySide6.QtCore import Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QPainter, QPen, QIcon, QPixmap, QColor

from musicplayer import config as cfg


class ColorCircleButton(QPushButton):
    """Small circle button representing an accent color."""

    def __init__(self, color_hex: str, size: int = 22, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(size + 6, size + 6)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0;
            }
        """)
        self._pixmap = self._make_pixmap(color_hex, size)
        self.setIcon(QIcon(self._pixmap))
        self.setIconSize(QPixmap(self._pixmap.size()).size())

    def _make_pixmap(self, color_hex: str, size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_hex))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return pixmap

    def set_selected(self, selected: bool):
        if selected:
            ring = QPixmap(self.width(), self.height())
            ring.fill(Qt.transparent)
            p = QPainter(ring)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor("#FFFFFF"))
            p.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
            p.end()
            combined = QPixmap(self._pixmap)
            cp = QPainter(combined)
            cp.drawPixmap(0, 0, ring)
            cp.end()
            self.setIcon(QIcon(combined))
        else:
            self.setIcon(QIcon(self._pixmap))


class ClickableSlider(QSlider):
    """QSlider with click-to-seek support."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            style = self.style()
            handle_rect = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            click_pos = event.position().toPoint()
            if not handle_rect.contains(click_pos):
                groove_rect = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
                slider_range = self.maximum() - self.minimum()
                groove_width = groove_rect.width()
                if groove_width > 0:
                    x_in_groove = click_pos.x() - groove_rect.x()
                    ratio = x_in_groove / groove_width
                    new_val = self.minimum() + round(ratio * slider_range)
                    self.setValue(new_val)
                event.accept()
                return
        super().mousePressEvent(event)


class SpinnerWidget(QWidget):
    """Animated spinning circle loader."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(16, 16)
        self.hide()

    def start(self):
        self._angle = 0
        self.show()
        if not self._timer.isActive():
            self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self.hide()

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(cfg.get_accent_color()), 2.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        r = self.rect().adjusted(2, 2, -2, -2)
        painter.drawArc(r, self._angle * 16, 270 * 16)


class TabButton(QPushButton):
    """Tab button with smooth color animation."""

    def __init__(self, text, accent, parent=None):
        super().__init__(text, parent)
        self._initializing = True
        self._accent = accent
        self._current_color = QColor(cfg.SECONDARY_TEXT_COLOR)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.valueChanged.connect(self._on_anim_value)

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.toggled.connect(self._on_toggled)
        self._apply_style()
        self._initializing = False

    def set_accent(self, accent):
        self._accent = accent
        if self.isChecked():
            self._current_color = QColor(accent)
            self._apply_style()

    def _on_anim_value(self, color):
        self._current_color = QColor(color)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: none; color: {self._current_color.name()};
                font-size: 15px; text-align: left;
                padding: 8px 16px 8px 16px;
            }}
        """)

    def _animate_to(self, target_hex):
        self._anim.stop()
        self._anim.setStartValue(self._current_color)
        self._anim.setEndValue(QColor(target_hex))
        self._anim.start()

    def _on_toggled(self, checked):
        if self._initializing:
            self._current_color = QColor(self._accent if checked else cfg.SECONDARY_TEXT_COLOR)
            self._apply_style()
            return
        self._anim.stop()
        self._anim.setStartValue(self._current_color)
        self._anim.setEndValue(QColor(self._accent if checked else cfg.SECONDARY_TEXT_COLOR))
        self._anim.start()

    def enterEvent(self, e):
        if not self.isChecked():
            self._animate_to(cfg.TEXT_COLOR)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.isChecked():
            self._animate_to(cfg.SECONDARY_TEXT_COLOR)
        super().leaveEvent(e)
