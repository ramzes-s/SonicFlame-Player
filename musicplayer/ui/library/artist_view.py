"""
Artist View Widget

This module contains the main widget for the "Artists" tab, which handles
loading, caching, and displaying artist cards.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QScrollArea, QGridLayout, QLabel,
    QSizePolicy
)
from PySide6.QtGui import QColor

from musicplayer.core import db
from musicplayer.ui.library.artist_worker import ArtistProcessingWorker
from musicplayer.ui.library.artist_card import ArtistCardWidget
from musicplayer.config import ACCENT_COLOR


class LoadingSpinnerWidget(QWidget):
    """A simple loading text widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Загрузка исполнителей...", self)
        font = self.label.font()
        font.setPointSize(14)
        self.label.setFont(font)
        layout.addWidget(self.label)


class ArtistViewWidget(QWidget):
    """
    The main widget for the artists view. It manages loading data,
    displaying a grid of artists, and handling cache logic.
    """
    artist_play_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loaded = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget(self)
        self._layout.addWidget(self._stack)

        self._spinner = LoadingSpinnerWidget(self)
        self._stack.addWidget(self._spinner)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #000000;
                border: none;
            }
            QScrollBar:vertical {
                background: #000;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(80,80,80,0.5);
                min-height: 30px;
            }
            QScrollBar:add-line:vertical, QScrollBar:sub-line:vertical {
                height: 0px;
            }
        """)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background-color: #000000;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)

        self._scroll_area.setWidget(self._grid_container)
        self._stack.addWidget(self._scroll_area)

        self._col_count = 0
        self.resizeEvent(None)

    def resizeEvent(self, event):
        new_col_count = max(1, self.width() // (200 + self._grid_layout.spacing()))

        if new_col_count != self._col_count:
            self._col_count = new_col_count

            items = []
            while self._grid_layout.count():
                item = self._grid_layout.takeAt(0)
                if item.widget():
                    items.append(item.widget())

            for i, widget in enumerate(items):
                row, col = divmod(i, self._col_count)
                self._grid_layout.addWidget(widget, row, col)

        if event:
            super().resizeEvent(event)

    def load_if_needed(self):
        if self._is_loaded:
            return

        self._stack.setCurrentWidget(self._spinner)

        if db.get_artists_cache_status():
            self._load_from_cache()
        else:
            self._rebuild_cache()

    def _load_from_cache(self):
        artists = db.get_cached_artists()
        for artist_data in artists:
            self._add_artist_card_to_grid(artist_data)

        self._is_loaded = True
        self._stack.setCurrentWidget(self._scroll_area)

    def _rebuild_cache(self):
        self.worker = ArtistProcessingWorker(self)
        self.worker.artist_ready.connect(self._add_artist_card_to_grid)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _add_artist_card_to_grid(self, artist_data: dict):
        if self._stack.currentWidget() == self._spinner:
            self._stack.setCurrentWidget(self._scroll_area)

        card = ArtistCardWidget(
            artist_name=artist_data["name"],
            track_count=artist_data["track_count"],
            collage_path=artist_data["collage_path"]
        )
        card.clicked.connect(self.artist_play_requested)

        row, col = divmod(self._grid_layout.count(), self._col_count or 1)
        self._grid_layout.addWidget(card, row, col)

    def _on_worker_finished(self):
        self._is_loaded = True
        self.worker = None

    def update_accent_color(self):
        for i in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(i)
            if item and item.widget():
                if isinstance(item.widget(), ArtistCardWidget):
                    item.widget().update_accent_color()