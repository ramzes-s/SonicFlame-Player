from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QWidget,
                                QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from musicplayer import config as cfg
from .helpers import (_folder_count_str, _track_count_str, _get_track_count,
                      _get_subfolder_count)


class BottomBarWidget(QWidget):
    select_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setFixedHeight(44)
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)

        self._breadcrumb_label = QLabel()
        self._breadcrumb_label.setStyleSheet(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 12px;")
        left_layout.addWidget(self._breadcrumb_label)

        self._breadcrumb_count = QLabel()
        self._breadcrumb_count.setStyleSheet(f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 12px;")
        left_layout.addWidget(self._breadcrumb_count)

        layout.addWidget(left_widget)
        layout.addStretch(1)

        self._select_btn = QPushButton("\u0412\u044b\u0431\u0440\u0430\u0442\u044c")
        self._select_btn.setFixedHeight(32)
        self._select_btn.setFixedWidth(140)
        self._select_btn.setCursor(Qt.PointingHandCursor)
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(lambda: self.select_requested.emit())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 160))
        self._select_btn.setGraphicsEffect(shadow)
        layout.addWidget(self._select_btn)

    def set_selected_path(self, path):
        self._select_btn.setEnabled(True)
        self._update_breadcrumb(path)

    def apply_accent_color(self, accent: str):
        self._select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent}; border: none; border-radius: 0;
                color: {cfg.TEXT_COLOR}; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {cfg.TEXT_COLOR}; color: {accent}; }}
            QPushButton:disabled {{ background-color: rgba(80,80,80,0.3); color: {cfg.DISABLED_TEXT_COLOR}; }}
        """)

    def _update_breadcrumb(self, path: str):
        try:
            track_count = _get_track_count(path)
            folder_count = _get_subfolder_count(path)
            self._breadcrumb_label.setText(f'<span style="color:{cfg.TEXT_COLOR};">{path}</span>')
            parts = []
            if folder_count:
                parts.append(f'<span style="color:{cfg.SECONDARY_TEXT_COLOR}; font-size: 13px;">{_folder_count_str(folder_count)}  \u0438 </span>')
            if track_count:
                parts.append(f'<span style="color:{cfg.SECONDARY_TEXT_COLOR}; font-size: 13px;">{_track_count_str(track_count)}</span>')
            self._breadcrumb_count.setText(" ".join(parts) if parts else '<span style="color:{cfg.DISABLED_TEXT_COLOR}; font-size: 13px;">\u041f\u0430\u043f\u043a\u0430 \u043f\u0443\u0441\u0442\u0430</span>')
        except Exception:
            self._breadcrumb_label.setText(path)
            self._breadcrumb_count.clear()
