from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize, QRect, QByteArray, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QIcon, QPixmap, QPainter

from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR


class IconButton(QPushButton):
    """Button with SVG icon."""

    def __init__(self, svg_getter, size=32, tooltip="", parent=None, circular_hover=False):
        super().__init__(parent)
        self.svg_getter = svg_getter
        self.icon_size = size
        self.tooltip = tooltip
        self._overlay_callback = None
        self._circular_hover = circular_hover

        self._hover_opacity = 0.8
        self._opacity_anim = None
        if self._circular_hover:
            self._opacity_anim = QPropertyAnimation(self, b"hover_opacity")
            self._opacity_anim.setDuration(200)
            self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.setFixedSize(size + 6, size + 6)
        self.setCursor(Qt.PointingHandCursor)

        if self._circular_hover:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    padding: 4px;
                }
            """)
        else:
            self.setStyleSheet(self._get_style())

        self._update_icon()

        if tooltip:
            self.setToolTip(tooltip)

    def _get_hover_opacity(self) -> float:
        return self._hover_opacity

    def _set_hover_opacity(self, value: float):
        self._hover_opacity = value
        self._update_icon()

    hover_opacity = Property(float, _get_hover_opacity, _set_hover_opacity)

    def enterEvent(self, event):
        if self._circular_hover and self._opacity_anim:
            self._opacity_anim.setStartValue(self._hover_opacity)
            self._opacity_anim.setEndValue(1.0)
            self._opacity_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._circular_hover and self._opacity_anim:
            self._opacity_anim.setStartValue(self._hover_opacity)
            self._opacity_anim.setEndValue(0.8)
            self._opacity_anim.start()
        super().leaveEvent(event)

    def set_overlay_callback(self, callback):
        self._overlay_callback = callback
        self._update_icon()

    def _get_style(self) -> str:
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 0.6);
            }
        """

    def _update_icon(self, color=None):
        from PySide6.QtSvg import QSvgRenderer

        use_color = color if color else TEXT_COLOR
        svg_data = self.svg_getter(color=use_color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))

        size = self.icon_size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if self._circular_hover:
            painter.setOpacity(self._hover_opacity)

        renderer.render(painter, QRect(0, 0, size, size))

        if self._overlay_callback is not None:
            self._overlay_callback(painter, QSize(size, size))

        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(self.icon_size, self.icon_size))

    def set_active(self, active: bool):
        if active:
            self._update_icon(cfg.get_accent_color())
        else:
            self._update_icon(TEXT_COLOR)


class ColorHoverButton(IconButton):
    """Button with smooth color transition on hover (no background)."""

    def __init__(self, svg_getter, size=32, tooltip="", parent=None):
        self._hover_anim = None
        self._color_phase = 0.0
        self._current_icon_color = TEXT_COLOR
        super().__init__(svg_getter, size, tooltip, parent, circular_hover=False)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: transparent;
            }
            QPushButton:pressed {
                background-color: transparent;
            }
        """)

    def _get_color_phase(self):
        return self._color_phase

    def _set_color_phase(self, value):
        self._color_phase = value
        self._update_icon_color()

    color_phase = Property(float, _get_color_phase, _set_color_phase)

    def _update_icon_color(self):
        accent = cfg.get_accent_color()
        r1, g1, b1 = int(TEXT_COLOR[1:3], 16), int(TEXT_COLOR[3:5], 16), int(TEXT_COLOR[5:7], 16)
        r2, g2, b2 = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        t = self._color_phase
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self._current_icon_color = color
        self._update_icon(color)

    def _update_icon(self, color=None):
        use_color = color if color else self._current_icon_color
        self._current_icon_color = use_color
        super()._update_icon(use_color)

    def enterEvent(self, event):
        if self._hover_anim:
            self._hover_anim.stop()
        self._hover_anim = QPropertyAnimation(self, b"color_phase")
        self._hover_anim.setDuration(200)
        self._hover_anim.setStartValue(self._color_phase)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hover_anim:
            self._hover_anim.stop()
        self._hover_anim = QPropertyAnimation(self, b"color_phase")
        self._hover_anim.setDuration(200)
        self._hover_anim.setStartValue(self._color_phase)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.start()
        super().leaveEvent(event)
