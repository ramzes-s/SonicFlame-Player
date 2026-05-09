"""
Library Dialog — Virtual Model Implementation

Uses QTableView + a custom virtual QAbstractTableModel for extreme performance
with very large datasets. Data is fetched from the database in pages on-demand
as the user scrolls. Sorting and filtering are delegated to the database.
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Any, Callable, Dict, Tuple

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QFileDialog,
                               QTableView, QHeaderView, QStyledItemDelegate,
                               QWidget, QAbstractItemView, QComboBox,
                               QMenu, QProgressBar, QStyleOptionViewItem, QTabWidget, QStackedWidget, QTabBar)
from PySide6.QtCore import (Qt, QPoint, QSize, QByteArray, Signal, QThread,
                            QTimer, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QItemSelectionModel)
from PySide6.QtGui import (QFont, QColor, QPainter, QIcon, QPixmap, QCursor, QAction,
                           QPainterPath)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtSvg import QSvgRenderer

from musicplayer import config as cfg
from musicplayer.core.db import (
    get_filtered_library_track_count,
    get_library_tracks_page,
    get_all_genres,
    get_favorite_filepaths,
    is_favorite as db_is_favorite,
    get_db_mtime,
    get_all_folders,
    normalize_path,
)
from musicplayer.utils.helpers import format_duration, get_color_from_features
from musicplayer.ui.svg_icons import get_music_note_svg
from musicplayer.ui.artist_view_widget import ArtistViewWidget

import math

# ============================================================
# Data Structures
# ============================================================

class Track:
    """Lightweight data class for tracks displayed in the UI."""
    __slots__ = ('filepath', 'title', 'artist', 'album', 'genre',
                 'duration', 'bitrate', 'folder', 'play_count',
                 'tempo', 'energy', 'mood')

    def __init__(self, filepath, title, artist, album, genre,
                 duration, bitrate, folder, play_count,
                 tempo, energy, mood):
        self.filepath = filepath
        self.title = title
        self.artist = artist
        self.album = album
        self.genre = genre
        self.duration = duration
        self.bitrate = bitrate
        self.folder = folder
        self.play_count = play_count
        self.tempo = tempo
        self.energy = energy
        self.mood = mood

# Column definitions
COL_TITLE = 0
COL_ARTIST = 1
COL_ALBUM = 2
COL_GENRE = 3
COL_FOLDER = 4
COL_DURATION = 5
COL_BITRATE = 6
COL_PLAY_COUNT = 7
COL_FAVORITE = 8
COL_MOOD = 9
COLUMN_COUNT = 10

HEADERS = ["Название", "Артист", "Альбом", "Жанр", "Папка", "Длительность", "Битрейт", "Топ", "♡", "★"]

# ============================================================
# Custom Delegate for Mood Star
# ============================================================

class MoodStarDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Let the base class handle selection background etc.
        super().paint(painter, option, QModelIndex())

        features = index.data(Qt.UserRole)
        if not features or not isinstance(features, tuple) or len(features) != 3:
            return

        tempo, energy, mood = features
        if tempo <= 0.0:
            return

        star_color = get_color_from_features(tempo, energy, mood)
        star_size = 16 # Small star for table cell

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(star_color)

        star_path = QPainterPath()
        num_points = 5
        outer_radius = star_size / 2
        inner_radius = outer_radius / 2.5
        
        start_angle = -math.pi / 2
        angle_step = math.pi / num_points

        center_x = option.rect.center().x()
        center_y = option.rect.center().y()

        star_path.moveTo(
            center_x + outer_radius * math.cos(start_angle),
            center_y + outer_radius * math.sin(start_angle)
        )
        for i in range(num_points * 2):
            angle = start_angle + i * angle_step
            radius = inner_radius if i % 2 == 1 else outer_radius
            star_path.lineTo(
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle)
            )
        star_path.closeSubpath()
        
        painter.drawPath(star_path)
        painter.restore()


# ============================================================
# Generic Worker Thread
# ============================================================
class DataWorker(QThread):
    """A generic worker thread to run a function with args and emit results."""
    results_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            if self.isInterruptionRequested(): return
            result = self._func(*self._args, **self._kwargs)
            if self.isInterruptionRequested(): return
            self.results_ready.emit(result)
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))

# ============================================================
# Virtual Table Model
# ============================================================
class LibraryModel(QAbstractTableModel):
    """A virtual table model that fetches data from the DB on demand."""
    PAGE_SIZE = 250
    
    total_count_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: Dict[int, Track] = {}
        self._total_rows = 0
        self._fav_set = set()
        
        # Filter and sort state
        self._search_term = ""
        self._genre_filter = ""
        self._folder_filter = ""
        self._fav_only = False
        self._sort_col = "Название"
        self._sort_ord = "ASC"

        self.worker: Optional[DataWorker] = None

    # --- Public API for Dialog ---
    
    def set_fav_set(self, fav_set: set):
        self._fav_set = fav_set
        self.reset()

    def set_search_term(self, term: str):
        self._search_term = term
        self.reset()

    def set_genre_filter(self, genre: str):
        self._genre_filter = genre
        self.reset()

    def set_folder_filter(self, folder: str):
        self._folder_filter = folder
        self.reset()

    def set_fav_only_filter(self, state: bool):
        self._fav_only = state
        self.reset()

    def sort(self, column: int, order: Qt.SortOrder):
        if column >= len(HEADERS): return
        self._sort_col = HEADERS[column]
        self._sort_ord = "ASC" if order == Qt.AscendingOrder else "DESC"
        
        # Clear cache and notify view that all data needs to be redrawn
        self._cache.clear()
        self.dataChanged.emit(self.index(0, 0), self.index(self._total_rows -1, self.columnCount() - 1))

        # Fetch the first page with the new sorting
        if self._total_rows > 0:
            self.fetchMore(QModelIndex())

    def get_track(self, row: int) -> Optional[Track]:
        return self._cache.get(row)

    # --- QAbstractTableModel Implementation ---

    def rowCount(self, parent=QModelIndex()):
        return self._total_rows

    def columnCount(self, parent=QModelIndex()):
        return COLUMN_COUNT

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row, col = index.row(), index.column()
        
        if row not in self._cache:
            self.fetchMore(index)
        
        track = self._cache.get(row)
        
        if track is None:
            if role == Qt.DisplayRole: return "..."
            return None

        # --- Display Roles ---
        if role == Qt.DisplayRole:
            if col == COL_TITLE: return track.title
            if col == COL_ARTIST: return track.artist
            if col == COL_ALBUM: return track.album
            if col == COL_GENRE: return track.genre or ""
            if col == COL_FOLDER: return track.folder
            if col == COL_DURATION: return format_duration(track.duration)
            if col == COL_BITRATE: return f"{track.bitrate} kbps" if track.bitrate else ""
            if col == COL_PLAY_COUNT: return str(track.play_count) if track.play_count else "0"
            if col == COL_FAVORITE: return "♥" if track.filepath in self._fav_set else ""
            return None

        # --- Other Roles ---
        if role == Qt.TextAlignmentRole and col in (COL_DURATION, COL_BITRATE, COL_PLAY_COUNT, COL_FAVORITE, COL_MOOD):
            return Qt.AlignCenter
        
        if role == Qt.FontRole and col in (COL_GENRE, COL_FOLDER, COL_BITRATE, COL_PLAY_COUNT):
            return QFont("Segoe UI", 9)
        
        if role == Qt.ForegroundRole and col == COL_FAVORITE and track.filepath in self._fav_set:
            return QColor(cfg.get_accent_color())

        if role == Qt.UserRole and col == COL_MOOD:
            return (track.tempo, track.energy, track.mood)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[section]
        return None

    # --- Virtual Model Logic (Lazy Loading) ---

    def canFetchMore(self, parent: QModelIndex) -> bool:
        return self._total_rows > len(self._cache)

    def fetchMore(self, parent: QModelIndex):
        if self.worker and self.worker.isRunning():
            return
            
        last_row = 0
        if parent.isValid():
            last_row = parent.row()
        
        remaining = self._total_rows - last_row
        items_to_fetch = min(self.PAGE_SIZE, remaining)

        if items_to_fetch <= 0:
            return
            
        self._fetch_page(last_row, items_to_fetch)
    
    def _fetch_page(self, offset, limit):
        if self.worker and self.worker.isRunning(): return
            
        self.worker = DataWorker(self._get_tracks_page_from_db, offset, limit)
        self.worker.results_ready.connect(self._on_page_fetched)
        # The dialog will manage the worker's lifetime
        self.parent().register_worker(self.worker)
        self.worker.start()

    def _on_page_fetched(self, result: Tuple[int, List[Track]]):
        offset, tracks = result
        if not tracks: return

        # No begin/end insert needed as we are just updating data
        for i, track in enumerate(tracks):
            self._cache[offset + i] = track
        
        top_left = self.index(offset, 0)
        bottom_right = self.index(offset + len(tracks) - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)

    def _get_tracks_page_from_db(self, offset, limit):
        # This runs in the worker thread
        tracks_info = get_library_tracks_page(
            offset, limit, sort_col=self._sort_col, sort_ord=self._sort_ord,
            search_term=self._search_term, genre_filter=self._genre_filter,
            folder_filter=self._folder_filter, fav_only=self._fav_only
        )
        tracks = []
        for ti in tracks_info:
            try: folder = str(Path(ti.filepath).parent.name)
            except Exception: folder = ""
            tracks.append(Track(
                filepath=ti.filepath, title=ti.title or "", artist=ti.artist or "Unknown Artist",
                album=ti.album or "Unknown Album", genre=ti.genre or "",
                duration=ti.duration or 0.0, bitrate=getattr(ti, 'bitrate', 0),
                folder=folder, play_count=getattr(ti, 'play_count', 0),
                tempo=getattr(ti, 'tempo', 0.0),
                energy=getattr(ti, 'energy', 0.0),
                mood=getattr(ti, 'mood', 0.0),
            ))
        return offset, tracks

    def reset(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()

        self.beginResetModel()
        self._cache.clear()
        self._total_rows = 0
        self.endResetModel()

        self.worker = DataWorker(
            get_filtered_library_track_count,
            search_term=self._search_term, genre_filter=self._genre_filter,
            folder_filter=self._folder_filter, fav_only=self._fav_only
        )
        self.worker.results_ready.connect(self._on_total_count_ready)
        self.parent().register_worker(self.worker)
        self.worker.start()

    def _on_total_count_ready(self, count):
        self.beginResetModel()
        self._total_rows = count
        self.endResetModel()
        self.total_count_changed.emit(count)
        if count > 0:
            self.fetchMore(QModelIndex())

# ============================================================
# Dialog
# ============================================================
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

        self.stacked_widget = QStackedWidget() # For displaying actual content
        self.stacked_widget.addWidget(tracks_tab)
        self.stacked_widget.addWidget(self.artist_view_widget)
        
        self.main_layout.addWidget(self._create_integrated_title_bar())
        self.main_layout.addWidget(self.stacked_widget) # This will display the content

    def _build_tracks_tab(self) -> QWidget:
        """Builds the content for the 'Tracks' tab."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        layout.addWidget(self._filter_bar())
        layout.addWidget(self._build_table(), stretch=1)
        
        self.status_label = QLabel("Загрузка…")
        self.status_label.setStyleSheet("color: #666666; font-size: 11px; padding: 6px 16px;")
        layout.addWidget(self.status_label)
        
        return container

    def _create_integrated_title_bar(self):
        bar = QWidget()
        bar.setObjectName("integrated_title_bar") # Add object name here
        bar.setFixedHeight(40)
        bar.setStyleSheet("background-color: #000000; border-bottom: 1px solid #000000;")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(15, 0, 10, 0)
        lay.setSpacing(10)

        # Icon
        icon_w = QSvgWidget()
        icon_w.setFixedSize(20, 20)
        icon_w.renderer().load(QByteArray(get_music_note_svg(60).encode('utf-8')))
        lay.addWidget(icon_w)

        lbl = QLabel("Библиотека")
        lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        lay.addWidget(lbl)
        lay.addStretch() # Add stretch after the label

        # Tabs (QTabBar)
        self.integrated_tab_bar = QTabBar(self) # Store as instance variable
        self.integrated_tab_bar.addTab("Треки")
        self.integrated_tab_bar.addTab("Исполнители")
        self.integrated_tab_bar.setStyleSheet(self._tab_style()) # Apply styles

        # Connect signals: new tab bar to stacked widget and existing _on_tab_changed
        self.integrated_tab_bar.currentChanged.connect(self.stacked_widget.setCurrentIndex)
        self.integrated_tab_bar.currentChanged.connect(self._on_tab_changed)

        lay.addWidget(self.integrated_tab_bar) # Removed stretch=1

        # Close button
        btn = QPushButton("✕")
        btn.setFixedSize(36, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setObjectName("close_btn")
        accent = cfg.get_accent_color()
        btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: #FFF; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: {accent}; }}")
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

        self.folder_cb = QComboBox()
        self.folder_cb.setFixedHeight(30)
        self.folder_cb.setFixedWidth(280)
        self.folder_cb.setStyleSheet(self._combo_style())
        self.folder_cb.addItem("Все папки", "")
        self.folder_cb.currentIndexChanged.connect(self._on_folder_filter_changed)
        lay.addWidget(self.folder_cb)

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
        clear_btn.setStyleSheet(f"QPushButton {{ border: 1px solid rgba(60,60,60,0.5); font-size: 11px; font-weight: bold; }} QPushButton:hover {{ color: {cfg.get_accent_color()}; }}")
        clear_btn.clicked.connect(self._clear_filters)
        lay.addWidget(clear_btn)
        
        return bar

    def _build_table(self):
        self.model = LibraryModel(self)
        self.model.total_count_changed.connect(self._update_status_text)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicator(COL_TITLE, Qt.AscendingOrder)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.model.sort)

        self.table.setStyleSheet(self._table_style())
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)

        # Apply custom delegate for the mood star column
        self.mood_delegate = MoodStarDelegate(self)
        self.table.setItemDelegateForColumn(COL_MOOD, self.mood_delegate)
        
        saved = _load_col_widths()
        header = self.table.horizontalHeader()
        for col, w in saved.items():
            if col < len(HEADERS): header.resizeSection(col, w)
        header.setStretchLastSection(True)

        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        return self.table

    def _initial_load(self):
        def _fetch_initial_data():
            return get_all_genres(), get_all_folders(), get_favorite_filepaths()

        worker = DataWorker(_fetch_initial_data)
        worker.results_ready.connect(self._on_initial_data_ready)
        self.register_worker(worker)
        worker.start()

    def _on_initial_data_ready(self, result):
        genres, folders, fav_set = result
        
        self.genre_cb.blockSignals(True)
        self.genre_cb.clear()
        self.genre_cb.addItem("Все жанры", "")
        self.genre_cb.addItems(genres)
        self.genre_cb.blockSignals(False)

        self.folder_cb.blockSignals(True)
        self.folder_cb.clear()
        self.folder_cb.addItem("Все папки", "")
        for folder_path, track_count in folders:
            name = Path(folder_path).name
            self.folder_cb.addItem(f"{name} ({track_count})", folder_path)
        self.folder_cb.blockSignals(False)
        
        self.model.set_fav_set(fav_set)

    def refresh_data(self):
        self._initial_load()
        
    def _update_status_text(self, count=None):
        if count is None: count = self.model.rowCount()
        self.status_label.setText(f"Найдено: {count} треков")

    # --- Interaction Slots ---
    def _on_tab_changed(self, index: int):
        """Load artist view data when its tab is selected."""
        if self.integrated_tab_bar.tabText(index) == "Исполнители":
            self.artist_view_widget.load_if_needed()

    # --- Filter Slots ---
    def _on_search_changed(self, text: str):
        QTimer.singleShot(200, lambda: self.model.set_search_term(text))
    def _on_genre_filter_changed(self, index: int):
        self.model.set_genre_filter(self.genre_cb.currentData() or "")
    def _on_folder_filter_changed(self, index: int):
        self.model.set_folder_filter(self.folder_cb.currentData() or "")
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
        self.folder_cb.setCurrentIndex(0)
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
        self.folder_cb.setStyleSheet(self._combo_style())
        self.table.setStyleSheet(self._table_style())
        if hasattr(self, 'integrated_tab_bar') and self.integrated_tab_bar: # Check if integrated_tab_bar exists
            self.integrated_tab_bar.setStyleSheet(self._tab_style())
        
        integrated_title_bar = self.findChild(QWidget, "integrated_title_bar")
        if integrated_title_bar:
            integrated_title_bar.setStyleSheet("background-color: #000000;") # Re-apply background, forces child styles to re-evaluate
            # The buttons within the title bar should pick up the accent color from cfg.get_accent_color() directly
        clear_btn = self.findChild(QPushButton, "clear_btn")
        if clear_btn:
            clear_btn.setStyleSheet(f"QPushButton {{ border: 1px solid rgba(60,60,60,0.5); font-size: 11px; font-weight: bold; }} QPushButton:hover {{ color: {cfg.get_accent_color()}; }}")
        self._on_fav_filter_toggled(self.fav_btn.isChecked())
    
    # --- Other UI logic ---
    def _on_double_click(self, index: QModelIndex):
        track = self.model.get_track(index.row())
        if track: self.track_selected.emit(track.filepath)

    def closeEvent(self, event):
        self._is_quitting = True
        for worker in self._active_workers:
            worker.requestInterruption()
        
        if not self._active_workers:
            self.save_and_quit(event)
        else:
            # Defer closing until last worker finishes
            event.ignore()
            self.hide() # Hide window immediately

    def save_and_quit(self, event):
        widths = {col: self.table.horizontalHeader().sectionSize(col) for col in range(COLUMN_COUNT)}
        _save_col_widths(widths)
        self.closed.emit()
        event.accept()

    def _input_style(self):
        return f"QLineEdit {{ background: transparent; border: none; border-bottom: 1px solid rgba(80,80,80,0.5); padding: 0 10px 0 4px; color: #FFF; font-size: 12px; }} QLineEdit:focus {{ border-bottom-color: {cfg.get_accent_color()}; }}"
    def _combo_style(self):
        return f"QComboBox {{ background: #1a1a1a; border: 1px solid rgba(80,80,80,0.5); padding: 0 8px; color: #FFF; font-size: 12px; }} QComboBox::drop-down {{ border: none; width: 20px; }} QComboBox QAbstractItemView::item:selected {{ background-color: {cfg.get_accent_color()}33; outline: none; }}"
    def _btn_style(self):
        return f"QPushButton {{ background: #1a1a1a; border: 1px solid rgba(80,80,80,0.5); color: #AAA; font-size: 11px; }} QPushButton:hover {{ color: {cfg.get_accent_color()};}}"
    
    def _tab_style(self):
        accent = cfg.get_accent_color()
        return f"""
            QTabBar {{
                border: none; /* Remove border from the QTabBar widget itself */
            }}
            QTabBar::tab {{
                background: transparent;
                color: #888;
                font-weight: bold;
                padding: 6px 25px;
                width: 150px; /* Set fixed width for tabs */
                border: none;
                border-bottom: none; /* Explicitly remove bottom border */
            }}
            QTabBar::tab:selected {{
                background: #000000;
                color: {accent};
                border: none;
                border-bottom: none; /* Explicitly remove bottom border */
            }}
            QTabBar::tab:hover {{
                color: #FFFFFF;
                background: transparent;
                border: none;
                border-bottom: none; /* Explicitly remove bottom border */
            }}
        """

    def _table_style(self):
        accent = cfg.get_accent_color()
        r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        sel = f"rgba({r},{g},{b},40)"
        return f"QTableView {{ background: #000; border: none; gridline-color: rgba(60,60,60,20); color: #FFF; font-size: 12px; }} QTableView::item {{ padding: 4px 8px; border-bottom: 1px solid rgba(60,60,60,20); }} QTableView::item:selected {{ background: {sel}; color: #FFF; }} QHeaderView::section {{ background: #0a0a0a; color: #AAA; padding: 6px 8px; border: none; border-bottom: 1px solid rgba(80,80,80,0.3); font-size: 11px; font-weight: bold; }} QHeaderView::section:hover {{ color: #FFF; background: #151515; }} QScrollBar:vertical {{ background: #000; width: 6px; }} QScrollBar::handle:vertical {{ background: rgba(80,80,80,0.5); min-height: 30px; }} QScrollBar:horizontal {{ background: #000; height: 6px; }}"
    
    def _show_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid(): return
        track = self.model.get_track(idx.row())
        if not track: return
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: #111; border: 1px solid #505050; padding: 4px 0; color: #FFF; }} QMenu::item:selected {{ background: {cfg.get_accent_color()}66; }}")
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
        if event.button() == Qt.LeftButton: self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos: self.move(event.globalPosition().toPoint() - self._drag_pos)

# ============================================================
# Column width persistence
# ============================================================
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
COL_WIDTHS_FILE = CACHE_DIR / "library_col_widths.json"

DEFAULT_COL_WIDTHS = {
    COL_TITLE: 400,
    COL_ARTIST: 300,
    COL_ALBUM: 230,
    COL_GENRE: 214,
    COL_FOLDER: 230,
    COL_DURATION: 110,
    COL_BITRATE: 80,
    COL_PLAY_COUNT: 50,
    COL_FAVORITE: 40,
    COL_MOOD: 40,
}

def _load_col_widths() -> dict:
    if COL_WIDTHS_FILE.exists():
        try:
            with open(COL_WIDTHS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            pass
    return dict(DEFAULT_COL_WIDTHS)


def _save_col_widths(widths: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(COL_WIDTHS_FILE, "w", encoding="utf-8") as f:
            json.dump(widths, f, indent=2)
    except Exception:
        pass

