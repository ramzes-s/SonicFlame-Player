from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QByteArray
from PySide6.QtGui import QPainter, QPaintEvent, QMouseEvent, QColor
from PySide6.QtSvgWidgets import QSvgWidget
from musicplayer import config as cfg
from musicplayer.ui.svg_icons import get_music_note_svg


class FramelessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag_pos = QPoint()
        self.hide()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = cfg.get_accent_color()
        color = QColor(accent)
        color.setAlpha(26)
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _build_title_bar(self, title_text: str) -> QWidget:
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        svg_data = get_music_note_svg(60).encode('utf-8')
        title_icon.renderer().load(QByteArray(svg_data))
        title_layout.addWidget(title_icon)

        title_label = QLabel(title_text)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(36, 30)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._apply_close_btn_accent()
        self._close_btn.clicked.connect(self.reject)
        title_layout.addWidget(self._close_btn)

        return title_bar

    def _apply_close_btn_accent(self):
        accent = cfg.get_accent_color()
        self._close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; color: #FFFFFF; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: %s; }
        """ % accent)

    def apply_accent_color(self):
        self._apply_close_btn_accent()
        self.update()

    def _setup_ui(self) -> QVBoxLayout:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: #000000; }")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        layout.addWidget(container)
        return inner

    def center_on_parent(self, y_offset: int = 50):
        if self.parent():
            parent_center = self.parent().geometry().center()
            new_x = parent_center.x() - self.rect().width() // 2
            new_y = parent_center.y() - self.rect().height() // 2 + y_offset
            self.move(new_x, new_y)

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
