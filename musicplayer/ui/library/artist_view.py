"""
Artist View Widget

This module contains the main widget for the "Artists" tab, which handles
loading, caching, and displaying artist cards.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout, QLabel,
)
from PySide6.QtGui import QPainter, QColor, QPen

from musicplayer.core import db
from musicplayer.ui.library.artist_worker import ArtistProcessingWorker
from musicplayer.ui.library.artist_card import ArtistCardWidget
from musicplayer import config as cfg


class Spinner(QWidget):
    """Animated spinning circle, shown during artist loading."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(14, 14)

    def start(self):
        self._angle = 0
        if not self._timer.isActive():
            self._timer.start(50)

    def stop(self):
        self._timer.stop()

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(cfg.get_accent_color()), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        r = self.rect().adjusted(2, 2, -2, -2)
        painter.drawArc(r, self._angle * 16, 270 * 16)


class LoadingBar(QWidget):
    """Bottom status bar with spinner + text during artist loading."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 6, 12, 6)

        self._spinner = Spinner(self)
        lo.addWidget(self._spinner)

        self._label = QLabel("Загрузка исполнителей...")
        self._label.setStyleSheet(
            f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px; "
            f"background: transparent;")
        lo.addWidget(self._label)
        lo.addStretch()

        self.hide()

    def start(self):
        self._spinner.start()
        self.show()

    def stop(self):
        self._spinner.stop()
        self.hide()


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

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {cfg.BG_COLOR};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {cfg.BG_COLOR};
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {cfg.DIVIDER_COLOR};
                min-height: 30px;
            }}
            QScrollBar:add-line:vertical, QScrollBar:sub-line:vertical {{
                height: 0px;
            }}
        """)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)

        self._scroll_area.setWidget(self._grid_container)
        self._layout.addWidget(self._scroll_area, 1)

        self._loading_bar = LoadingBar(self)
        self._layout.addWidget(self._loading_bar)

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

        if db.get_artists_cache_status():
            self._load_from_cache()
        else:
            self._rebuild_cache()

    def _load_from_cache(self):
        artists = db.get_cached_artists()
        for artist_data in artists:
            self._add_artist_card_to_grid(artist_data)

        self._is_loaded = True

    def _rebuild_cache(self):
        self._loading_bar.start()
        self.worker = ArtistProcessingWorker(self)
        self.worker.artist_ready.connect(self._add_artist_card_to_grid)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _add_artist_card_to_grid(self, artist_data: dict):
        card = ArtistCardWidget(
            artist_name=artist_data["name"],
            track_count=artist_data["track_count"],
            collage_path=artist_data["collage_path"]
        )
        card.clicked.connect(self.artist_play_requested)

        row, col = divmod(self._grid_layout.count(), self._col_count or 1)
        self._grid_layout.addWidget(card, row, col)

    def _on_worker_finished(self):
        self._loading_bar.stop()
        self._is_loaded = True
        self.worker = None

    def update_accent_color(self):
        acc = cfg.get_accent_color()
        self._loading_bar._spinner.update()
        for i in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(i)
            if item and item.widget():
                if isinstance(item.widget(), ArtistCardWidget):
                    item.widget().update_accent_color()
