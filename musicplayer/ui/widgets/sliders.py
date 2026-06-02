from PySide6.QtWidgets import QSlider, QStyleOptionSlider, QStyle
from PySide6.QtCore import Qt

from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR


class ClickableSlider(QSlider):
    """Base slider with click-to-seek support."""

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setCursor(Qt.PointingHandCursor)

    def _set_value_from_click(self, event):
        """Calculate slider value from click position."""
        if self.maximum() <= 0:
            return
        style = self.style()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = style.subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self
        )
        if self.orientation() == Qt.Horizontal:
            click_x = event.position().x()
            groove_start = groove_rect.left()
            groove_end = groove_rect.right()
            groove_width = groove_end - groove_start
            if groove_width > 0:
                ratio = max(0.0, min(1.0, (click_x - groove_start) / groove_width))
                value = int(ratio * (self.maximum() - self.minimum()) + self.minimum())
                self.setValue(value)


class SeekSlider(ClickableSlider):
    """Custom styled seek slider."""

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet(self._get_style())
        self.setRange(0, 0)
        self._is_user_interacting = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.maximum() > 0:
            self._set_value_from_click(event)
            self._is_user_interacting = True
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._is_user_interacting:
            self._set_value_from_click(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        was_interacting = self._is_user_interacting
        self._is_user_interacting = False
        super().mouseReleaseEvent(event)
        if was_interacting:
            event.accept()

    def set_value_safe(self, value: int):
        if not self._is_user_interacting:
            self.setValue(value)

    def _get_style(self) -> str:
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {cfg.DIVIDER_COLOR};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0;
                background: {cfg.get_accent_color()};
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {cfg.TEXT_COLOR};
            }}
            QSlider::sub-page:horizontal {{
                background: {cfg.get_accent_color()};
                border-radius: 2px;
            }}
        """


class VolumeSlider(ClickableSlider):
    """Custom styled volume slider with click-to-seek support."""

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet(self._get_style())
        self.setRange(0, 100)
        self.setValue(50)
        self.setFixedWidth(120)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.maximum() > 0:
            self._set_value_from_click(event)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def _get_style(self) -> str:
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {cfg.DIVIDER_COLOR};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: {TEXT_COLOR};
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {cfg.get_accent_color()};
            }}
            QSlider::sub-page:horizontal {{
                background: {TEXT_COLOR};
                border-radius: 2px;
            }}
        """
