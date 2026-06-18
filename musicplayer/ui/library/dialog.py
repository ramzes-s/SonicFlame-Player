"""
Library Dialog

Main dialog for the library view with tracks and artists tabs.
Uses QTableView + virtual model for performance with large datasets.
"""

import os
from typing import List

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QTableView, QHeaderView,
                               QWidget, QAbstractItemView, QComboBox,
                               QMenu, QStyleOptionViewItem, QStackedWidget, QTabBar)
from PySide6.QtCore import Qt, QPoint, QByteArray, Signal, QTimer, QModelIndex
from PySide6.QtGui import QAction
from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer import config as cfg
from musicplayer.core.db import (
    get_all_genres,
    get_tracks_by_artist,
)
from musicplayer.ui.svg_icons import get_music_note_svg
from musicplayer.ui.library.model import LibraryModel, MoodStarDelegate
from musicplayer.ui.library.worker import DataWorker
from musicplayer.ui.library.artist_view import ArtistViewWidget
from musicplayer.ui.library.settings import load_col_widths, save_col_widths
from musicplayer.ui.library.types import COLUMN_COUNT


class LibraryDialog(QDialog):
    track_selected = Signal(str)
    edit_tags_requested = Signal(str)
    artist_play_requested = Signal(str)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(1700, 900)
        self.setWindowTitle("Библиотека")

        self._drag_pos = QPoint()
        self._active_workers: List[DataWorker] = []
        self._is_quitting = False

        self._build_ui()
        self._initial_load()

    def register_worker(self, worker: DataWorker):
        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._on_worker_finished(worker))

    def _on_worker_finished(self, worker: DataWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if self._is_quitting and not self._active_workers:
            QApplication.instance().quit()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        tracks_tab = self._build_tracks_tab()
        self.artist_view_widget = ArtistViewWidget()
        self.artist_view_widget.artist_play_requested.connect(self.artist_play_requested)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(tracks_tab)
        self.stacked_widget.addWidget(self.artist_view_widget)

        self.main_layout.addWidget(self._create_integrated_title_bar())
        self.main_layout.addWidget(self.stacked_widget)

    def _build_tracks_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._filter_bar())
        layout.addWidget(self._build_table(), stretch=1)

        self.status_label = QLabel("Загрузка...")
        self.status_label.setStyleSheet(f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px; padding: 6px 16px;")
        layout.addWidget(self.status_label)

        return container

    def _create_integrated_title_bar(self):
        bar = QWidget()
        bar.setObjectName("integrated_title_bar")
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background-color: {cfg.BG_COLOR}; border-bottom: 1px solid {cfg.BG_COLOR};")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(15, 0, 10, 0)
        lay.setSpacing(10)

        icon_w = QSvgWidget()
        icon_w.setFixedSize(20, 20)
        icon_w.renderer().load(QByteArray(get_music_note_svg(60).encode('utf-8')))
        lay.addWidget(icon_w)

        lbl = QLabel("Библиотека")
        lbl.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 13px; font-weight: bold;")
        lay.addWidget(lbl)
        lay.addStretch()

        self.integrated_tab_bar = QTabBar(self)
        self.integrated_tab_bar.addTab("Треки")
        self.integrated_tab_bar.addTab("Исполнители")
        self.integrated_tab_bar.setStyleSheet(self._tab_style())

        self.integrated_tab_bar.currentChanged.connect(self.stacked_widget.setCurrentIndex)
        self.integrated_tab_bar.currentChanged.connect(self._on_tab_changed)

        lay.addWidget(self.integrated_tab_bar)

        btn = QPushButton("✕")
        btn.setFixedSize(36, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setObjectName("close_btn")
        accent = cfg.get_accent_color()
        btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {cfg.TEXT_COLOR}; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: {accent}; }}")
        btn.clicked.connect(self.close)
        lay.addWidget(btn)

        return bar

    def _filter_bar(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background-color: #0a0a0a; border-bottom: 1px solid rgba(80,80,80,0.3);")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setFixedHeight(30)
        self.search_edit.setPlaceholderText("Поиск по всем полям...")
        self.search_edit.setStyleSheet(self._input_style())
        self.search_edit.textChanged.connect(self._on_search_changed)
        lay.addWidget(self.search_edit, stretch=1)

        self.genre_cb = QComboBox()
        self.genre_cb.setFixedHeight(30)
        self.genre_cb.setFixedWidth(200)
        self.genre_cb.setStyleSheet(self._combo_style())
        self.genre_cb.addItem("Все жанры", "")
        self.genre_cb.currentIndexChanged.connect(self._on_genre_filter_changed)
        lay.addWidget(self.genre_cb)

        self.fav_btn = QPushButton("♡ Избранные")
        self.fav_btn.setFixedHeight(30)
        self.fav_btn.setFixedWidth(130)
        self.fav_btn.setCheckable(True)
        self.fav_btn.setCursor(Qt.PointingHandCursor)
        self.fav_btn.setStyleSheet(self._btn_style())
        self.fav_btn.toggled.connect(self._on_fav_filter_toggled)
        lay.addWidget(self.fav_btn)

        clear_btn = QPushButton("✕ Сброс")
        clear_btn.setFixedHeight(30)
        clear_btn.setFixedWidth(100)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(f"QPushButton {{ border: 1px solid {cfg.BUTTON_BORDER_COLOR}; font-size: 11px; font-weight: bold; }} QPushButton:hover {{ color: {cfg.get_accent_color()}; }}")
        clear_btn.clicked.connect(self._clear_filters)
        lay.addWidget(clear_btn)

        return bar

    def _build_table(self):
        self.model = LibraryModel(self)
        self.model.total_count_changed.connect(self._update_status_text)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.model.sort)

        self.table.setStyleSheet(self._table_style())
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)

        self.mood_delegate = MoodStarDelegate(self)
        self.table.setItemDelegateForColumn(9, self.mood_delegate)

        saved = load_col_widths()
        header = self.table.horizontalHeader()
        from musicplayer.ui.library.types import HEADERS
        for col, w in saved.items():
            if col < len(HEADERS):
                header.resizeSection(col, w)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        return self.table

    def _initial_load(self):
        worker = DataWorker(get_all_genres)
        worker.results_ready.connect(self._on_genres_ready)
        self.register_worker(worker)
        worker.start()

    def _on_genres_ready(self, genres):
        self.genre_cb.blockSignals(True)
        self.genre_cb.clear()
        self.genre_cb.addItem("Все жанры", "")
        self.genre_cb.addItems(genres)
        self.genre_cb.blockSignals(False)

        self.model.reset()

    def refresh_data(self):
        self._initial_load()

    def _update_status_text(self, count=None):
        if count is None:
            count = self.model.rowCount()
        self.status_label.setText(f"Найдено: {count} треков")

    def _on_tab_changed(self, index: int):
        if self.integrated_tab_bar.tabText(index) == "Исполнители":
            self.artist_view_widget.load_if_needed()

    def _on_search_changed(self, text: str):
        def _delayed_search(t=text):
            try:
                self.model.set_search_term(t)
            except RuntimeError:
                pass
        QTimer.singleShot(200, _delayed_search)

    def _on_genre_filter_changed(self, index: int):
        text = self.genre_cb.currentText()
        genre = "" if text == "Все жанры" else text
        self.model.set_genre_filter(genre)

    def _on_fav_filter_toggled(self, checked: bool):
        self.model.set_fav_only_filter(checked)
        accent = cfg.get_accent_color()
        if checked:
            self.fav_btn.setStyleSheet(f"background: {accent}33; border: 1px solid {accent}66; color: {accent}; font-size: 11px; font-weight: bold;")
            self.fav_btn.setText("♡ Избранные ✓")
        else:
            self.fav_btn.setStyleSheet(self._btn_style())
            self.fav_btn.setText("♡ Избранные")

    def _clear_filters(self):
        self.search_edit.clear()
        self.genre_cb.setCurrentIndex(0)
        self.fav_btn.setChecked(False)

    def on_accent_color_changed(self, color: str):
        if cfg.get_accent_color() != color:
            cfg.ACCENT_COLOR = color
            self._update_styles()
            self.artist_view_widget.update_accent_color()

    def _update_styles(self):
        self.search_edit.setStyleSheet(self._input_style())
        self.genre_cb.setStyleSheet(self._combo_style())
        self.table.setStyleSheet(self._table_style())
        if hasattr(self, 'integrated_tab_bar') and self.integrated_tab_bar:
            self.integrated_tab_bar.setStyleSheet(self._tab_style())

        integrated_title_bar = self.findChild(QWidget, "integrated_title_bar")
        if integrated_title_bar:
            integrated_title_bar.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        clear_btn = self.findChild(QPushButton, "clear_btn")
        if clear_btn:
            clear_btn.setStyleSheet(f"QPushButton {{ border: 1px solid {cfg.BUTTON_BORDER_COLOR}; font-size: 11px; font-weight: bold; }} QPushButton:hover {{ color: {cfg.get_accent_color()}; }}")
        self._on_fav_filter_toggled(self.fav_btn.isChecked())

    def _on_double_click(self, index: QModelIndex):
        track = self.model.get_track(index.row())
        if track:
            self.track_selected.emit(track.filepath)

    def closeEvent(self, event):
        self._is_quitting = True
        for worker in self._active_workers:
            worker.requestInterruption()

        if not self._active_workers:
            self.save_and_quit(event)
        else:
            event.ignore()
            self.hide()

    def save_and_quit(self, event):
        widths = {col: self.table.horizontalHeader().sectionSize(col) for col in range(COLUMN_COUNT)}
        save_col_widths(widths)
        self.closed.emit()
        event.accept()

    def _input_style(self):
        return f"QLineEdit {{ background: transparent; border: none; border-bottom: 1px solid {cfg.INPUT_BORDER_COLOR}; padding: 0 10px 0 4px; color: {cfg.INPUT_TEXT_COLOR}; font-size: 12px; }} QLineEdit:focus {{ border-bottom-color: {cfg.get_accent_color()}; }}"

    def _combo_style(self):
        return f"QComboBox {{ background: {cfg.INPUT_BG_COLOR}; border: 1px solid {cfg.INPUT_BORDER_COLOR}; padding: 0 8px; color: {cfg.INPUT_TEXT_COLOR}; font-size: 12px; }} QComboBox::drop-down {{ border: none; width: 20px; }} QComboBox QAbstractItemView::item:selected {{ background-color: {cfg.get_accent_color()}33; outline: none; }}"

    def _btn_style(self):
        return f"QPushButton {{ background: {cfg.INPUT_BG_COLOR}; border: 1px solid {cfg.INPUT_BORDER_COLOR}; color: #AAA; font-size: 11px; }} QPushButton:hover {{ color: {cfg.get_accent_color()};}}"

    def _tab_style(self):
        accent = cfg.get_accent_color()
        return f"""
            QTabBar {{
                border: none;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {cfg.SECONDARY_TEXT_COLOR};
                font-weight: bold;
                padding: 6px 25px;
                width: 150px;
                border: none;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background: {cfg.BG_COLOR};
                color: {accent};
                border: none;
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                color: {cfg.TEXT_COLOR};
                background: transparent;
                border: none;
                border-bottom: none;
            }}
        """

    def _table_style(self):
        accent = cfg.get_accent_color()
        r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        sel = f"rgba({r},{g},{b},40)"
        return f"QTableView {{ background: {cfg.BG_COLOR}; border: none; gridline-color: rgba({cfg.DIVIDER_ITEM_RGB[0]},{cfg.DIVIDER_ITEM_RGB[1]},{cfg.DIVIDER_ITEM_RGB[2]},{cfg.DIVIDER_ITEM_ALPHA}); color: {cfg.TEXT_COLOR}; font-size: 12px; }} QTableView::item {{ padding: 4px 8px; border-bottom: 1px solid rgba({cfg.DIVIDER_ITEM_RGB[0]},{cfg.DIVIDER_ITEM_RGB[1]},{cfg.DIVIDER_ITEM_RGB[2]},{cfg.DIVIDER_ITEM_ALPHA}); }} QTableView::item:selected {{ background: {sel}; color: {cfg.TEXT_COLOR}; }} QHeaderView::section {{ background: #0a0a0a; color: #AAA; padding: 6px 8px; border: none; border-bottom: 1px solid rgba(80,80,80,0.3); font-size: 11px; font-weight: bold; }} QHeaderView::section:hover {{ color: {cfg.TEXT_COLOR}; background: #151515; }} QScrollBar:vertical {{ background: {cfg.BG_COLOR}; width: 6px; }} QScrollBar::handle:vertical {{ background: {cfg.DIVIDER_COLOR}; min-height: 30px; }} QScrollBar:horizontal {{ background: {cfg.BG_COLOR}; height: 6px; }}"

    def _show_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        track = self.model.get_track(idx.row())
        if not track:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: {cfg.SECONDARY_BG_COLOR}; border: 1px solid #505050; padding: 4px 0; color: {cfg.TEXT_COLOR}; }} QMenu::item:selected {{ background: {cfg.get_accent_color()}66; }}")
        act_play = QAction("Воспроизвести", menu)
        act_play.triggered.connect(lambda: self.track_selected.emit(track.filepath))
        menu.addAction(act_play)
        act_play_artist = QAction("Воспроизвести Артиста", menu)
        act_play_artist.triggered.connect(lambda: self.artist_play_requested.emit(track.artist))
        menu.addAction(act_play_artist)
        menu.addSeparator()
        act_edit = QAction("Редактировать теги", menu)
        act_edit.triggered.connect(lambda: self.edit_tags_requested.emit(track.filepath))
        menu.addAction(act_edit)
        act_explore = QAction("Открыть в проводнике", menu)
        act_explore.triggered.connect(lambda: os.startfile(os.path.dirname(track.filepath)))
        menu.addAction(act_explore)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)