from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QPaintEvent, QColor, QLinearGradient
from musicplayer import config as cfg


class LoadingBar(QWidget):
    """Thin animated loading bar at the bottom of the dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._offset = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._visible = False

    def start(self):
        self._visible = True
        self._offset = 0.0
        self._timer.start(16)
        self.show()
        self.update()

    def stop(self):
        self._timer.stop()
        self._visible = False
        self.hide()

    def _animate(self):
        self._offset += 0.03
        if self._offset > 1.0:
            self._offset = 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent):
        if not self._visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)

        w = self.width()
        h = self.height()
        bar_width = int(w * 0.3)
        x_start = int(self._offset * w) - bar_width

        gradient = QLinearGradient(x_start, 0, x_start + bar_width, 0)
        gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 0))
        gradient.setColorAt(0.3, color)
        gradient.setColorAt(0.7, color)
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))

        painter.fillRect(x_start, 0, bar_width, h, gradient)


from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, QMouseEvent


class CoverDisplayLabel(QLabel):
    cover_double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Нет обложки")
        self.setStyleSheet("""
            QLabel {
                background-color: #111111;
                border: 1px solid rgba(80, 80, 80, 0.5);
                color: #666666;
                font-size: 11px;
            }
        """)

    def setPixmap(self, pixmap: QPixmap):
        super().setPixmap(pixmap)
        if not pixmap.isNull():
            self.setText("")
        else:
            self.setText("Нет обложки")

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.cover_double_clicked.emit()
            super().mouseDoubleClickEvent(event)