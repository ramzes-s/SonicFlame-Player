"""
Library Model and Delegate

Virtual table model for efficient rendering of large track collections,
plus custom delegate for mood star display.
"""

import math
from typing import Dict, Optional, Tuple, List
from pathlib import Path

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtGui import QPainter, QPainterPath, QFont, QColor

from musicplayer import config as cfg
from musicplayer.core.db import (
    get_filtered_library_track_count,
    get_library_tracks_page,
)
from musicplayer.utils.helpers import format_duration, get_color_from_features
from musicplayer.ui.library.types import Track, HEADERS, COLUMN_COUNT
from musicplayer.ui.library.worker import DataWorker


class MoodStarDelegate(QStyledItemDelegate):
    """Custom delegate for rendering mood star in table cells."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        super().paint(painter, option, QModelIndex())

        features = index.data(Qt.UserRole)
        if not features or not isinstance(features, tuple) or len(features) != 3:
            return

        tempo, energy, mood = features
        if tempo <= 0.0:
            return

        star_color = get_color_from_features(tempo, energy, mood)
        star_size = 16

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


class LibraryModel(QAbstractTableModel):
    """A virtual table model that fetches data from the DB on demand."""

    PAGE_SIZE = 250
    total_count_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: Dict[int, Track] = {}
        self._total_rows = 0

        self._search_term = ""
        self._genre_filter = ""
        self._folder_filter = ""
        self._fav_only = False
        self._sort_col = "Название"
        self._sort_ord = "ASC"

        self.worker: Optional[DataWorker] = None

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
        if column >= len(HEADERS):
            return
        self._sort_col = HEADERS[column]
        self._sort_ord = "ASC" if order == Qt.AscendingOrder else "DESC"

        self._cache.clear()
        if self._total_rows > 0:
            self.dataChanged.emit(self.index(0, 0), self.index(self._total_rows - 1, self.columnCount() - 1))
            self.fetchMore(QModelIndex())

    def get_track(self, row: int) -> Optional[Track]:
        return self._cache.get(row)

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
            if role == Qt.DisplayRole:
                return "..."
            return None

        if role == Qt.DisplayRole:
            if col == 0:
                return track.title
            if col == 1:
                return track.artist
            if col == 2:
                return track.album
            if col == 3:
                return track.genre or ""
            if col == 4:
                return track.folder
            if col == 5:
                return format_duration(track.duration)
            if col == 6:
                return f"{track.bitrate} kbps" if track.bitrate else ""
            if col == 7:
                return str(track.play_count) if track.play_count else "0"
            if col == 8:
                return "♥" if track.is_favorite else ""
            return None

        if role == Qt.TextAlignmentRole and col in (5, 6, 7, 8, 9):
            return Qt.AlignCenter

        if role == Qt.FontRole and col in (3, 4, 6, 7):
            return QFont("Segoe UI", 9)

        if role == Qt.ForegroundRole and col == 8 and track.is_favorite:
            return QColor(cfg.get_accent_color())

        if role == Qt.UserRole and col == 9:
            return (track.tempo, track.energy, track.mood)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[section]
        return None

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
        if self.worker and self.worker.isRunning():
            return

        self.worker = DataWorker(self._get_tracks_page_from_db, offset, limit)
        self.worker.results_ready.connect(self._on_page_fetched)
        self.parent().register_worker(self.worker)
        self.worker.start()

    def _on_page_fetched(self, result: Tuple[int, List[Track]]):
        offset, tracks = result
        if not tracks:
            return

        for i, track in enumerate(tracks):
            self._cache[offset + i] = track

        top_left = self.index(offset, 0)
        bottom_right = self.index(offset + len(tracks) - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)

    def _get_tracks_page_from_db(self, offset, limit):
        tracks_info = get_library_tracks_page(
            offset, limit, sort_col=self._sort_col, sort_ord=self._sort_ord,
            search_term=self._search_term, genre_filter=self._genre_filter,
            folder_filter=self._folder_filter, fav_only=self._fav_only
        )
        tracks = []
        for ti in tracks_info:
            try:
                folder = str(Path(ti.filepath).parent.name)
            except Exception:
                folder = ""
            tracks.append(Track(
                filepath=ti.filepath, title=ti.title or "", artist=ti.artist or "Unknown Artist",
                album=ti.album or "Unknown Album", genre=ti.genre or "",
                duration=ti.duration or 0.0, bitrate=getattr(ti, 'bitrate', 0),
                folder=folder, play_count=getattr(ti, 'play_count', 0),
                tempo=getattr(ti, 'tempo', 0.0),
                energy=getattr(ti, 'energy', 0.0),
                mood=getattr(ti, 'mood', 0.0),
                is_favorite=getattr(ti, 'is_favorite', False),
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