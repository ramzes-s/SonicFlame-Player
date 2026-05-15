import urllib.request
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QScrollArea, QFrame, QGridLayout)
from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QPainter, QPixmap, QMouseEvent, QColor
from PySide6.QtSvg import QSvgRenderer
from musicplayer import config as cfg
from musicplayer.ui.svg_icons import get_music_note_svg
from .base_dialog import BaseFramelessDialog


def _music_note_pixmap(size=120, color="#666666"):
    svg_bytes = get_music_note_svg(size, color=color).encode('utf-8')
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class TrackSearchResultsDialog(BaseFramelessDialog):
    def __init__(self, track_results, parent=None, artist="", title="", duration=""):
        super().__init__(parent)
        self.track_results = track_results
        self.selected_track = None
        self.setMinimumSize(760, 710)
        self._artist = artist
        self._title = title
        self._duration = duration
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent(50)

    def _build_ui(self):
        inner = self._setup_ui()

        title_text = "Результаты поиска"
        if self._artist or self._title or self._duration:
            title_text = f"Результаты поиска для: {self._artist} - {self._title}"
            if self._duration:
                title_text += f" ♪ {self._duration}"
        title_bar = self._build_title_bar(title_text)
        inner.addWidget(title_bar)

        content = QWidget()
        content.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { background-color: #000000; width: 5px; }
            QScrollBar::handle:vertical { background-color: rgba(80,80,80,0.6); border-radius: 3px; min-height: 30px; }
        """)

        card_container = QWidget()
        card_layout = QVBoxLayout(card_container)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(8)

        for score, track_data in self.track_results:
            card = self._build_card(track_data, score, self._artist, self._title, self._duration)
            card_layout.addWidget(card)

        card_layout.addStretch()
        scroll.setWidget(card_container)
        content_layout.addWidget(scroll)
        inner.addWidget(content, stretch=1)

    def _build_card(self, track_data, score, original_artist, original_title, original_duration):
        card = QFrame()
        accent = cfg.get_accent_color()
        track_name = track_data.get("trackName", "—")
        artist_name = track_data.get("artistName", "—")
        duration_ms = track_data.get("trackTimeMillis", 0)
        api_duration = f"{duration_ms // 60000}:{duration_ms % 60000 // 1000:02d}" if duration_ms else ""

        is_artist_match = original_artist.strip().lower() == artist_name.strip().lower()
        is_title_match = original_title.strip().lower() == track_name.strip().lower()
        is_perfect_match = is_artist_match and is_title_match
        title_color_style = f"color: {accent};" if is_perfect_match else "color: #FFFFFF;"

        card.setStyleSheet(f"""
            QFrame {{ background-color: #111111; border: 1px solid rgba(80,80,80,0.5); padding: 10px; }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(12)

        COVER_SIZE = 120
        cover_label = QLabel()
        cover_label.setFixedSize(COVER_SIZE, COVER_SIZE)
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setStyleSheet("""
            QLabel { background-color: #1a1a1a; color: #666666; font-size: 11px; }
        """)

        art_url = track_data.get("artworkUrl100", "").replace("100x100", "300x300")
        if art_url:
            try:
                req = urllib.request.Request(art_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    img_data = resp.read()
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(COVER_SIZE, COVER_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    cover_label.setPixmap(scaled)
                    cover_label.setText("")
            except Exception:
                cover_label.setPixmap(_music_note_pixmap(COVER_SIZE))
        else:
            cover_label.setPixmap(_music_note_pixmap(COVER_SIZE))

        pick_btn = QPushButton("✓ Подходит")
        pick_btn.setFixedWidth(COVER_SIZE)
        pick_btn.setFixedHeight(28)
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {accent}; color: #FFFFFF; border: none; border-radius: 0; font-size: 12px; font-weight: bold; }}
        """)
        pick_btn.clicked.connect(lambda checked=False, td=track_data: self._select_track(td))

        left_col = QVBoxLayout()
        left_col.setSpacing(0)
        left_col.setAlignment(Qt.AlignTop)
        left_col.addWidget(cover_label)
        left_col.addWidget(pick_btn)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(0, 2, 0, 2)

        collection = track_data.get("collectionName", "—")
        release = track_data.get("releaseDate", "")
        year = release[:4] if release else ""
        genres = track_data.get("genres", [])
        if not genres:
            primary = track_data.get("primaryGenreName", "")
            if primary:
                genres = [primary]

        title_artist = f"{artist_name} — {track_name}"
        name_lbl = QLabel(f"<b>{title_artist}</b>")
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"{title_color_style} font-size: 13px;")
        info_layout.addWidget(name_lbl)

        if collection and collection != "—":
            album_lbl = QLabel(f"Альбом: {collection}")
            album_lbl.setStyleSheet("color: #AAAAAA; font-size: 12px;")
            info_layout.addWidget(album_lbl)

        meta_parts = []
        if year:
            meta_parts.append(year)
        if api_duration:
            meta_parts.append(api_duration)
        genre_str = ", ".join(genres) if genres else ""
        if genre_str:
            meta_parts.append(genre_str)

        if meta_parts:
            meta_lbl = QLabel("  •  ".join(meta_parts))
            meta_lbl.setStyleSheet("color: #888888; font-size: 12px;")
            meta_lbl.setWordWrap(True)
            info_layout.addWidget(meta_lbl)

        source = track_data.get("source", "")
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        if source:
            source_color = "#888888" if source == "iTunes" else "#1EC65E"
            if source == "iTunes":
                source_color = "#d563a1"
            source_lbl = QLabel(source)
            source_lbl.setStyleSheet(f"color: {source_color}; font-size: 10px; font-weight: bold;")
            bottom_row.addWidget(source_lbl)
        bottom_row.addStretch()

        score_label_color = "#FFFFFF" if (original_artist and original_title and is_perfect_match) else "#666666"
        score_label = QLabel(f"Совпадение: {score}")
        score_label.setStyleSheet(f"color: {score_label_color}; font-size: 11px;")
        bottom_row.addWidget(score_label)
        info_layout.addLayout(bottom_row)

        card_layout.addLayout(left_col)
        card_layout.addLayout(info_layout)
        return card

    def _select_track(self, track_data):
        self.selected_track = track_data
        self.accept()


class CoverTile(QWidget):
    selected = Signal(bytes)

    def __init__(self, label: str, cover_data: bytes, parent=None):
        super().__init__(parent)
        self.label = label
        self.cover_data = cover_data
        self.TILE_SIZE = 200
        self._hovered = False
        self.setFixedSize(self.TILE_SIZE, self.TILE_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self._pixmap = QPixmap()
        self._pixmap.loadFromData(cover_data)
        self._overlay_color = QColor(0, 0, 0, 180)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.cover_data)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.TILE_SIZE, self.TILE_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.TILE_SIZE - scaled.width()) // 2
            y = (self.TILE_SIZE - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(0, 0, self.TILE_SIZE, self.TILE_SIZE, QColor("#1a1a1a"))
            pix = _music_note_pixmap(80, "#666666")
            nx = (self.TILE_SIZE - pix.width()) // 2
            ny = (self.TILE_SIZE - pix.height()) // 2
            painter.drawPixmap(nx, ny, pix)

        if self._hovered:
            accent = cfg.get_accent_color()
            painter.setPen(QColor(accent))
            font = painter.font()
            font.setPointSize(48)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "✓")
        else:
            painter.fillRect(0, 0, self.TILE_SIZE, self.TILE_SIZE, self._overlay_color)
            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            text_rect = self.rect().adjusted(8, 8, -8, -8)
            painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignCenter, self.label)


class CoverSearchResultsDialog(BaseFramelessDialog):
    def __init__(self, covers, parent=None, artist="", title=""):
        super().__init__(parent)
        self.covers = covers
        self.selected_cover = None
        self.setFixedSize(700, 500)
        self._artist = artist
        self._title = title
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent(50)

    def _build_ui(self):
        inner = self._setup_ui()

        title_text = "Выбор обложки трека"
        if self._artist or self._title:
            title_text = f"Выбор обложки для: {self._artist} - {self._title}"
        title_bar = self._build_title_bar(title_text)
        inner.addWidget(title_bar)

        content = QWidget()
        content.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(0)

        card_container = QWidget()
        card_container.setStyleSheet("background-color: #000000;")
        card_layout = QGridLayout(card_container)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignCenter)

        cols = 3
        for i, (label, cover_data) in enumerate(self.covers):
            row = i // cols
            col = i % cols
            tile = CoverTile(label, cover_data)
            tile.selected.connect(self._select_cover)
            card_layout.addWidget(tile, row, col)

        card_layout.setRowStretch((len(self.covers) + cols - 1) // cols, 1)
        content_layout.addWidget(card_container)
        inner.addWidget(content, stretch=1)

    def _select_cover(self, cover_data: bytes):
        self.selected_cover = cover_data
        self.accept()
