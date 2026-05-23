import os

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QFileDialog, QWidget, QStackedWidget)
from PySide6.QtCore import Qt, QByteArray, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPaintEvent

from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer import config as cfg
from musicplayer.core.db import get_filtered_library_track_count, get_covers_cache_size, get_analyzed_track_count
from musicplayer.ui.svg_icons import get_music_note_svg

from .constants import ACCENT_PRESETS, format_size, get_library_track_count
from .widgets import TabButton
from .page_main import MainPage
from .page_appearance import AppearancePage
from .page_webserver import WebServerPage
from .page_system import SystemPage


class SettingsDialog(QDialog):
    """Frameless dialog for application settings."""

    accent_color_changed = Signal(str)
    dynamic_color_toggled = Signal(bool)
    web_server_toggled = Signal(bool)
    web_server_port_changed = Signal(int)
    music_folder_changed = Signal(bool)
    prevent_sleep_toggled = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(620, 420)
        self.setModal(True)

        self._build_ui()
        self._update_stats()

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

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: #000000; }")

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- Title bar ---
        self._build_title_bar(inner)

        # --- Body: sidebar tabs + stacked content ---
        self._build_body(inner)

        # --- Status bar ---
        self._build_status_bar(inner)

        layout.addWidget(container)

        self._update_tab_style()
        self._switch_tab(0)

    def _build_title_bar(self, inner: QVBoxLayout):
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        title_icon.renderer().load(QByteArray(get_music_note_svg(60).encode('utf-8')))
        title_layout.addWidget(title_icon)
        title_label = QLabel("Настройки")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        accent = cfg.get_accent_color()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; color: #FFFFFF;
                font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {accent}; }}
            QPushButton:pressed {{ background-color: #555555; }}
        """)
        close_btn.clicked.connect(self.accept)
        title_layout.addWidget(close_btn)
        self._close_btn = close_btn
        inner.addWidget(title_bar)

    def _build_body(self, inner: QVBoxLayout):
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar
        self._tab_btns = []
        sidebar = QWidget()
        sidebar.setFixedWidth(140)
        sidebar.setStyleSheet("background-color: #000000;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        tab_names = ["Основное", "Внешний вид", "Сервер и API", "Системные"]
        page_classes = [MainPage, AppearancePage, WebServerPage, SystemPage]
        self._pages = []
        for i, (name, page_cls) in enumerate(zip(tab_names, page_classes)):
            btn = TabButton(name, cfg.get_accent_color())
            btn.setProperty("tab_index", i)
            btn.clicked.connect(lambda checked=False, idx=i: self._switch_tab(idx))
            self._tab_btns.append(btn)
            sidebar_layout.addWidget(btn)
            if i < len(tab_names) - 1:
                sep_tab = QWidget()
                sep_tab.setFixedHeight(1)
                sep_tab.setStyleSheet("background-color: rgba(80, 80, 80, 0.2);")
                sidebar_layout.addWidget(sep_tab)

            # Create and wire page
            page = page_cls(self.settings)
            self._pages.append(page)

        sidebar_layout.addStretch()
        body.addWidget(sidebar)

        # Separator
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: rgba(80,80,80,0.2);")
        body.addWidget(sep)

        # Stacked content
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #000000;")
        for page in self._pages:
            self._stack.addWidget(page)
        body.addWidget(self._stack, 1)
        inner.addLayout(body)

        # Wire signals
        self._wire_page_signals()

    def _wire_page_signals(self):
        main_page = self._pages[0]
        appearance_page = self._pages[1]
        webserver_page = self._pages[2]
        system_page = self._pages[3]

        main_page.folder_browse_requested.connect(self._browse_folder)
        main_page.similarity_precision_changed.connect(self._on_similarity_precision_changed)

        appearance_page.accent_color_selected.connect(self._set_accent_color)
        appearance_page.dynamic_color_toggled.connect(self.dynamic_color_toggled.emit)
        appearance_page.mini_widget_toggled.connect(self._on_mini_widget_toggled)
        appearance_page.opacity_changed.connect(self._on_opacity_changed)

        webserver_page.web_server_toggled.connect(self._on_web_server_toggled)
        webserver_page.port_changed.connect(self._on_webserver_port_changed)

        system_page.prevent_sleep_toggled.connect(self._on_prevent_sleep_toggled)
        system_page.cleanup_finished.connect(self._on_cleanup_finished)

    def _build_status_bar(self, inner: QVBoxLayout):
        status_bar = QWidget()
        status_bar.setFixedHeight(32)
        status_bar.setStyleSheet("background-color: #0a0a0a;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 0, 16, 0)

        a = cfg.get_accent_color()
        self.library_count_label = QLabel()
        self.library_count_label.setStyleSheet(f"color: {a}; font-size: 13px;")
        status_layout.addWidget(self.library_count_label)
        status_layout.addStretch()
        self.covers_size_label = QLabel()
        self.covers_size_label.setStyleSheet(f"color: {a}; font-size: 13px;")
        status_layout.addWidget(self.covers_size_label)
        status_layout.addStretch()
        self._cleanup_result_label = QLabel()
        self._cleanup_result_label.setStyleSheet(f"color: {a}; font-size: 12px;")
        self._cleanup_result_label.setVisible(False)
        status_layout.addWidget(self._cleanup_result_label)
        status_layout.addStretch()
        from musicplayer import config as app_cfg
        self.version_label = QLabel(f"code by ramzes  v{app_cfg.APP_VERSION}")
        self.version_label.setStyleSheet(f"color: {cfg.get_accent_color()}; font-size: 13px;")
        status_layout.addWidget(self.version_label)
        status_layout.addSpacing(10)
        inner.addWidget(status_bar)

    def _switch_tab(self, idx: int):
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)

    def _update_tab_style(self):
        accent = cfg.get_accent_color()
        for btn in self._tab_btns:
            btn.set_accent(accent)

    def showEvent(self, event):
        super().showEvent(event)
        self._pages[2].refresh_status()

    def closeEvent(self, event):
        self._pages[2].cleanup()
        self._pages[3].cleanup()
        event.accept()

    # --- Signal handlers ---

    def _set_accent_color(self, color_hex: str):
        self.settings._data["accent_color"] = color_hex
        self.settings._save()

        import musicplayer.config
        musicplayer.config.ACCENT_COLOR = color_hex

        self._pages[1].highlight_color(color_hex)

        self.accent_color_changed.emit(color_hex)

    def _browse_folder(self):
        current = self.settings.music_folder or ""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите корневую папку с музыкой",
            current,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.settings.music_folder = folder
            self._pages[0].set_folder_path(folder)
            self.music_folder_changed.emit(True)

    def _on_web_server_toggled(self, checked: bool):
        self.settings.web_server_enabled = checked
        self.web_server_toggled.emit(checked)

    def _on_webserver_port_changed(self, port: int):
        self.settings.web_server_port = port
        self.web_server_port_changed.emit(port)

    def _on_mini_widget_toggled(self, checked: bool):
        self.settings.mini_widget_on_minimize = checked

    def _on_opacity_changed(self, value: int):
        self.settings.mini_widget_opacity = value

    def _on_prevent_sleep_toggled(self, checked: bool):
        self.prevent_sleep_toggled.emit(checked)

    def _on_similarity_precision_changed(self, value: int):
        self.settings.similarity_precision = value

    def _on_cleanup_finished(self, removed: int):
        if self.isVisible():
            self._cleanup_result_label.setText(f"Удалено треков: {removed}")
            self._cleanup_result_label.setVisible(True)
            self._update_stats()
            QTimer.singleShot(3000, lambda: self._cleanup_result_label.setVisible(False))

    def _update_stats(self):
        covers_size = get_covers_cache_size()
        self.covers_size_label.setText(f"Кеш обложек:  {format_size(covers_size)}")

        track_count = get_library_track_count()
        analyzed_count = get_analyzed_track_count()
        self.library_count_label.setText(f"Треков:  {track_count} ({analyzed_count})")

        current = self.settings._data.get("accent_color", ACCENT_PRESETS[0][0])
        self._pages[1].highlight_color(current)

    def apply_accent_color(self, color: str):
        self._update_tab_style()
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; color: #FFFFFF;
                font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {color}; }}
            QPushButton:pressed {{ background-color: #555555; }}
        """)
        self.library_count_label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self.covers_size_label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self.version_label.setStyleSheet(f"color: {color}; font-size: 14px;")

        for page in self._pages:
            page.apply_accent_color(color)

        self.update()
