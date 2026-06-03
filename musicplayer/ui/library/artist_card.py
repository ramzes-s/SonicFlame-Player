"""
Artist Card Widget

This module defines the clickable card widget for the Artist View.
It displays a collage of album arts and animates text on hover.
"""

from PySide6.QtCore import (
    Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QSize
)
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QLinearGradient
from PySide6.QtWidgets import QWidget, QSizePolicy

from musicplayer import config as cfg


class ArtistCardWidget(QWidget):
    """
    A widget that displays an artist's collage and name.
    The text color animates on hover.
    """
    clicked = Signal(str)

    def __init__(self, artist_name: str, track_count: int, collage_path: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(180, 180)
        self.setMaximumSize(250, 250)
        self.setCursor(Qt.PointingHandCursor)

        self._artist_name = artist_name
        self._track_count = track_count
        self._collage = QPixmap(collage_path)
        self._accent_color = QColor(cfg.get_accent_color())
        self._white_color = QColor(cfg.TEXT_COLOR)
        self._border_default_color = QColor(40, 40, 40)

        self._text_color = self._white_color
        self._count_opacity = 0.7
        self._border_color = self._border_default_color

        self._text_color_anim = QPropertyAnimation(self, b"textColor", self)
        self._text_color_anim.setDuration(200)
        self._text_color_anim.setStartValue(self._white_color)
        self._text_color_anim.setEndValue(self._accent_color)
        self._text_color_anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._opacity_anim = QPropertyAnimation(self, b"countOpacity", self)
        self._opacity_anim.setDuration(200)
        self._opacity_anim.setStartValue(0.7)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

        self._border_color_anim = QPropertyAnimation(self, b"borderColor", self)
        self._border_color_anim.setDuration(200)
        self._border_color_anim.setStartValue(self._border_default_color)
        self._border_color_anim.setEndValue(self._accent_color)
        self._border_color_anim.setEasingCurve(QEasingCurve.InOutQuad)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    @Property(QColor)
    def textColor(self) -> QColor:
        return self._text_color

    @textColor.setter
    def textColor(self, color: QColor):
        self._text_color = color
        self.update()

    @Property(float)
    def countOpacity(self) -> float:
        return self._count_opacity

    @countOpacity.setter
    def countOpacity(self, opacity: float):
        self._count_opacity = opacity
        self.update()

    @Property(QColor)
    def borderColor(self) -> QColor:
        return self._border_color

    @borderColor.setter
    def borderColor(self, color: QColor):
        self._border_color = color
        self.update()

    def update_accent_color(self):
        new_color = QColor(cfg.get_accent_color())
        self._accent_color = new_color
        self._text_color_anim.setEndValue(self._accent_color)
        self._border_color_anim.setEndValue(self._accent_color)

    def enterEvent(self, event):
        self._text_color_anim.setDirection(QPropertyAnimation.Forward)
        self._opacity_anim.setDirection(QPropertyAnimation.Forward)
        self._border_color_anim.setDirection(QPropertyAnimation.Forward)
        self._text_color_anim.start()
        self._opacity_anim.start()
        self._border_color_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._text_color_anim.setDirection(QPropertyAnimation.Backward)
        self._opacity_anim.setDirection(QPropertyAnimation.Backward)
        self._border_color_anim.setDirection(QPropertyAnimation.Backward)
        self._text_color_anim.start()
        self._opacity_anim.start()
        self._border_color_anim.start()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._artist_name)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._collage.isNull():
            painter.drawPixmap(self.rect(), self._collage)

        gradient = QLinearGradient(0, self.height() * 0.4, 0, self.height())
        gradient.setColorAt(0, Qt.transparent)
        gradient.setColorAt(1, QColor(0, 0, 0, 200))
        painter.fillRect(self.rect(), gradient)

        font = QFont("Arial", 14, QFont.Bold)
        painter.setFont(font)
        text_rect = self.rect().adjusted(10, 10, -10, -25)

        shadow_color = QColor(0, 0, 0, 100)
        painter.setPen(shadow_color)
        painter.drawText(text_rect.translated(1, 1), Qt.AlignBottom | Qt.AlignLeft | Qt.TextWordWrap, self._artist_name)

        painter.setPen(self._text_color)
        painter.drawText(text_rect, Qt.AlignBottom | Qt.AlignLeft | Qt.TextWordWrap, self._artist_name)

        count_color = QColor(self._white_color)
        count_color.setAlphaF(self._count_opacity)
        painter.setPen(count_color)

        count_font = QFont("Arial", 9)
        painter.setFont(count_font)

        count_rect = self.rect().adjusted(10, 0, -10, -10)
        painter.drawText(count_rect, Qt.AlignBottom | Qt.AlignLeft, f"{self._track_count} tracks")

        painter.setPen(self._border_color)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def sizeHint(self):
        return QSize(200, 200)