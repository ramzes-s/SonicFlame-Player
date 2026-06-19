import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QStyledItemDelegate, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from musicplayer import config as cfg
from .widgets import ClickableSlider


class _TallItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(sz.height(), 44))
        return sz


class MainPage(QWidget):
    folder_browse_requested = Signal()
    similarity_precision_changed = Signal(int)
    analysis_duration_changed = Signal(int)
    language_filter_changed = Signal(str)
    max_similar_tracks_changed = Signal(int)

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

        # Fade on play/pause (0 = off)
        fade_row = QHBoxLayout()
        fade_row.setSpacing(10)
        fade_label = QLabel("Затухание при паузе/воспроизведении")
        fade_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        fade_row.addWidget(fade_label)
        fade_row.addStretch()
        self._fade_slider = ClickableSlider(Qt.Horizontal)
        self._fade_slider.setRange(0, 5)
        self._fade_slider.setValue(self._settings.fade_duration)
        self._fade_slider.setFixedWidth(280)
        self._fade_slider.setCursor(Qt.PointingHandCursor)
        self._fade_slider.valueChanged.connect(self._on_fade_duration_changed)
        self._apply_slider_style(self._fade_slider)
        self._fade_value = QLabel(f"{self._settings.fade_duration}с")
        self._fade_value.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 13px;")
        fade_row.addWidget(self._fade_value)
        fade_row.addWidget(self._fade_slider)
        lo.addLayout(fade_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"QFrame {{ color: {cfg.DIVIDER_COLOR}; max-height: 1px; }}")
        lo.addWidget(sep)

        lo.addSpacing(8)

        sim_row = QHBoxLayout()
        sim_row.setSpacing(10)
        sim_label = QLabel("Точность подбора похожих треков")
        sim_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        sim_row.addWidget(sim_label)
        sim_row.addStretch()
        self._sim_slider = ClickableSlider(Qt.Horizontal)
        self._sim_slider.setRange(0, 40)
        self._sim_slider.setValue(self._settings.similarity_precision)
        self._sim_slider.setFixedWidth(280)
        self._sim_slider.setCursor(Qt.PointingHandCursor)
        self._sim_slider.valueChanged.connect(self._on_similarity_changed)
        self._update_slider_style()
        sim_row.addWidget(self._sim_slider)
        lo.addLayout(sim_row)

        # Analysis duration slider
        dur_row = QHBoxLayout()
        dur_row.setSpacing(10)
        dur_label = QLabel("Длительность анализа треков")
        dur_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        dur_row.addWidget(dur_label)
        dur_row.addStretch()
        self._dur_slider = ClickableSlider(Qt.Horizontal)
        self._dur_slider.setRange(30, 60)
        self._dur_slider.setPageStep(10)
        self._dur_slider.setSingleStep(10)
        # ticks handled by snapping logic in _on_duration_changed
        self._dur_slider.setValue(self._settings.analysis_duration)
        self._dur_slider.setFixedWidth(280)
        self._dur_slider.setCursor(Qt.PointingHandCursor)
        self._dur_slider.valueChanged.connect(self._on_duration_changed)
        self._apply_slider_style(self._dur_slider)
        dur_value = QLabel(f"{self._settings.analysis_duration}с")
        dur_value.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 13px;")
        dur_row.addWidget(dur_value)
        self._dur_value_label = dur_value
        dur_row.addWidget(self._dur_slider)
        lo.addLayout(dur_row)

        # Max similar tracks
        max_sim_row = QHBoxLayout()
        max_sim_row.setSpacing(10)
        max_sim_label = QLabel("Максимум похожих треков")
        max_sim_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        max_sim_row.addWidget(max_sim_label)
        max_sim_row.addStretch()
        self._max_sim_slider = ClickableSlider(Qt.Horizontal)
        self._max_sim_slider.setRange(50, 200)
        self._max_sim_slider.setPageStep(10)
        self._max_sim_slider.setSingleStep(10)
        self._max_sim_slider.setValue(self._settings.max_similar_tracks)
        self._max_sim_slider.setFixedWidth(280)
        self._max_sim_slider.setCursor(Qt.PointingHandCursor)
        self._max_sim_slider.valueChanged.connect(self._on_max_sim_changed)
        self._apply_slider_style(self._max_sim_slider)
        self._max_sim_value = QLabel(f"{self._settings.max_similar_tracks}")
        self._max_sim_value.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 13px;")
        max_sim_row.addWidget(self._max_sim_value)
        max_sim_row.addWidget(self._max_sim_slider)
        lo.addLayout(max_sim_row)

        # Language filter mode
        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        lang_label = QLabel("Фильтр языка при подборе")
        lang_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        lang_row.addWidget(lang_label)
        lang_row.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.setFixedWidth(280)
        self._lang_combo.setItemDelegate(_TallItemDelegate(self._lang_combo))
        self._lang_combo.addItem("Не учитывать", "off")
        self._lang_combo.addItem("Понижать вес", "penalty")
        self._lang_combo.addItem("Исключать", "exclude")
        mode = self._settings.language_filter_mode
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == mode:
                self._lang_combo.setCurrentIndex(i)
                break
        self._lang_combo.currentIndexChanged.connect(self._on_lang_filter_changed)
        lang_row.addWidget(self._lang_combo)
        lo.addLayout(lang_row)
        self._apply_lang_combo_style()

        lo.addStretch()

    def _apply_lang_combo_style(self):
        accent = cfg.get_accent_color()
        self._lang_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {cfg.BG_COLOR};
                border: none;
                outline: none;
                border-bottom: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                font-size: 13px;
                padding: 1px 8px 1px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
                outline: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cfg.BG_COLOR};
                border: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                outline: none;
                margin: 0px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::viewport {{
                background-color: {cfg.BG_COLOR};
                border: none;
            }}
        """)

    def _on_similarity_changed(self, value: int):
        self._settings.similarity_precision = value
        self.similarity_precision_changed.emit(value)

    def _on_duration_changed(self, value: int):
        snapped = round(value / 10) * 10
        if snapped != value:
            self._dur_slider.blockSignals(True)
            self._dur_slider.setValue(snapped)
            self._dur_slider.blockSignals(False)
        self._settings.analysis_duration = snapped
        self._dur_value_label.setText(f"{snapped}с")
        self.analysis_duration_changed.emit(snapped)

    def _on_lang_filter_changed(self, idx: int):
        mode = self._lang_combo.itemData(idx)
        self._settings.language_filter_mode = mode
        self.language_filter_changed.emit(mode)

    def _on_max_sim_changed(self, value: int):
        snapped = round(value / 10) * 10
        if snapped != value:
            self._max_sim_slider.blockSignals(True)
            self._max_sim_slider.setValue(snapped)
            self._max_sim_slider.blockSignals(False)
        self._settings.max_similar_tracks = snapped
        self._max_sim_value.setText(f"{snapped}")
        self.max_similar_tracks_changed.emit(snapped)

    def _on_fade_duration_changed(self, value: int):
        self._settings.fade_duration = value
        self._fade_value.setText(f"{value}с")

    def set_folder_path(self, folder: str):
        if folder and os.path.isdir(folder):
            self.folder_btn.setText(folder)
            self._update_folder_button_style(True)
        else:
            self.folder_btn.setText("Укажите корневую папку с музыкой")
            self._update_folder_button_style(False)

    def _update_folder_button_style(self, has_folder: bool):
        accent = cfg.get_accent_color()
        border_color = cfg.DIVIDER_COLOR if has_folder else "#FF4444"
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
                background-color: {cfg.BUTTON_PRESSED_BG_COLOR};
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

    def _apply_slider_style(self, slider):
        accent = cfg.get_accent_color()
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {cfg.DIVIDER_COLOR}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -5px 0;
                background: {accent}; border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{ background: {cfg.TEXT_COLOR}; }}
            QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
        """)

    def _update_slider_style(self):
        if hasattr(self, '_sim_slider'):
            self._apply_slider_style(self._sim_slider)
        if hasattr(self, '_dur_slider'):
            self._apply_slider_style(self._dur_slider)
        if hasattr(self, '_max_sim_slider'):
            self._apply_slider_style(self._max_sim_slider)
        if hasattr(self, '_fade_slider'):
            self._apply_slider_style(self._fade_slider)

    def apply_accent_color(self, color: str):
        self._update_slider_style()
        self._update_folder_button_style(
            bool(self._settings.music_folder and os.path.isdir(self._settings.music_folder))
        )
        self._apply_lang_combo_style()
