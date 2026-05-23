import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from musicplayer import config as cfg
from .widgets import ClickableSlider


class MainPage(QWidget):
    folder_browse_requested = Signal()
    similarity_precision_changed = Signal(int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(16)

        self.folder_btn = QPushButton()
        self.folder_btn.setFixedHeight(36)
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(self.folder_browse_requested.emit)
        self._update_folder_button_text()
        lo.addWidget(self.folder_btn)

        lo.addSpacing(8)

        sim_row = QHBoxLayout()
        sim_row.setSpacing(10)
        sim_label = QLabel("Точность подбора похожих треков")
        sim_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        sim_row.addWidget(sim_label)
        sim_row.addStretch()
        self._sim_slider = ClickableSlider(Qt.Horizontal)
        self._sim_slider.setRange(0, 20)
        self._sim_slider.setValue(self._settings.similarity_precision)
        self._sim_slider.setFixedWidth(280)
        self._sim_slider.setCursor(Qt.PointingHandCursor)
        self._sim_slider.valueChanged.connect(self._on_similarity_changed)
        self._update_slider_style()
        sim_row.addWidget(self._sim_slider)
        lo.addLayout(sim_row)

        lo.addStretch()

    def _on_similarity_changed(self, value: int):
        self._settings.similarity_precision = value
        self.similarity_precision_changed.emit(value)

    def set_folder_path(self, folder: str):
        if folder and os.path.isdir(folder):
            self.folder_btn.setText(folder)
            self._update_folder_button_style(True)
        else:
            self.folder_btn.setText("Укажите корневую папку с музыкой")
            self._update_folder_button_style(False)

    def _update_folder_button_style(self, has_folder: bool):
        accent = cfg.get_accent_color()
        border_color = "rgba(80, 80, 80, 0.5)" if has_folder else "#FF4444"
        self.folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {border_color};
                color: {accent};
                font-size: 13px;
                text-align: left;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(80, 80, 80, 0.3);
            }}
            QPushButton:pressed {{
                background-color: rgba(60, 60, 60, 0.4);
            }}
        """)

    def _update_folder_button_text(self):
        folder = self._settings.music_folder
        if folder and os.path.isdir(folder):
            self.folder_btn.setText(folder)
            self._update_folder_button_style(True)
        else:
            self.folder_btn.setText("Укажите корневую папку с музыкой")
            self._update_folder_button_style(False)

    def _update_slider_style(self):
        accent = cfg.get_accent_color()
        self._sim_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: rgba(80,80,80,0.5); border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -5px 0;
                background: {accent}; border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{ background: #FFFFFF; }}
            QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
        """)

    def apply_accent_color(self, color: str):
        self._update_slider_style()
        self._update_folder_button_style(
            bool(self._settings.music_folder and os.path.isdir(self._settings.music_folder))
        )
