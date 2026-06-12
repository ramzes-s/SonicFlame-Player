import os

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QWidget, QStackedWidget)
from PySide6.QtCore import Qt, QByteArray, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPaintEvent

from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer import config as cfg
from musicplayer.core.db import get_covers_cache_info, get_artist_collage_cache_info, get_analyzed_track_count
from musicplayer.ui.svg_icons import get_music_note_svg

from .constants import ACCENT_PRESETS, get_library_track_count
from .widgets import TabButton
from .page_main import MainPage
from .page_appearance import AppearancePage
from .page_webserver import WebServerPage
from .page_system import SystemPage
from .page_plugins import PluginsPage
from .page_about import AboutPage


class SettingsDialog(QDialog):
    """Frameless dialog for application settings."""

    accent_color_changed = Signal(str)
    dynamic_color_toggled = Signal(bool)
    web_server_toggled = Signal(bool)
    web_server_port_changed = Signal(int)
    music_folder_changed = Signal(bool)
    db_reset_requested = Signal()
    prevent_sleep_toggled = Signal(bool)
    audio_device_changed = Signal(object)

    def __init__(self, settings, parent=None, plugin_pages=None, plugin_infos=None,
                 plugin_manager=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        #self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        #self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMinimumSize(720, 500)
        self.setModal(True)
        self.resize(760, 520)
        self.settings = settings
        self._plugin_pages = plugin_pages or []
        self._plugin_infos = plugin_infos or []
        self._plugin_manager = plugin_manager

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
        container.setStyleSheet(f"#container {{ background-color: {cfg.BG_COLOR}; }}")

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- Title bar ---
        self._build_title_bar(inner)

        # --- Body: sidebar tabs + stacked content ---
        self._build_body(inner)

        layout.addWidget(container)

        self._update_tab_style()
        self._switch_tab(0)

    def _build_title_bar(self, inner: QVBoxLayout):
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        title_icon.renderer().load(QByteArray(get_music_note_svg(60).encode('utf-8')))
        title_layout.addWidget(title_icon)
        title_label = QLabel("Настройки")
        title_label.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        accent = cfg.get_accent_color()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; color: {cfg.TEXT_COLOR};
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
        sidebar.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        tab_names = ["Основное", "Внешний вид", "Сервер и API", "Плагины", "Системные"]
        page_classes = [MainPage, AppearancePage, WebServerPage,
                        lambda s: PluginsPage(s, self._plugin_infos, self._plugin_manager), SystemPage]
        self._pages = []

        def _add_tab(name, page_widget):
            idx = len(self._pages)
            btn = TabButton(name, cfg.get_accent_color())
            btn.setProperty("tab_index", idx)
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_tab(i))
            self._tab_btns.append(btn)
            sidebar_layout.addWidget(btn)
            sep_tab = QWidget()
            sep_tab.setFixedHeight(1)
            sep_tab.setStyleSheet(f"background-color: {cfg.DIVIDER_ITEM_COLOR};")
            sidebar_layout.addWidget(sep_tab)
            self._pages.append(page_widget)

        for name, page_cls in zip(tab_names, page_classes):
            _add_tab(name, page_cls(self.settings))

        for widget_factory, name in self._plugin_pages:
            _add_tab(name, widget_factory())

        # About page — always last
        _add_tab("О программе", AboutPage(self.settings))

        sidebar_layout.addStretch()
        body.addWidget(sidebar)

        # Separator
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {cfg.DIVIDER_ITEM_COLOR};")
        body.addWidget(sep)

        # Stacked content
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
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
        system_page = self._pages[4]

        main_page.folder_browse_requested.connect(self._browse_folder)
        main_page.similarity_precision_changed.connect(self._on_similarity_precision_changed)
        main_page.analysis_duration_changed.connect(self._on_analysis_duration_changed)

        appearance_page.accent_color_selected.connect(self._set_accent_color)
        appearance_page.dynamic_color_toggled.connect(self.dynamic_color_toggled.emit)
        appearance_page.mini_widget_toggled.connect(self._on_mini_widget_toggled)
        appearance_page.opacity_changed.connect(self._on_opacity_changed)

        webserver_page.web_server_toggled.connect(self._on_web_server_toggled)
        webserver_page.port_changed.connect(self._on_webserver_port_changed)

        system_page.prevent_sleep_toggled.connect(self._on_prevent_sleep_toggled)
        system_page.audio_device_changed.connect(self.audio_device_changed.emit)
        system_page.cleanup_finished.connect(self._update_stats)
        system_page.db_reset_requested.connect(self.db_reset_requested.emit)

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
        self._pages[4].cleanup()
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
        from musicplayer.ui.folder_browse.dialog import FolderBrowseDialog
        dlg = FolderBrowseDialog(
            parent=self,
            title="Выберите корневую папку с музыкой",
            start_path=self.settings.music_folder or "",
            root_path=None
        )
        if dlg.exec() == 1:
            folder = dlg.selected_path
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

    def _on_analysis_duration_changed(self, value: int):
        self.settings.analysis_duration = value

    def _update_stats(self):
        track_count = get_library_track_count()
        analyzed_count = get_analyzed_track_count()
        covers_count, covers_size = get_covers_cache_info()
        collages_count, collages_size = get_artist_collage_cache_info()
        self._pages[4].update_stats(track_count, analyzed_count,
                                    covers_count, covers_size,
                                    collages_count, collages_size)

        current = self.settings._data.get("accent_color", ACCENT_PRESETS[0][0])
        self._pages[1].highlight_color(current)

    def apply_accent_color(self, color: str):
        self._update_tab_style()
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; color: {cfg.TEXT_COLOR};
                font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {color}; }}
            QPushButton:pressed {{ background-color: #555555; }}
        """)
        for page in self._pages:
            page.apply_accent_color(color)

        self.update()
