"""
Playlist View Module

Custom list view for displaying and managing tracks with
smart auto-scroll to keep current track centered.
"""

import json
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QVBoxLayout,
                                QWidget, QLabel, QStyledItemDelegate, QStyleOptionViewItem, QStyle,
                                QAbstractItemView, QMenu)
from PySide6.QtCore import Qt, Signal, QRect, QRectF, QSize, QEvent, QByteArray, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPainter, QFontMetrics, QPixmap, QCursor
from PySide6.QtSvg import QSvgRenderer
from musicplayer.core.db import TrackInfo
from musicplayer.core.db import (
    get_library_tracks_page,
    is_favorite as db_is_favorite,
    toggle_favorite as db_toggle_favorite,
    get_favorite_filepaths as db_get_favorite_filepaths,
)
from musicplayer.utils.helpers import format_duration
from musicplayer.ui.svg_icons import get_crown_svg, get_heart_svg


from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR, DIVIDER_COLOR, DIVIDER_ITEM_RGB, DIVIDER_ITEM_ALPHA

HEART_SIZE = 16
HEART_SPACING = 6  # px between heart and adjacent badges/icons


def _parse_paren_segments(text: str) -> list[tuple[str, bool]]:
    """Split text into segments: (text, is_parenthesized)."""
    segments: list[tuple[str, bool]] = []
    buf: list[str] = []
    in_paren = False
    for ch in text:
        if ch == '(':
            if buf:
                segments.append((''.join(buf), in_paren))
                buf = []
            in_paren = True
            buf.append(ch)
        elif ch == ')':
            buf.append(ch)
            if buf:
                segments.append((''.join(buf), in_paren))
                buf = []
            in_paren = False
        else:
            buf.append(ch)
    if buf:
        segments.append((''.join(buf), in_paren))
    return segments


class PlaylistItem(QListWidgetItem):
    """Custom list item for track display."""

    def __init__(self, track: TrackInfo, view_index: int):
        super().__init__()
        # Store the TrackInfo filepath for direct track lookup
        self.setData(Qt.UserRole, track.filepath)
        # Store the current view index (changes when filtering)
        self.setData(Qt.UserRole + 1, view_index)


class PlaylistDelegate(QStyledItemDelegate):
    """Custom delegate for painting playlist items with rich formatting."""

    def __init__(self, parent=None, tracks_ref=None, favorites=None):
        super().__init__(parent)
        self.tracks_ref = tracks_ref  # Currently displayed tracks list
        self._favorites = favorites  # FavoritesManager instance
        self._playing_filepath = None  # Currently playing track filepath
        self._title_top = False  # False: artist above, True: title above

    def set_display_mode(self, mode: str):
        """Set whether title is on top. 'artist_top' or 'title_top'."""
        self._title_top = (mode == "title_top")

    def set_favorites(self, favorites):
        """Set favorites manager reference."""
        self._favorites = favorites

    def set_playing_track(self, filepath: str):
        """Set the currently playing track filepath for highlight."""
        self._playing_filepath = filepath

    def _is_playing(self, track) -> bool:
        """Check if a track is currently playing."""
        if track is None or self._playing_filepath is None:
            return False
        return track.filepath == self._playing_filepath

    def _is_favorite(self, track) -> bool:
        """Check if a track is in favorites."""
        if track is None:
            return False
        return track.is_favorite

    def _render_heart_pixmap(self, is_fav: bool) -> QPixmap:
        """Render heart SVG with appropriate color and opacity."""
        if is_fav:
            svg_data = get_heart_svg(HEART_SIZE, cfg.get_accent_color())
            opacity = 1.0
        else:
            svg_data = get_heart_svg(HEART_SIZE, "#FFFFFF")
            opacity = 80 / 255.0  # ~31% opaque — subtle outline

        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        pixmap = QPixmap(HEART_SIZE, HEART_SIZE)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(opacity)
        renderer.render(painter, QRect(0, 0, HEART_SIZE, HEART_SIZE))
        painter.end()

        return pixmap

    def _get_heart_rect(self, view_index: int, option_rect: QRect) -> QRect:
        """Calculate the heart icon rectangle position."""
        track = None
        if self.tracks_ref is not None and 0 <= view_index < len(self.tracks_ref):
            track = self.tracks_ref[view_index]

        if track is None:
            return QRect()

        # Heart is rightmost: right_edge - HEART_SIZE - 2px_gap
        x = option_rect.right() - HEART_SIZE - 12  # 10px margin + 2px gap
        y = option_rect.top() + (option_rect.height() - HEART_SIZE) // 2
        return QRect(x, y, HEART_SIZE, HEART_SIZE)

    def _get_heart_rect_for_index(self, view_index: int, option_rect: QRect) -> QRect:
        """Calculate the heart icon rectangle position for a given view index."""
        return self._get_heart_rect(view_index, option_rect)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint playlist item with heart, artist (bold), title (normal), and badges."""
        painter.save()

        # Get track filepath from the item and find in current view
        filepath = index.data(Qt.UserRole)
        view_index = index.data(Qt.UserRole + 1)

        track = None
        if self.tracks_ref is not None and filepath:
            for t in self.tracks_ref:
                if t.filepath == filepath:
                    track = t
                    break

        is_playing = self._is_playing(track)
        is_hovered = option.state & QStyle.State_MouseOver

        # Background
        if is_playing:
            accent = QColor(cfg.get_accent_color())
            accent.setAlpha(40)
            painter.fillRect(option.rect, accent)
        elif is_hovered:
            painter.fillRect(option.rect, QColor(80, 80, 80, 80))

        # Divider line at bottom
        painter.setPen(QColor(*DIVIDER_ITEM_RGB, DIVIDER_ITEM_ALPHA))
        painter.drawLine(option.rect.left(), option.rect.bottom() - 1,
                        option.rect.right(), option.rect.bottom() - 1)

        # Text layout
        left_margin = 15
        right_margin = 200  # Space for badges + heart
        text_rect = option.rect.adjusted(left_margin, 0, -right_margin, 0)

        if track:
            if self._title_top:
                top_text = track.title
                top_is_title = True
                bottom_text = track.artist
                bottom_is_title = False
            else:
                top_text = track.artist
                top_is_title = False
                bottom_text = track.title
                bottom_is_title = True

            # Top row — title (bold, accent or gray) or artist (normal, white ~70%)
            if top_is_title:
                normal_font = QFont("Segoe UI", 11)
                normal_font.setBold(True)
                paren_font = QFont("Segoe UI", 11)
                paren_font.setBold(False)
                normal_color = QColor(cfg.get_accent_color()) if is_playing else QColor(200, 200, 200)
                paren_color = QColor(cfg.get_accent_color()) if is_playing else QColor(cfg.SECONDARY_TEXT_COLOR)
                tx = text_rect.left()
                ty = text_rect.top() + 18
                for seg_text, is_paren in _parse_paren_segments(top_text):
                    font = paren_font if is_paren else normal_font
                    painter.setFont(font)
                    painter.setPen(paren_color if is_paren else normal_color)
                    fm = QFontMetrics(font)
                    seg_w = fm.horizontalAdvance(seg_text)
                    if tx + seg_w <= text_rect.right():
                        painter.drawText(tx, ty, seg_text)
                        tx += seg_w + 4
                    else:
                        available = text_rect.right() - tx - fm.horizontalAdvance('…')
                        if available > 0:
                            painter.drawText(tx, ty, fm.elidedText(seg_text, Qt.ElideRight, available))
                        break
            else:
                artist_font = QFont("Segoe UI", 10)
                painter.setFont(artist_font)
                painter.setPen(Qt.white if is_playing else QColor(255, 255, 255, 180))
                fm_artist = QFontMetrics(artist_font)
                painter.drawText(text_rect.left(), text_rect.top() + 18,
                                 fm_artist.elidedText(top_text, Qt.ElideRight, text_rect.width()))

            # Bottom row
            if bottom_is_title:
                normal_font = QFont("Segoe UI", 11)
                normal_font.setBold(True)
                paren_font = QFont("Segoe UI", 11)
                paren_font.setBold(False)
                normal_color = QColor(cfg.get_accent_color()) if is_playing else QColor(200, 200, 200)
                paren_color = QColor(cfg.get_accent_color()) if is_playing else QColor(cfg.SECONDARY_TEXT_COLOR)
                tx = text_rect.left()
                ty = text_rect.top() + 36
                for seg_text, is_paren in _parse_paren_segments(bottom_text):
                    font = paren_font if is_paren else normal_font
                    painter.setFont(font)
                    painter.setPen(paren_color if is_paren else normal_color)
                    fm = QFontMetrics(font)
                    seg_w = fm.horizontalAdvance(seg_text)
                    if tx + seg_w <= text_rect.right():
                        painter.drawText(tx, ty, seg_text)
                        tx += seg_w + 4
                    else:
                        available = text_rect.right() - tx - fm.horizontalAdvance('…')
                        if available > 0:
                            painter.drawText(tx, ty, fm.elidedText(seg_text, Qt.ElideRight, available))
                        break
            else:
                artist_font = QFont("Segoe UI", 10)
                painter.setFont(artist_font)
                painter.setPen(Qt.white if is_playing else QColor(255, 255, 255, 180))
                fm_artist = QFontMetrics(artist_font)
                painter.drawText(text_rect.left(), text_rect.top() + 36,
                                 fm_artist.elidedText(bottom_text, Qt.ElideRight, text_rect.width()))

            # --- BADGES (right side) ---
            # Order from RIGHT to LEFT:
            # Heart | Duration | Genre1 | Genre2 | ... | Crown
            badge_font = QFont("Segoe UI", 9)
            painter.setFont(badge_font)
            badge_y = option.rect.top() + (option.rect.height() - 18) // 2
            x = option.rect.right() - 10  # Start from right edge

            # 1) Heart icon (RIGHTMOST — after duration badge)
            is_fav = self._is_favorite(track)
            heart_pixmap = self._render_heart_pixmap(is_fav)

            # We'll draw heart after duration, so first calculate positions
            # Duration badge width
            duration_text = format_duration(track.duration)
            fm_dur = QFontMetrics(badge_font)
            dur_w = fm_dur.horizontalAdvance(duration_text) + 10

            # Heart position: rightmost, then duration to its left
            heart_x = x - HEART_SIZE - 2  # 2px gap
            heart_y = option.rect.top() + (option.rect.height() - HEART_SIZE) // 2

            if not heart_pixmap.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(heart_x, heart_y, heart_pixmap)

            x = heart_x - HEART_SPACING  # Move left for duration badge

            # 2) Duration badge
            x -= dur_w
            rect_d = QRectF(x, badge_y, dur_w, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*cfg.BADGE_BG_RGB, cfg.BADGE_BG_ALPHA))
            painter.drawRoundedRect(rect_d, 4, 4)
            painter.setPen(QColor(*cfg.BADGE_TEXT_COLOR))
            painter.drawText(rect_d, Qt.AlignCenter, duration_text)

            # 2) Genre badges (each genre in its own badge)
            if track.genre:
                genres = [g.strip() for g in track.genre.split(';') if g.strip()]
                if not genres:
                    genres = [track.genre.strip()] if track.genre.strip() else []

                # Limit to 3 genres max, show +N for overflow
                MAX_GENRES = 3
                if len(genres) > MAX_GENRES:
                    extra = len(genres) - MAX_GENRES + 1
                    genres = genres[:MAX_GENRES - 1] + [f'+{extra}']

                for genre_text in reversed(genres):
                    if len(genre_text) > 18:
                        genre_text = genre_text[:17] + '…'

                    fm_g = QFontMetrics(badge_font)
                    genre_w = fm_g.horizontalAdvance(genre_text) + 10

                    x -= genre_w + 4
                    rect_g = QRectF(x, badge_y, genre_w, 18)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(*cfg.BADGE_BG_RGB, cfg.BADGE_BG_ALPHA))
                    painter.drawRoundedRect(rect_g, 4, 4)
                    painter.setPen(QColor(*cfg.BADGE_TEXT_COLOR))
                    painter.setFont(badge_font)
                    painter.drawText(rect_g, Qt.AlignCenter, genre_text)

            # 3) Crown icon (if lossless)
            if track.is_lossless:
                crown_w = 18
                x -= crown_w + HEART_SPACING
                svg_data = get_crown_svg(14).encode('utf-8')
                crown_pixmap = QPixmap()
                crown_pixmap.loadFromData(svg_data)
                if not crown_pixmap.isNull():
                    crown_pixmap = crown_pixmap.scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    crown_y = option.rect.top() + (option.rect.height() - 14) // 2
                    painter.drawPixmap(x + 2, crown_y, crown_pixmap)
        painter.restore()

    def sizeHint(self, option, index):
        """Set item height."""
        return QSize(0, 52)


class FavoritesManager:
    """Manages favorite tracks using SQLite database."""

    def toggle_favorite(self, filepath: str) -> bool:
        """Toggle favorite status. Returns new state (True = favorite)."""
        return db_toggle_favorite(filepath)

    def is_favorite(self, filepath: str) -> bool:
        """Check if a track is in favorites."""
        return db_is_favorite(filepath)

    def get_favorites(self) -> set:
        """Get all favorite filepaths."""
        return db_get_favorite_filepaths()


class PlaylistListWidget(QListWidget):
    """Custom QListWidget with zone-based click handling."""

    # Zones (matching _right_margin = 180 in delegate):
    # | text area              | heart | badges...         |
    #  ^--- left part         ^--- left edge of 180px zone

    track_selected = Signal(int)  # view_index
    heart_clicked = Signal(int)   # view_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delegate = None
        self._suppress_selection = False  # Block selection change

    def set_playlist_delegate(self, delegate: PlaylistDelegate):
        self._delegate = delegate

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                view_index = item.data(Qt.UserRole + 1)
                rect = self.visualItemRect(item)

                # Heart zone: rightmost area (matches _get_heart_rect)
                heart_x = rect.right() - HEART_SIZE - 12
                heart_end = rect.right() - 10
                heart_rect = QRect(heart_x, rect.top(), heart_end - heart_x, rect.height())

                click_pos = event.position().toPoint()

                if heart_rect.contains(click_pos):
                    # Heart zone — suppress selection, handle in release
                    self._suppress_selection = True
                    event.accept()
                    return

        self._suppress_selection = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._suppress_selection:
            self._suppress_selection = False
            if event.button() == Qt.LeftButton:
                item = self.itemAt(event.position().toPoint())
                if item:
                    view_index = item.data(Qt.UserRole + 1)
                    rect = self.visualItemRect(item)

                    heart_x = rect.right() - HEART_SIZE - 12
                    heart_end = rect.right() - 10
                    heart_rect = QRect(heart_x, rect.top(), heart_end - heart_x, rect.height())
                    click_pos = event.position().toPoint()

                    if heart_rect.contains(click_pos):
                        self.heart_clicked.emit(view_index)
                        event.accept()
                        return
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                view_index = item.data(Qt.UserRole + 1)
                rect = self.visualItemRect(item)

                heart_x = rect.right() - HEART_SIZE - 12
                heart_end = rect.right() - 10
                heart_rect = QRect(heart_x, rect.top(), heart_end - heart_x, rect.height())
                click_pos = event.position().toPoint()

                if heart_rect.contains(click_pos):
                    # Heart zone
                    self.heart_clicked.emit(view_index)
                    event.accept()
                    return
                else:
                    # Text zone — play track
                    self.track_selected.emit(view_index)
                    event.accept()
                    return

        super().mouseReleaseEvent(event)


class PlaylistWidget(QWidget):
    """
    Playlist display with smart auto-scroll.

    Features:
    - Custom-styled list of tracks with rich formatting
    - Auto-scroll to center current track
    - Click to select and play track
    - Heart icon to toggle favorite per track
    """

    track_selected = Signal(int)  # Emitted when user clicks a track (view index)
    favorite_clicked = Signal(int)  # Emitted when user clicks heart icon (view index)
    badge_clicked = Signal(int)  # Emitted when user clicks badge area (view index)
    playlist_loaded = Signal()  # Emitted after tracks are loaded
    context_similar_tracks = Signal(object)  # Emitted from context menu: find similar for TrackInfo
    context_artist_tracks = Signal(str)  # Emitted from context menu: all tracks by artist name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {cfg.BG_COLOR};
            }}
        """)

        # Favorites manager
        self.favorites = FavoritesManager()
        self._context_actions = []  # List of (text, callback) for plugin context menu
        self._context_submenus = []  # List of (label, [(text, callback)]) for plugin submenus
        self._context_refresh_cb = None  # Callable(view_index, track) to rebuild submenus

        # Track data — share same reference so add_track works during scanning
        self._full_tracks = []    # All tracks from folder
        self._view_tracks = self._full_tracks  # Same reference when showing full playlist

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Track list
        self.list_widget = PlaylistListWidget()
        self.list_widget.setStyleSheet(self._get_list_style())
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Connect custom signals
        self.list_widget.track_selected.connect(self._on_track_selected)
        self.list_widget.heart_clicked.connect(self._on_heart_clicked)

        # Set custom delegate — reference _view_tracks from the start
        self.delegate = PlaylistDelegate(self.list_widget, self._view_tracks, self.favorites)
        self.list_widget.setItemDelegate(self.delegate)
        self.list_widget.set_playlist_delegate(self.delegate)

        layout.addWidget(self.list_widget)

        self._current_index = -1

    def _get_list_style(self) -> str:
        """Generate QSS for the playlist."""
        return f"""
            QListWidget {{
                background-color: {cfg.BG_COLOR};
                border: none;
                outline: none;
                padding: 0;
            }}
            QListWidget::item {{
                background-color: transparent;
                padding: 0;
                margin: 0;
            }}
            QScrollBar:vertical {{
                background-color: {cfg.BG_COLOR};
                width: 5px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cfg.SCROLLBAR_HANDLE_COLOR};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cfg.SCROLLBAR_HANDLE_HOVER_COLOR};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    def _on_track_selected(self, view_index: int):
        """Handle track selection from custom signal."""
        self.track_selected.emit(view_index)

    def _on_heart_clicked(self, view_index: int):
        """Handle heart icon click — toggle favorite."""
        self.favorite_clicked.emit(view_index)

    def add_context_action(self, text: str, callback):
        """Add an action to the right-click context menu."""
        self._context_actions.append((text, callback))

    def add_context_submenu(self, label: str, items: list):
        """Add a submenu to the right-click context menu.

        Args:
            label: submenu label text
            items: list of (item_text, callback) tuples
        """
        self._context_submenus.append((label, items))

    def set_context_refresh(self, callback):
        """Register a callback invoked before the context menu is shown.
        callback(view_index, track) should rebuild _context_submenus and _context_actions.
        """
        self._context_refresh_cb = callback

    def remove_context_actions(self, actions: list):
        """Remove specific context actions (used by PluginManager on disable)."""
        for item in actions:
            if item in self._context_actions:
                self._context_actions.remove(item)

    def remove_context_submenus(self, submenus: list):
        """Remove specific context submenus (used by PluginManager on disable)."""
        for item in submenus:
            if item in self._context_submenus:
                self._context_submenus.remove(item)

    def contextMenuEvent(self, event):
        """Show context menu with plugin actions on right-click."""
        list_pos = self.list_widget.mapFromGlobal(event.globalPos())
        item = self.list_widget.itemAt(list_pos)
        view_index = None
        track = None
        if item:
            view_index = item.data(Qt.UserRole + 1)
            if view_index is not None:
                if hasattr(self, 'get_track_by_view_index'):
                    track = self.get_track_by_view_index(view_index)

        # Refresh dynamic context menu items
        if self._context_refresh_cb is not None:
            self._context_refresh_cb(view_index, track)

        has_plugin_actions = bool(self._context_actions or self._context_submenus)
        if not has_plugin_actions and track is None:
            return

        menu = QMenu(self)
        accent = cfg.get_accent_color()
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {cfg.BG_COLOR}; color: {cfg.TEXT_COLOR};
                border: 1px solid {cfg.DIVIDER_COLOR}; padding: 4px 0; font-size: 12px; }}
            QMenu::item {{ padding: 8px 24px; }}
            QMenu::item:selected {{ background-color: {accent}; color: {cfg.CTR_TEXT_COLOR}; }}
            QMenu::separator {{ height: 1px; background: {cfg.DIVIDER_COLOR};
                margin: 4px 10px; }}
        """)

        # Permanent track-specific actions
        if track is not None:
            artist_name = (track.artist or "").split(";")[0].split(",")[0].strip()
            similar_action = menu.addAction("Найти похожие треки")
            similar_action.triggered.connect(
                lambda checked=False, t=track: self.context_similar_tracks.emit(t))

            if artist_name and artist_name != "Unknown Artist":
                artist_action = menu.addAction("Все песни исполнителя")
                artist_action.triggered.connect(
                    lambda checked=False, a=artist_name: self.context_artist_tracks.emit(a))

            edit_action = menu.addAction("Редактировать теги")
            edit_action.triggered.connect(
                lambda checked=False, vi=view_index: self.badge_clicked.emit(vi))

            if self._context_submenus:
                menu.addSeparator()

        # Plugin submenus — require a track
        if track is not None:
            for label, items in self._context_submenus:
                sub = menu.addMenu(label)
                sub.setStyleSheet(menu.styleSheet())
                for item in items:
                    if item is None:
                        sub.addSeparator()
                    else:
                        text, cb = item
                        action = sub.addAction(text)
                        action.setData(view_index)
                        action.triggered.connect(
                            lambda checked=False, c=cb, vi=view_index: c(vi))

        # Simple actions (always shown)
        if self._context_actions:
            if self._context_submenus and track is not None:
                menu.addSeparator()
            for text, cb in self._context_actions:
                action = menu.addAction(text)
                action.setData(view_index)
                action.triggered.connect(lambda checked=False, c=cb: c())

        if menu.actions():
            menu.exec(event.globalPos())

    def load_tracks(self, tracks: list):
        """Load tracks into the playlist (full folder scan)."""
        self._full_tracks = list(tracks)
        self._view_tracks = self._full_tracks  # Same reference when showing full
        self._display_tracks()
        self.playlist_loaded.emit()

    def update_track_data(self, old_filepath: str, new_track: TrackInfo):
        """
        Update a track's metadata in both _full_tracks and _view_tracks,
        then redraw the view. Preserves current playing highlight.
        """
        playing_filepath = self.delegate._playing_filepath
        saved_current_index = self._current_index

        # Update in _full_tracks
        for i, t in enumerate(self._full_tracks):
            if t.filepath == old_filepath:
                self._full_tracks[i] = new_track
                break

        # If _view_tracks is a separate list (favorites mode), update it too
        if self._view_tracks is not self._full_tracks:
            for i, t in enumerate(self._view_tracks):
                if t.filepath == old_filepath:
                    self._view_tracks[i] = new_track
                    break

        # Redraw
        self._display_tracks()

        # Restore current index
        self._current_index = saved_current_index

        # Restore playing highlight
        if playing_filepath in (old_filepath, new_track.filepath):
            target_fp = new_track.filepath
            for i, t in enumerate(self._view_tracks):
                if t.filepath == target_fp:
                    self._current_index = i
                    self.delegate.set_playing_track(target_fp)
                    self.list_widget.viewport().update()
                    break

    def add_track(self, track: TrackInfo, index: int = None):
        """Add a single track to the full playlist."""
        self._full_tracks.append(track)

        # If currently showing full playlist, add to view too
        if self._view_tracks is self._full_tracks:
            view_index = len(self._view_tracks) - 1
            self._add_track_to_view(track, view_index)
            # Keep delegate reference in sync
            self.delegate.tracks_ref = self._view_tracks

    def _display_tracks(self):
        """Clear and redraw the current view, preserving scroll position."""
        scroll_bar = self.list_widget.verticalScrollBar()
        scroll_pos = scroll_bar.value() if scroll_bar else 0
        self.list_widget.clear()
        for i, track in enumerate(self._view_tracks):
            self._add_track_to_view(track, i)
        self._current_index = -1
        self.delegate.tracks_ref = self._view_tracks
        if scroll_bar:
            scroll_bar.setValue(scroll_pos)

    def _add_track_to_view(self, track: TrackInfo, view_index: int):
        """Add a track to the QListWidget."""
        item = PlaylistItem(track, view_index)
        self.list_widget.addItem(item)

    def set_current_track_by_filepath(self, filepath: str):
        """
        Set currently playing track by filepath (works with filtered views).
        Finds the track in the current view and highlights it.
        """
        for i, track in enumerate(self._view_tracks):
            if track.filepath == filepath:
                self.set_current_track(i)
                return

    def scroll_to_current_track(self):
        """Scroll playlist to the currently playing track."""
        fp = self.delegate._playing_filepath
        if fp:
            self.set_current_track_by_filepath(fp)

    def set_current_track(self, view_index: int):
        """
        Update currently playing track and apply smart, smooth auto-scroll.
        Highlight is based on _playing_filepath in the delegate, not Qt selection.
        """
        if view_index < 0 or view_index >= self.list_widget.count():
            return

        item = self.list_widget.item(view_index)
        if not item:
            return

        self._current_index = view_index

        # --- Smooth Scroll (Reliable Method) ---
        # 1. Get current scrollbar value
        scrollbar = self.list_widget.verticalScrollBar()
        old_value = scrollbar.value()

        # 2. Use Qt's logic to instantly jump to the target position
        self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)

        # 3. Get the new value calculated by Qt
        new_value = scrollbar.value()

        # 4. Instantly reset to the old value (user won't see this)
        scrollbar.setValue(old_value)

        # 5. Animate from the old value to the new, correct value
        self.scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self.scroll_animation.setDuration(200)
        self.scroll_animation.setStartValue(old_value)
        self.scroll_animation.setEndValue(new_value)
        self.scroll_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.scroll_animation.start()

        # Trigger redraw to update highlight
        self.list_widget.viewport().update()

    def get_track_by_view_index(self, view_index: int):
        """Get TrackInfo by current view index."""
        if 0 <= view_index < len(self._view_tracks):
            return self._view_tracks[view_index]
        return None

    def get_current_index(self) -> int:
        """Get currently selected track index in current view."""
        return self._current_index

    def clear(self):
        """Clear the playlist."""
        self.list_widget.clear()
        self._full_tracks.clear()
        self._view_tracks.clear()
        self._current_index = -1

    def show_favorites_only(self):
        """Show ALL favorite tracks from all folders."""
        fav_tracks = get_library_tracks_page(offset=0, limit=99999, fav_only=True, sort_col='artist', sort_ord='ASC')
        self._view_tracks = fav_tracks
        self._display_tracks()
        self.playlist_loaded.emit()

    def show_full_playlist(self):
        """Show the full playlist from current folder."""
        self._view_tracks = self._full_tracks
        self._display_tracks()
        self.playlist_loaded.emit()

    def get_view_tracks(self) -> list:
        """Get the currently displayed tracks (for next/prev logic)."""
        return self._view_tracks

    def set_playing_track(self, filepath: str):
        """Set the currently playing track filepath for highlight and redraw."""
        self.delegate.set_playing_track(filepath)
        self.list_widget.viewport().update()

    def apply_accent_color(self, color: str):
        """Update accent color — triggers repaint of all items."""
        self.list_widget.viewport().update()

    def resort_current_view(self, mode: str):
        """Resort the currently displayed view according to mode (artist/title/newest)."""
        if mode not in ("artist", "title", "newest"):
            mode = "artist"
        if not self._view_tracks:
            return
        # Current playing track filepath to preserve highlight after resort
        playing_fp = self.delegate._playing_filepath if self.delegate else None

        def sort_key(t: TrackInfo):
            if mode == "artist":
                return ((t.artist or ""), (t.album or ""), (t.title or ""))
            if mode == "title":
                return ((t.title or ""), (t.artist or ""), (t.album or ""))
            # newest: use mtime if available, then title for determinism
            return (-(getattr(t, "mtime", 0) or 0), (t.title or ""))

        self._view_tracks = sorted(self._view_tracks, key=sort_key)
        self._display_tracks()
        if playing_fp:
            for i, t in enumerate(self._view_tracks):
                if t.filepath == playing_fp:
                    self.set_current_track(i)
                    self.delegate.set_playing_track(playing_fp)
                    self.list_widget.viewport().update()
                    break

