"""
Main Window Module

Assembles all UI blocks into the main application window.
Handles coordination between player, playlist, and controls.
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QFileDialog, QMessageBox, QPushButton, QLabel,
                                QApplication, QDialog, QCheckBox, QSystemTrayIcon, QMenu, QComboBox)
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import Qt, QPoint, QTimer, QByteArray, QUrl, Q_ARG, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QIcon, QColor, QPalette
import subprocess
import sys
import os
import socket
from pathlib import Path
from PySide6.QtGui import QFont, QIcon
from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer.core.player import AudioPlayer
from musicplayer.core.playlist import Playlist
from musicplayer.core.db import TrackInfo
from musicplayer.core.settings import AppSettings, get_playlist_sort_mode, set_playlist_sort_mode
from musicplayer.core.ipc import IPCServer
from musicplayer.core.web_server import WebServer
from musicplayer.core.db import is_favorite as db_is_favorite, toggle_favorite as db_toggle_favorite
from musicplayer.ui.svg_icons import get_music_note_svg
from musicplayer.utils.audio_scanner import AudioScanner
from musicplayer.utils.analysis_worker import AnalysisManager # ADDED

from musicplayer.ui.track_info import TrackInfoWidget
from musicplayer.ui.playlist_view import PlaylistWidget, PlaylistItem
from musicplayer.ui.controls import ControlsWidget
from musicplayer.ui.sidebar import SideBarWidget
from musicplayer.ui.mini_widget import MiniPlayerWidget
from musicplayer.core.media_keys import _install_media_keys_filter
from musicplayer.core.recommendations import find_similar_tracks # NEW import
from musicplayer.core.db import get_all_library_tracks_light # NEW import



# Global accent color
from musicplayer import config as cfg
from musicplayer.config import DIVIDER_COLOR


def _get_exe_dir() -> Path:
    """Get the directory containing the exe (or project root in dev mode)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


class MissingTrackDialog(QMessageBox):
    """
    Dialog shown when a track file is missing.
    Asks user whether to remove the track from the library.
    """

    def __init__(self, track_title: str, track_artist: str, filepath: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Трек не найден")
        self.setIcon(QMessageBox.Warning)

        # Custom text with track info
        file_name = Path(filepath).name
        self.setText(
            f"<b>Файл не найден:</b><br><br>"
            f"<i>{track_title}</i> — {track_artist}<br>"
            f"<span style='color: #888888; font-size: 11px;'>{file_name}</span><br><br>"
            f"Удалить запись из библиотеки?"
        )

        # Add standard buttons
        self.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.setDefaultButton(QMessageBox.No)


def remove_track_from_library(filepath: str, playlist_widget=None, playlist=None, main_window=None) -> bool:
    """
    Remove a track from the library database and cache.

    Args:
        filepath: Path to the track file
        playlist_widget: Optional PlaylistWidget reference to remove from view
        playlist: Optional Playlist object to update current index
        main_window: Optional MainWindow reference to clear playing state

    Returns:
        True if track was successfully removed
    """
    from musicplayer.core.db import delete_track

    # Delete from DB (also removes cover file via delete_track)
    delete_track(filepath)

    # Remove from playlist view if provided
    if playlist_widget:
        # Remove from _full_tracks (always)
        original_full = playlist_widget._full_tracks
        playlist_widget._full_tracks = [
            t for t in original_full if t.filepath != filepath
        ]

        # Handle _view_tracks
        if playlist_widget._view_tracks is original_full:
            # _view_tracks points to same list as _full_tracks
            playlist_widget._view_tracks = playlist_widget._full_tracks
        else:
            # _view_tracks is a separate filtered list (e.g. favorites)
            playlist_widget._view_tracks = [
                t for t in playlist_widget._view_tracks if t.filepath != filepath
            ]

        # Update delegate reference
        playlist_widget.delegate.tracks_ref = playlist_widget._view_tracks

        # Clear and rebuild the QListWidget
        playlist_widget.list_widget.clear()
        for i, track in enumerate(playlist_widget._view_tracks):
            item = PlaylistItem(track, i)
            playlist_widget.list_widget.addItem(item)
        playlist_widget._current_index = -1

        # Force viewport repaint
        playlist_widget.list_widget.viewport().update()

    # Update the core Playlist object if provided
    if playlist:
        full_tracks = playlist.get_tracks()
        updated_tracks = [t for t in full_tracks if t.filepath != filepath]
        playlist.set_tracks(updated_tracks)

        # If the removed track was the current one, reset current index
        current_track = playlist.get_current_track()
        if current_track and current_track.filepath == filepath:
            if len(updated_tracks) > 0:
                playlist.play_track_at(0)
            else:
                playlist._current_index = -1

    # Clear playing state in main window if provided
    if main_window:
        if main_window._current_playing_filepath == filepath:
            main_window._current_playing_filepath = None
            main_window.controls_widget.set_current_track_favorite("", False)
            main_window.player.stop()

    return True


class MainWindow(QMainWindow):
    """
    Main application window.
    """
    
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("SonicFlame Player")
        self.setMinimumSize(1100, 600)
        self.setStyleSheet("background-color: #000000;")

        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(200, 200, 200, 100))
        self.setGraphicsEffect(shadow)

        # Core components
        self.player = AudioPlayer()
        self.playlist = Playlist()
        self.settings = AppSettings()
        self.scanner = None
        self._drag_pos = QPoint()
        self._current_folder_path = None
        self._current_playing_filepath = None
        self._blink_anim = None
        self._blink_phase = 0.0

        # --- New IPC and Subprocess Handling ---
        self.library_process = None
        self.ipc_server = IPCServer(self)
        self.ipc_server.play_track_requested.connect(self._play_from_library)
        self.ipc_server.artist_play_requested.connect(self._on_play_artist_requested)
        self.ipc_server.library_closed.connect(self._on_ipc_library_closed)

        # Web server for remote control
        self._web_server = WebServer()
        # Wire web server signals to player methods using dedicated slots
        self._wire_web_server_signals()
        # ---

        # Analysis Manager for background audio feature extraction
        self.analysis_manager = AnalysisManager(self) # ADDED

        # Setup UI
        self._apply_saved_accent_color()
        
        # System tray icon - init before _restore_state to avoid AttributeError
        self._tray_icon = None
        self._mini_widget = None
        self._setup_tray_icon()
        
        self._setup_ui()
        self._connect_signals()

        # Disable folder button until music_folder is configured
        has_music_folder = bool(self.settings.music_folder and os.path.isdir(self.settings.music_folder))
        self.sidebar.set_music_folder_configured(has_music_folder)

        self._restore_state()

        # Media keys handler
        self._media_keys_handler = None
        self._setup_media_keys()

        # Start web server if enabled
        if self.settings.web_server_enabled:
            self._start_web_server()

    def _get_icon_path(self) -> Path:
        """Get path to icon file."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / "Sonic-Flame.ico"
        return Path(__file__).parent.parent.parent / "Sonic-Flame.ico"

    def _setup_tray_icon(self):
        """Create system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)
        icon_path = self._get_icon_path()
        if icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Показать")
        show_action.triggered.connect(self._restore_from_tray)
        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self._quit_from_tray)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.setVisible(False)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self._tray_icon:
            self._tray_icon.setVisible(False)
        self._hide_mini_widget()
        self.ipc_server.send_close()

    def _quit_from_tray(self):
        self.close()

    def _apply_saved_accent_color(self):
        saved_color = self.settings._data.get("accent_color")
        if saved_color:
            cfg.ACCENT_COLOR = saved_color

    def _setup_custom_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)
        
        self.title_icon_widget = QSvgWidget()
        self.title_icon_widget.setFixedSize(20, 20)
        self.title_icon_widget.renderer().load(get_music_note_svg(60).encode('utf-8'))
        title_layout.addWidget(self.title_icon_widget)

        title_label = QLabel("SonicFlame Player")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        self.playlist_title_label = QLabel("")
        self.playlist_title_label.setStyleSheet("color: #888888; font-size: 12px; margin-left: 4px;")
        title_layout.addWidget(self.playlist_title_label)

        self.sep_label = QLabel("•")
        self.sep_label.setStyleSheet("color: #555555; font-size: 12px;")
        self.sep_label.setVisible(False)
        title_layout.addWidget(self.sep_label)

        self.scanning_status_label = QLabel("")
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.scanning_status_label.setVisible(False)
        title_layout.addWidget(self.scanning_status_label)
        
        title_layout.addStretch()

        # Sort mode dropdown (placed at the far right near the minimize button)
        self._sort_combo = QComboBox()
        self._sort_combo.setStyleSheet(
            """
            QComboBox { background: #000000; border: none; color: #CCCCCC; font-size: 12px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #000000; color: #CCCCCC; selection-background-color: #333333; }
            """
        )
        self._sort_combo.setFixedSize(170, 26)
        self._sort_combo.addItems(["По исполнителю", "По названию", "По новизне", "Перемешать"])
        
        self._sort_combo.blockSignals(True)
        try:
            current = get_playlist_sort_mode()
        except Exception:
            current = "artist"
        index_map = {"artist": 0, "title": 1, "newest": 2, "shuffle": 3}
        self._sort_combo.setCurrentIndex(index_map.get(current, 0))
        self._sort_combo.blockSignals(False)
        
        self._sort_combo.currentIndexChanged.connect(self._on_sort_mode_changed)
        title_layout.addWidget(self._sort_combo)
        
        min_btn = QPushButton("─")
        min_btn.setFixedSize(36, 30)
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.setStyleSheet(self._get_title_button_style())
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(36, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(self._get_title_button_style(cfg.get_accent_color()))
        self.close_btn.clicked.connect(self.close)
        title_layout.addWidget(self.close_btn)
        
        return title_bar
    
    def _get_title_button_style(self, hover_color: str = "#333333") -> str:
        return f"""
            QPushButton {{ background-color: transparent; border: none; color: #FFFFFF; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ background-color: #555555; }}
        """

    def _on_sort_mode_changed(self, index: int):
        # Map UI index to internal sort mode
        mapping = {0: "artist", 1: "title", 2: "newest", 3: "shuffle"}
        mode = mapping.get(index, "artist")
        
        try:
            set_playlist_sort_mode(mode)
        except Exception:
            pass
        
        # Apply to the active playlist display
        if hasattr(self, 'playlist'):
            self.playlist.set_sort_mode(mode)
            
        # Re-render the UI list to reflect new order
        if self.playlist_widget:
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            
            # Restore current track highlight if possible
            current = self.playlist.get_current_track()
            current_fp = getattr(self, "_current_playing_filepath", None) or (current.filepath if current else None)
            if current_fp:
                self.playlist_widget.set_current_track_by_filepath(current_fp)
                self.playlist_widget.set_playing_track(current_fp)
    
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._setup_custom_title_bar())
        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        self.sidebar = SideBarWidget()
        middle_layout.addWidget(self.sidebar)
        self.track_info_widget = TrackInfoWidget()
        middle_layout.addWidget(self.track_info_widget, stretch=0)
        self.playlist_widget = PlaylistWidget()
        middle_layout.addWidget(self.playlist_widget, stretch=1)
        main_layout.addLayout(middle_layout, stretch=1)
        self.controls_widget = ControlsWidget()
        main_layout.addWidget(self.controls_widget)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
    
    def _connect_signals(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)
        self.player.error_occurred.connect(self._on_player_error)
        self.playlist_widget.track_selected.connect(self._on_track_selected)
        self.playlist_widget.favorite_clicked.connect(self._on_favorite_clicked)
        self.playlist_widget.badge_clicked.connect(self._on_badge_clicked)
        self.controls_widget.play_pause_clicked.connect(self._on_play_pause)
        self.controls_widget.next_clicked.connect(self._on_next)
        self.controls_widget.previous_clicked.connect(self._on_previous)
        self.controls_widget.repeat_toggled.connect(self._on_repeat_toggled)
        self.controls_widget.seek_requested.connect(self._on_seek)
        self.controls_widget.volume_changed.connect(self._on_volume_changed)
        self.controls_widget.favorite_toggled.connect(self._on_control_favorite_toggled)
        self.controls_widget.similar_tracks_requested.connect(self._on_similar_tracks_requested) # NEW
        self.sidebar.folder_open_requested.connect(self._on_open_folder)
        self.sidebar.favorites_toggled.connect(self._on_favorites_toggled)
        self.sidebar.top_requested.connect(self._on_top_toggled)
        self.sidebar.playlist_type_changed.connect(self._on_playlist_type_changed)
        self.sidebar.settings_requested.connect(self._on_settings_requested)
        self.sidebar.library_requested.connect(self._on_library_requested)
        self.player.media_status_changed.connect(self._on_media_status_changed)
        self.player.volume_changed.connect(self._on_volume_changed_for_web)
        self.player.volume_changed.connect(self.controls_widget.set_volume)

    def _on_volume_changed_for_web(self, volume: float):
        """Update web server when volume changes."""
        self._update_web_server_state()
    
    def _on_open_folder(self):
        start_dir = self._current_folder_path or self.settings.last_folder or self.settings.music_folder or ""
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с музыкой", start_dir)
        if not folder:
            return
        music_folder = self.settings.music_folder
        if music_folder and os.path.isdir(music_folder):
            folder_norm = os.path.normpath(folder)
            music_norm = os.path.normpath(music_folder)
            if not folder_norm.startswith(music_norm + os.sep) and folder_norm != music_norm:
                QMessageBox.information(
                    self,
                    "Папка вне музыкальной директории",
                    f"Выбранная папка должна находиться внутри основной папки с музыкой:\n{music_folder}"
                )
                return
        self.settings.last_folder = folder
        self.settings.playlist_type = "Folder"
        self.playlist_title_label.setText(Path(folder).name)
        self.sep_label.setVisible(True)
        self.scanning_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.scanning_status_label.setText("Сканирование...")
        self.scanning_status_label.setVisible(True)
        self._start_blink_animation()
        self._scan_folder(folder)
    
    def _scan_folder(self, folder_path: str):
        self._current_folder_path = folder_path
        if self.scanner and self.scanner.isRunning():
            self.scanner.cancel()
        self.scanner = AudioScanner(folder_path, use_cache=True)
        self._removed_tracks_count = 0
        self.scanner.scanning_started.connect(self._on_scanning_started)
        self.scanner.track_scanned.connect(self._on_track_scanned)
        self.scanner.scanning_progress.connect(self._on_scanning_progress)
        self.scanner.tracks_removed.connect(self._on_tracks_removed)
        self.scanner.scanning_finished.connect(self._on_scanning_finished)
        self.scanner.scanning_error.connect(self._on_scanning_error)
        self.scanner.start()
    
    def _on_scanning_started(self, folder_path: str):
        self.playlist.clear()
        try:
            self.playlist.begin_bulk_add()
        except Exception:
            pass
        self.playlist_widget.clear()
        self.playlist_widget._view_tracks = self.playlist_widget._full_tracks
        self.playlist_widget.delegate.tracks_ref = self.playlist_widget._view_tracks
        self.sidebar.set_all_buttons_enabled(False, include_folder=False)

    def _start_blink_animation(self):
        self._blink_phase = 0.0
        if self._blink_anim:
            self._blink_anim.stop()
        self._blink_anim = QPropertyAnimation(self, b"blink_phase")
        self._blink_anim.setDuration(4000)
        self._blink_anim.setStartValue(0.0)
        self._blink_anim.setEndValue(1.0)
        self._blink_anim.setEasingCurve(QEasingCurve.SineCurve)
        self._blink_anim.valueChanged.connect(self._update_blink_color)
        self._blink_anim.finished.connect(self._on_blink_loop)
        self._blink_anim.start()

    def _on_blink_loop(self):
        if self._blink_anim:
            self._blink_anim.setCurrentTime(0)
            self._blink_anim.start()

    def _stop_blink_animation(self):
        if self._blink_anim:
            self._blink_anim.stop()
            self._blink_anim.deleteLater()
            self._blink_anim = None

    def _get_blink_phase(self):
        return self._blink_phase

    def _set_blink_phase(self, value):
        self._blink_phase = value

    blink_phase = Property(float, _get_blink_phase, _set_blink_phase)

    def _update_blink_color(self):
        t = abs(0.5 - self._blink_phase) * 2
        r = int(136 + (255 - 136) * t)
        g = int(136 + (255 - 136) * t)
        b = int(136 + (255 - 136) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self.scanning_status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _on_scanning_progress(self, current: int, total: int):
        self.scanning_status_label.setText(f"Сканирование: {current}/{total}")

    def _on_tracks_removed(self, count: int):
        self._removed_tracks_count += count

    def _on_track_scanned(self, track):
        self.playlist.add_tracks([track])
        self.playlist_widget.add_track(track)
    
    def _on_scanning_finished(self, tracks: list):
        from musicplayer.core.db import upsert_folder

        self._stop_blink_animation()
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")

        removed = self._removed_tracks_count
        track_count = len(tracks)
        status = f"Загружено: {track_count} треков"
        if removed > 0:
            status += f". Не найдено: {removed}"
        self.scanning_status_label.setText(status)

        if self._current_folder_path:
            upsert_folder(self._current_folder_path, track_count)
        QTimer.singleShot(3000, lambda: (
                self.scanning_status_label.setText(f"{track_count}"),
                self.scanning_status_label.setVisible(True)
            ))
        self.sidebar.set_all_buttons_enabled(True)

        if self.sidebar._favorites_active:
            self.sidebar._favorites_active = False
            self.sidebar.favorites_btn.set_active(False)
            self.settings.favorites_mode = False
        if self.sidebar._top_active:
            self.sidebar._top_active = False
            self.sidebar.top_btn.set_active(False)
            self.settings.top_mode = False

        if self.playlist.get_track_count() == 0 and tracks:
            try:
                self.playlist.begin_bulk_add()
            except Exception:
                pass
            self.playlist.load_tracks_no_sort(tracks)
            self.playlist_widget.load_tracks(tracks)
            try:
                self.playlist.end_bulk_add()
            except Exception:
                pass
        try:
            self.playlist.end_bulk_add()
        except Exception:
            pass

        from musicplayer.core.settings import get_playlist_sort_mode
        sort_mode = get_playlist_sort_mode()
        self.playlist.set_sort_mode(sort_mode)
        self.playlist_widget.load_tracks(self.playlist.get_tracks())
        if hasattr(self, "_sort_combo"):
            self._sort_combo.blockSignals(True)
            index_map = {"artist": 0, "title": 1, "newest": 2, "shuffle": 3}
            self._sort_combo.setCurrentIndex(index_map.get(sort_mode, 0))
            self._sort_combo.blockSignals(False)

        last_fp = self.settings.last_track
        restored = False
        if last_fp:
            for i, t in enumerate(self.playlist_widget.get_view_tracks()):
                if t.filepath == last_fp:
                    self._play_track_at_view_index(i)
                    restored = True
                    break
        if not restored and self.playlist.get_track_count() > 0:
            self._play_track_at_view_index(0)

        self._update_playlist_title()
        self.ipc_server.send_refresh()
        self._update_web_server_playlist()

        # Start background analysis for new/unanalyzed tracks
        self.analysis_manager.start_analysis(self.playlist.get_tracks()) # ADDED
    
    def _on_scanning_error(self, error_msg: str):
        self._stop_blink_animation()
        self.scanning_status_label.setVisible(False)
        self.sidebar.set_all_buttons_enabled(True)
        QMessageBox.warning(self, "Scan Error", error_msg)

    def _update_playlist_title(self):
        text, show_sep = "", False
        if self.sidebar._top_active:
            text, show_sep = "Топ", True
        elif self.sidebar._favorites_active:
            text, show_sep = "Избранное", True
        elif self._current_folder_path:
            text, show_sep = Path(self._current_folder_path).name, True
        self.playlist_title_label.setText(text)
        self.sep_label.setVisible(show_sep)

    def _handle_missing_track(self, filepath: str):
        remove_track_from_library(
            filepath,
            playlist_widget=self.playlist_widget,
            playlist=self.playlist,
            main_window=self
        )
        self.playlist_widget._display_tracks()
        self.playlist_widget.list_widget.viewport().update()
    
    def _on_track_selected(self, index: int):
        self._play_track_at_view_index(index)
    
    def _play_track_at_view_index(self, view_index: int):
        view_tracks = self.playlist_widget.get_view_tracks()
        if not (0 <= view_index < len(view_tracks)):
            return

        track = view_tracks[view_index]
        if not os.path.exists(track.filepath):
            dialog = MissingTrackDialog(track.title, track.artist, track.filepath, self)
            if dialog.exec() == QMessageBox.Yes:
                QTimer.singleShot(0, lambda fp=track.filepath: self._handle_missing_track(fp))
            return

        if self._current_playing_filepath == track.filepath and self.player.get_state() == QMediaPlayer.PlayingState:
            return

        # The track object comes from the view, which should be in sync with the
        # core playlist, especially after a scan/load. The view_index is
        # assumed to be valid for the core playlist as well.
        self.playlist.play_track_at(view_index)
            
        self._current_playing_filepath = track.filepath
        self.settings._data["last_track"] = track.filepath
        self.settings._data["last_folder"] = str(Path(track.filepath).parent)
        
        if self.settings.favorites_mode:
            self.settings.playlist_type = "Favorites"
        elif self.settings.top_mode:
            self.settings.playlist_type = "Top"
        elif self.settings.playlist_type not in ("Folder", "Favorites", "Top"):
            self.settings.playlist_type = "Playlist"
        
        self.player.load_source(track)
        print(f"[DEBUG _play_track_at_view_index] Loaded source: {track.filepath}")

        from musicplayer.core.db import ensure_cover_for_track
        if not track.has_cover or not track.cover_data:
            track.cover_data = ensure_cover_for_track(track.filepath)
            track.has_cover = bool(track.cover_data)

        self._apply_dynamic_color_from_track(track)
        self.track_info_widget.update_track_info(track)
        self.playlist_widget.set_current_track_by_filepath(track.filepath)
        self.playlist_widget.set_playing_track(track.filepath)
        self.controls_widget.set_current_track_favorite(track.filepath, db_is_favorite(track.filepath))
        self._update_mini_widget_track(track)
        self.player.play()
        self.controls_widget.set_play_state(True)
        
        self.settings.batch_save()

        # Force web server state update after starting a track.
        # A small delay allows the player to report the correct duration.
        QTimer.singleShot(100, self._update_web_server_state)

    def _update_mini_widget_track(self, track):
        if self._mini_widget and self._mini_widget.isVisible():
            self._mini_widget.set_track_info(track.artist, track.title)

    def _apply_dynamic_color_from_track(self, track):
        if not self.settings.dynamic_color: return
        from musicplayer.ui.accent_style import apply_accent_to_main_window
        from musicplayer.utils.color_extractor import extract_accent_color
        
        new_color = extract_accent_color(track.cover_data) if track.cover_data else "#ed6a02"
        cfg.ACCENT_COLOR = new_color
        self.settings._data["accent_color"] = new_color
        apply_accent_to_main_window(self)
        if hasattr(self.playlist_widget, 'list_widget'):
            self.playlist_widget.list_widget.viewport().update()
        self.ipc_server.send_accent_color(new_color)

    def _on_dynamic_color_toggled(self, enabled: bool):
        if not enabled: return
        current_filepath = self._current_playing_filepath
        if current_filepath:
            try:
                track = next(t for t in self.playlist_widget.get_view_tracks() if t.filepath == current_filepath)
                self._apply_dynamic_color_from_track(track)
            except StopIteration:
                pass

    def _on_play_pause(self):
        self.player.toggle_play_pause()
        self._update_web_server_state()
    
    def _on_next(self):
        view_tracks = self.playlist_widget.get_view_tracks()
        if not view_tracks:
            return
        
        # Find current track in view_tracks (not from core playlist which may be sorted differently)
        current_fp = self._current_playing_filepath
        current_index = -1
        for i, t in enumerate(view_tracks):
            if t.filepath == current_fp:
                current_index = i
                break
        
        # Get next track from view_tracks order
        next_index = current_index + 1
        repeat_mode = self.playlist.get_repeat_mode()
        
        if next_index >= len(view_tracks):
            if repeat_mode == "all":
                next_index = 0
            else:
                self.player.stop()
                return
        
        self._play_track_at_view_index(next_index)

    def _on_previous(self):
        if self.player.get_position() > 3000:
            self.player.set_position(0)
            return

        view_tracks = self.playlist_widget.get_view_tracks()
        if not view_tracks:
            return
        
        # Find current track in view_tracks (not from core playlist which may be sorted differently)
        current_fp = self._current_playing_filepath
        current_index = -1
        for i, t in enumerate(view_tracks):
            if t.filepath == current_fp:
                current_index = i
                break
        
        # Get previous track from view_tracks order
        prev_index = current_index - 1
        repeat_mode = self.playlist.get_repeat_mode()
        
        if prev_index < 0:
            if repeat_mode == "all":
                prev_index = len(view_tracks) - 1
            else:
                prev_index = 0
        
        self._play_track_at_view_index(prev_index)

    def _on_repeat_toggled(self, mode: str):
        self.playlist.set_repeat_mode(mode)
        self.settings.repeat_mode = mode
    
    def _on_seek(self, position_ms: int):
        self.player.set_position(position_ms)

    def _on_volume_changed(self, volume: float):
        self.player.set_volume(volume)
        self.settings.volume = volume
    
    def _on_position_changed(self, position_ms: int):
        self.controls_widget.set_position(position_ms)
        self._update_web_server_state()

    def _on_duration_changed(self, duration_ms: int):
        self.controls_widget.set_duration(duration_ms)
        self._update_web_server_state()

    def _on_state_changed(self, state):
        is_playing = (state == QMediaPlayer.PlayingState)
        self.controls_widget.set_play_state(is_playing)
        if self._mini_widget and self._mini_widget.isVisible():
            self._mini_widget.set_play_state(is_playing)
        self._update_web_server_state()
    
    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self._current_playing_filepath:
                from musicplayer.core.db import increment_play_count
                increment_play_count(self._current_playing_filepath)
            self._on_next()
    
    def _on_player_error(self, error_msg: str):
        QMessageBox.critical(self, "Player Error", error_msg)

    def _on_favorites_toggled(self, enabled: bool):
        self.playlist_title_label.setText("Избранное")
        self.sep_label.setVisible(True)
        self.scanning_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.scanning_status_label.setText("Загрузка...")
        self.scanning_status_label.setVisible(True)
        self._start_blink_animation()

        from musicplayer.core.db import get_favorite_tracks
        fav_tracks = get_favorite_tracks()
        self.playlist.clear()
        if fav_tracks:
            self.playlist.set_tracks(fav_tracks)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
        self._update_web_server_playlist()
        self.player.stop()
        self._current_playing_filepath = None
        
        # Reset both buttons and internal state first, then activate favorites
        self.sidebar._favorites_active = False
        self.sidebar._top_active = False
        self.sidebar.favorites_btn.set_active(False)
        self.sidebar.top_btn.set_active(False)
        self.sidebar._favorites_active = True
        self.sidebar.favorites_btn.set_active(True)
        
        self.settings.favorites_mode = True
        self.settings.top_mode = False
        if self.playlist.get_track_count() > 0: self._play_track_at_view_index(0)
        else: self.controls_widget.set_current_track_favorite("", False)
        self._stop_blink_animation()
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.scanning_status_label.setText(f"{self.playlist.get_track_count()}")
        self.scanning_status_label.setVisible(True)

    def _on_top_toggled(self, enabled: bool):
        self.playlist_title_label.setText("Топ")
        self.sep_label.setVisible(True)
        self.scanning_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.scanning_status_label.setText("Загрузка...")
        self.scanning_status_label.setVisible(True)
        self._start_blink_animation()

        from musicplayer.core.db import get_top_tracks
        top_tracks = get_top_tracks(50)
        self.playlist.clear()
        if top_tracks:
            self.playlist.set_tracks(top_tracks)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
        self._update_web_server_playlist()
        self.player.stop()
        self._current_playing_filepath = None

        # Reset both buttons and internal state first, then activate top
        self.sidebar._favorites_active = False
        self.sidebar._top_active = False
        self.sidebar.favorites_btn.set_active(False)
        self.sidebar.top_btn.set_active(False)
        self.sidebar._top_active = True
        self.sidebar.top_btn.set_active(True)

        self.settings.top_mode = True
        self.settings.favorites_mode = False
        if self.playlist.get_track_count() > 0: self._play_track_at_view_index(0)
        else: self.controls_widget.set_current_track_favorite("", False)
        self._stop_blink_animation()
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.scanning_status_label.setText(f"{self.playlist.get_track_count()}")
        self.scanning_status_label.setVisible(True)

    def _on_playlist_type_changed(self, playlist_type: str):
        """Handle playlist type changes from sidebar."""
        self.settings.playlist_type = playlist_type

    def _on_settings_requested(self):
        from musicplayer.ui.settings_dialog import SettingsDialog
        from musicplayer.ui.accent_style import apply_accent_to_main_window
        dialog = SettingsDialog(self.settings, self)
        dialog.accent_color_changed.connect(lambda color: apply_accent_to_main_window(self, settings_dialog=dialog))
        dialog.accent_color_changed.connect(lambda color: self.ipc_server.send_accent_color(color))
        dialog.dynamic_color_toggled.connect(self._on_dynamic_color_toggled)
        dialog.web_server_toggled.connect(self._on_web_server_toggled)
        dialog.web_server_port_changed.connect(self._on_web_server_port_changed)
        dialog.music_folder_changed.connect(self.sidebar.set_music_folder_configured)
        dialog.exec()
        apply_accent_to_main_window(self)

    def _on_web_server_toggled(self, enabled: bool):
        """Handle web server toggle from settings."""
        if enabled:
            if not self._web_server.is_running():
                self._start_web_server()
        else:
            self._stop_web_server()

    def _on_web_server_port_changed(self, port: int):
        """Handle web server port change from settings."""
        if self._web_server.is_running():
            self._stop_web_server()
            self._start_web_server()

    def _on_library_requested(self):
        # Start server before launching client to prevent race condition
        if not self.ipc_server.is_client_connected():
            self.ipc_server.start()

        if self.library_process and self.library_process.poll() is None:
            self.ipc_server.send_show()
            QTimer.singleShot(100, self.ipc_server.send_refresh)
            return

        exe_dir = _get_exe_dir()
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--library"]
        else:
            args = [sys.executable, str(exe_dir / "main.py"), "--library"]
        
        self.library_process = subprocess.Popen(args)

    def _on_ipc_library_closed(self):
        print("[MainWindow] Received library closed signal.")
        if self.library_process:
            self.library_process.poll()
        
    def _play_from_library(self, filepath: str):
        view_tracks = self.playlist_widget.get_view_tracks()
        try:
            idx = next(i for i, t in enumerate(view_tracks) if t.filepath == filepath)
            self._play_track_at_view_index(idx)
            return
        except StopIteration:
            pass
        
        from musicplayer.core.db import get_track
        track = get_track(filepath)
        if track:
            # If track's folder is current, just play it without rescanning
            if self._current_folder_path == str(Path(filepath).parent):
                self._play_track_from_db(track)
            else:
                # Playing from different folder = Playlist mode
                self.settings.playlist_type = "Playlist"
                self._scan_folder_and_play(str(Path(filepath).parent), filepath)

    def _on_play_artist_requested(self, artist_name: str):
        """Load all tracks by an artist and play them."""
        self.playlist_title_label.setText(artist_name)
        self.sep_label.setVisible(True)
        self.scanning_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.scanning_status_label.setText("Загрузка...")
        self.scanning_status_label.setVisible(True)
        self._start_blink_animation()

        from musicplayer.core.db import get_tracks_by_artist
        
        self.showNormal() # Bring window to front
        self.raise_()
        self.activateWindow()

        tracks = get_tracks_by_artist(artist_name)
        if not tracks:
            self._stop_blink_animation()
            return
            
        self.playlist.clear()
        self.playlist.set_tracks(tracks)
        self.playlist_widget.load_tracks(tracks)
        self._update_web_server_playlist()
        
        # Reset any special view modes
        if self.sidebar._favorites_active:
            self.sidebar._favorites_active = False
            self.sidebar.favorites_btn.set_active(False)
            self.settings.favorites_mode = False
        if self.sidebar._top_active:
            self.sidebar._top_active = False
            self.sidebar.top_btn.set_active(False)
            self.settings.top_mode = False

        self.settings.playlist_type = "Playlist"
        # self.playlist_title_label.setText(artist_name) # Already set above
        # self.sep_label.setVisible(True) # Already set above
        
        track_count = self.playlist.get_track_count()
        self._stop_blink_animation()
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.scanning_status_label.setText(f"{track_count}")
        self.scanning_status_label.setVisible(True)
        
        if track_count > 0:
            # Set playlist_type BEFORE playing to override _play_track_at_view_index logic
            self.settings.playlist_type = "Playlist"
            self._play_track_at_view_index(0)

    def _on_similar_tracks_requested(self):
        """Find and load similar tracks to the currently playing track."""
        current_fp = self._current_playing_filepath
        current_track = None
        if current_fp:
            for t in self.playlist_widget.get_view_tracks():
                if t.filepath == current_fp:
                    current_track = t
                    break
        if not current_track:
            QMessageBox.information(self, "Поиск похожих треков", "Нет текущего воспроизводимого трека для поиска похожих.")
            return

        from musicplayer.core.db import increment_play_count
        increment_play_count(current_track.filepath)

        self.scanning_status_label.setText("Поиск похожих...")
        self.scanning_status_label.setVisible(True)
        self.playlist_title_label.setText("Похожие треки" + (f" ({current_track.title[:150]}...)" if len(current_track.title) > 150 else f" ({current_track.title})"))
        self.sep_label.setVisible(True)

        # Disable sidebar buttons while loading
        self.sidebar.set_all_buttons_enabled(False, include_folder=False)

        # Get all tracks from the database (light version to save memory)
        all_tracks = get_all_library_tracks_light()

        # Filter out the current track itself from the search pool, and tracks that don't have analysis data
        search_pool = [t for t in all_tracks if t.filepath != current_track.filepath and t.tempo is not None and t.energy is not None and t.mood is not None]

        if not search_pool:
            QMessageBox.information(self, "Поиск похожих треков", "Недостаточно треков в библиотеке с данными для анализа, чтобы найти похожие.")
            self.scanning_status_label.setVisible(False)
            self.sidebar.set_all_buttons_enabled(True)
            return

        similar_tracks = find_similar_tracks(current_track, search_pool, limit=100) # Limit to 100 similar tracks

        if not similar_tracks:
            QMessageBox.information(self, "Поиск похожих треков", "Не удалось найти похожие треки.")
            self.scanning_status_label.setVisible(False)
            self.sidebar.set_all_buttons_enabled(True)
            return

        self.playlist.clear()
        self.playlist.set_tracks(similar_tracks)
        self.playlist_widget.load_tracks(similar_tracks)
        self._update_web_server_playlist()

        # Reset any special view modes from sidebar
        if self.sidebar._favorites_active:
            self.sidebar._favorites_active = False
            self.sidebar.favorites_btn.set_active(False)
            self.settings.favorites_mode = False
        if self.sidebar._top_active:
            self.sidebar._top_active = False
            self.sidebar.top_btn.set_active(False)
            self.settings.top_mode = False

        self.settings.playlist_type = "Similar" # Set playlist type

        # Update status label with count and re-enable sidebar buttons
        self.scanning_status_label.setText(f"{len(similar_tracks)}")
        self.scanning_status_label.setVisible(True)
        self.sidebar.set_all_buttons_enabled(True)

        # Start playing the first similar track, or the current track if it's in the similar list
        if self.playlist.get_track_count() > 0:
            if current_track in similar_tracks: # Play current track if it's in the new similar list
                try:
                    current_idx = next(i for i, t in enumerate(similar_tracks) if t.filepath == current_track.filepath)
                    self._play_track_at_view_index(current_idx)
                except StopIteration:
                    self._play_track_at_view_index(0)
            else:
                self._play_track_at_view_index(0) # Play the most similar track

        self._update_web_server_state()

    def _play_track_from_db(self, track):
        from musicplayer.core.db import ensure_cover_for_track
        if not os.path.exists(track.filepath):
            dialog = MissingTrackDialog(track.title, track.artist, track.filepath, self)
            if dialog.exec() == QMessageBox.Yes:
                QTimer.singleShot(0, lambda fp=track.filepath: self._handle_missing_track(fp))
            return

        self._current_playing_filepath = track.filepath
        self.settings.last_track = track.filepath
        self.settings.last_folder = str(Path(track.filepath).parent)
        self.player.load_source(track)

        if not track.has_cover or not track.cover_data:
            track.cover_data = ensure_cover_for_track(track.filepath)
            track.has_cover = bool(track.cover_data)

        self._apply_dynamic_color_from_track(track)
        self.track_info_widget.update_track_info(track)
        self.controls_widget.set_current_track_favorite(track.filepath, db_is_favorite(track.filepath))
        self.player.play()
        self.controls_widget.set_play_state(True)

    def _scan_folder_and_play(self, folder_path: str, target_filepath: str):
        # NEW: Update title bar immediately
        self.playlist_title_label.setText(Path(folder_path).name)
        self.sep_label.setVisible(True)
        self.scanning_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.scanning_status_label.setText("Загрузка...")
        self.scanning_status_label.setVisible(True)
        self._start_blink_animation()

        if self.scanner and self.scanner.isRunning(): self.scanner.cancel()
        self._current_folder_path = folder_path
        self.settings.last_folder = folder_path
        self.playlist.clear()
        self.playlist_widget.clear()
        self.playlist_widget._view_tracks = self.playlist_widget._full_tracks
        self.playlist_widget.delegate.tracks_ref = self.playlist_widget._view_tracks

        if self.sidebar._favorites_active:
            self.sidebar._favorites_active = False
            self.sidebar.favorites_btn.set_active(False)
            self.settings.favorites_mode = False

        self.scanner = AudioScanner(folder_path, use_cache=True)
        self._removed_tracks_count = 0
        self.scanner.scanning_started.connect(self._on_scanning_started)
        self.scanner.track_scanned.connect(self._on_track_scanned)
        self.scanner.scanning_progress.connect(self._on_scanning_progress)
        self.scanner.tracks_removed.connect(self._on_tracks_removed)
        self.scanner.scanning_finished.connect(lambda tracks: self._on_scan_finished_and_play(tracks, target_filepath))
        self.scanner.scanning_error.connect(self._on_scanning_error)
        self.scanner.start()

    def _on_scan_finished_and_play(self, tracks: list, target_filepath: str):
        self._stop_blink_animation()
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")

        removed = self._removed_tracks_count
        status = f"Загружено: {len(tracks)} треков"
        if removed > 0: status += f". Не найдено: {removed}"
        self.scanning_status_label.setText(status)
        QTimer.singleShot(3000, lambda: (
                self.scanning_status_label.setText(f"{len(tracks)}"),
                self.scanning_status_label.setVisible(True)
            ))
        self.sidebar.set_all_buttons_enabled(True)

        if self.playlist.get_track_count() == 0 and tracks:
            self.playlist.set_tracks(tracks)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())

        self._update_playlist_title()
        self.ipc_server.send_refresh()

        try:
            idx = next(i for i, t in enumerate(self.playlist_widget.get_view_tracks()) if t.filepath == target_filepath)
            self._play_track_at_view_index(idx)
        except StopIteration:
            if tracks: self._play_track_at_view_index(0)

    def _on_favorite_clicked(self, index: int):
        view_tracks = self.playlist_widget.get_view_tracks()
        if 0 <= index < len(view_tracks):
            track = view_tracks[index]
            new_state = self.playlist_widget.favorites.toggle_favorite(track.filepath)
            if self.sidebar._favorites_active:
                self.playlist_widget.show_favorites_only()
            else:
                self.playlist_widget.list_widget.viewport().update()
            if self._current_playing_filepath:
                self.playlist_widget.set_playing_track(self._current_playing_filepath)
            if self._current_playing_filepath == track.filepath:
                self.controls_widget.set_current_track_favorite(track.filepath, new_state)
            self._update_web_server_favorites()

    def _on_badge_clicked(self, index: int):
        from musicplayer.ui.tag_editor import TagEditorDialog
        from musicplayer.core.db import upsert_track, delete_track, extract_metadata
        view_tracks = self.playlist_widget.get_view_tracks()
        if not (0 <= index < len(view_tracks)): return
        
        track = view_tracks[index]
        old_filepath = track.filepath
        was_playing = self._current_playing_filepath == old_filepath and self.player.is_playing()
        position = self.player.get_position() if was_playing else 0

        if was_playing:
            self.player.stop()
            self.player.player.setSource(QUrl())

        dialog = TagEditorDialog(track.filepath, self, update_player=True)
        result = dialog.exec()

        if dialog.delete_confirmed:
            remove_track_from_library(
                old_filepath,
                playlist_widget=self.playlist_widget,
                playlist=self.playlist,
                main_window=self
            )
            try:
                os.remove(old_filepath)
            except OSError as e:
                QMessageBox.critical(self, "Ошибка удаления файла", f"Не удалось удалить файл:{e}")
            return

        if result == QDialog.DialogCode.Accepted:
            new_filepath = dialog.file_path
            if os.path.exists(new_filepath):
                if os.path.normpath(new_filepath) != os.path.normpath(old_filepath):
                    delete_track(old_filepath)
                updated_track = extract_metadata(new_filepath)
                if updated_track:
                    upsert_track(updated_track, os.path.getmtime(new_filepath))
                    self.playlist_widget.update_track_data(old_filepath, updated_track)
                    if self._current_playing_filepath == old_filepath:
                        self._current_playing_filepath = new_filepath
                    if self._current_playing_filepath:
                        self.playlist_widget.set_playing_track(self._current_playing_filepath)
                    if was_playing:
                        self.track_info_widget.update_track_info(updated_track)
                        self.player.load_source(updated_track)
                        QTimer.singleShot(100, lambda pos=position: self._resume_after_tag_edit(pos))
        else:  # Dialog was rejected
            if was_playing:
                old_track = next((t for t in view_tracks if t.filepath == old_filepath), None)
                if old_track:
                    self.player.load_source(old_track)
                QTimer.singleShot(100, lambda pos=position: self._resume_after_tag_edit(pos))

    def _resume_after_tag_edit(self, position: int):
        self.player.player.setPosition(position)
        self.player.play()

    def _on_control_favorite_toggled(self):
        if self._current_playing_filepath:
            new_state = db_toggle_favorite(self._current_playing_filepath)
            self.controls_widget.set_current_track_favorite(self._current_playing_filepath, new_state)
            self.playlist_widget.list_widget.viewport().update()
            self._update_web_server_favorites()

    def _restore_state(self):
        vol = self.settings.volume
        if vol is not None:
            self.player.set_volume(vol)
            self.controls_widget.set_volume(vol)
        if self.settings.repeat_mode:
            self.playlist.set_repeat_mode(self.settings.repeat_mode)
            self.controls_widget.set_repeat_mode(self.settings.repeat_mode)

        path = None
        if self.settings.favorites_mode:
            from musicplayer.core.db import get_favorite_tracks
            self.sidebar._favorites_active = True
            self.sidebar._top_active = False
            self.sidebar.favorites_btn.set_active(True)
            self.sidebar.top_btn.set_active(False)
            fav_tracks = get_favorite_tracks()
            self.playlist.set_tracks(fav_tracks)
            # Apply current sort mode to favorites view
            from musicplayer.core.settings import get_playlist_sort_mode
            mode = get_playlist_sort_mode()
            self.playlist.set_sort_mode(mode)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            self._update_web_server_playlist()
            self.settings.playlist_type = "Favorites"
            self._update_playlist_title()
            # Restore last played track
            last_fp = self.settings.last_track
            if last_fp:
                for i, t in enumerate(self.playlist_widget.get_view_tracks()):
                    if t.filepath == last_fp:
                        self._play_track_at_view_index(i)
                        break
        elif self.settings.top_mode:
            from musicplayer.core.db import get_top_tracks
            self.sidebar._favorites_active = False
            self.sidebar._top_active = True
            self.sidebar.favorites_btn.set_active(False)
            self.sidebar.top_btn.set_active(True)
            top_tracks = get_top_tracks(50)
            self.playlist.set_tracks(top_tracks)
            # Apply current sort mode to top view
            from musicplayer.core.settings import get_playlist_sort_mode
            mode = get_playlist_sort_mode()
            self.playlist.set_sort_mode(mode)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            self._update_web_server_playlist()
            self.settings.playlist_type = "Top"
            self._update_playlist_title()
            # Restore last played track
            last_fp = self.settings.last_track
            if last_fp:
                for i, t in enumerate(self.playlist_widget.get_view_tracks()):
                    if t.filepath == last_fp:
                        self._play_track_at_view_index(i)
                        break
        elif self.settings.last_folder and os.path.isdir(self.settings.last_folder):
            path = self.settings.last_folder
        elif self.settings.music_folder and os.path.isdir(self.settings.music_folder):
            path = self.settings.music_folder
        
        if path:
            self._scan_folder(path)
            self.settings.playlist_type = "Folder"
            self._update_playlist_title()

    def showMinimized(self):
        if self.settings.mini_widget_on_minimize:
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            if self._tray_icon: self._tray_icon.setVisible(True)
            self.hide()
            self.ipc_server.send_close()
            self._show_mini_widget()
        else:
            super().showMinimized()

    def _show_mini_widget(self):
        if self._mini_widget is None:
            self._mini_widget = MiniPlayerWidget()
            self._mini_widget.play_pause_clicked.connect(self._on_mini_play_pause)
            self._mini_widget.next_clicked.connect(self._on_mini_next)
            self._mini_widget.previous_clicked.connect(self._on_mini_previous)
            self._mini_widget.expand_requested.connect(self._restore_from_tray)
        current_fp = self._current_playing_filepath
        if current_fp:
            for t in self.playlist_widget.get_view_tracks():
                if t.filepath == current_fp:
                    self._mini_widget.set_track_info(t.artist, t.title)
                    break
        self._mini_widget.set_play_state(self.player.is_playing())
        self._mini_widget.show()

    def _hide_mini_widget(self):
        if self._mini_widget: self._mini_widget.hide()

    def _on_mini_play_pause(self): self.player.toggle_play_pause()
    def _on_mini_next(self): self._on_next()
    def _on_mini_previous(self): self._on_previous()

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange and self.windowState() & Qt.WindowMinimized:
            if self.settings.mini_widget_on_minimize:
                if self._tray_icon: self._tray_icon.setVisible(True)
                self.hide()
                self.ipc_server.send_close()
        super().changeEvent(event)

    def closeEvent(self, event):
        self._hide_mini_widget()
        if self._tray_icon: self._tray_icon.setVisible(False)
        if self.scanner and self.scanner.isRunning(): self.scanner.cancel()
        
        self.player.stop()
        self.ipc_server.stop() # Stops server and tells client to close
        
        if self.library_process and self.library_process.poll() is None:
            self.library_process.terminate()
            try:
                self.library_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.library_process.kill()

        if self._media_keys_handler:
            self._media_keys_handler.uninstall()

        self._stop_web_server()
        
        event.accept()

    def _setup_media_keys(self):
        def on_media_key(action: str):
            if action == "play_pause": self.player.toggle_play_pause()
            elif action == "next_track": self._on_next()
            elif action == "prev_track": self._on_previous()
        self._media_keys_handler = _install_media_keys_filter(int(self.winId()), on_media_key)

    def _wire_web_server_signals(self):
        """Connect web server signals to player/UI actions.
        This ensures the Web UI triggers real player methods on the main thread.
        """
        ws = self._web_server
        if not ws:
            return
        ws.play_requested.connect(self.player.play)
        ws.pause_requested.connect(self.player.pause)
        ws.next_requested.connect(self._on_next)
        ws.previous_requested.connect(self._on_previous)
        ws.volume_requested.connect(self.player.set_volume)
        ws.seek_requested.connect(self.player.set_position)
        ws.play_track_requested.connect(lambda idx: self._play_track_at_view_index(idx))
        ws.play_folder_requested.connect(self._on_play_folder_from_web)
        ws.toggle_favorite_requested.connect(self._on_web_toggle_favorite)
        ws.toggle_repeat_requested.connect(self._on_web_toggle_repeat)
        ws.play_favorites_requested.connect(lambda: self._on_favorites_toggled(True))
        ws.play_top_requested.connect(lambda: self._on_top_toggled(True))
        ws.play_similar_requested.connect(self._on_similar_tracks_requested)

    def _on_web_toggle_favorite(self):
        """Handle favorite toggle request from web UI."""
        # The controls widget button is the source of truth for this action
        self.controls_widget.favorite_toggled.emit()

    def _on_web_toggle_repeat(self):
        """Cycle through repeat modes: none -> all -> one -> none."""
        from musicplayer.core.playlist import RepeatMode
        current = self.playlist.get_repeat_mode()
        if current == RepeatMode.NONE:
            new_mode = RepeatMode.ALL
        elif current == RepeatMode.ALL:
            new_mode = RepeatMode.ONE
        else:
            new_mode = RepeatMode.NONE
        self.playlist.set_repeat_mode(new_mode)
        self.controls_widget.set_repeat_mode(new_mode)
        if self._web_server.is_running():
            self._web_server.update_state(
                self.player.is_playing(),
                self.player.get_position(),
                self.player.get_duration(),
                self.player.get_volume(),
                new_mode
            )

    def _on_play_folder_from_web(self, folder_path: str):
        """Обработка запроса на воспроизведение папки из веб-интерфейса."""
        if not os.path.isdir(folder_path):
            print(f"[MainWindow] Папка не найдена: {folder_path}")
            return
        music_folder = self.settings.music_folder
        if music_folder and os.path.isdir(music_folder):
            folder_norm = os.path.normpath(folder_path)
            music_norm = os.path.normpath(music_folder)
            if not folder_norm.startswith(music_norm + os.sep) and folder_norm != music_norm:
                print(f"[MainWindow] Папка вне музыкальной директории: {folder_path}")
                return
        self._scan_folder(folder_path)

    def _start_web_server(self):
        """Start the web server."""
        port = self.settings.web_server_port
        print(f"[MainWindow] Starting web server on port {port}")
        try:
            self._web_server.start_async(port)
            print(f"[MainWindow] Web server started")
            QTimer.singleShot(1000, self._sync_playlist_now)
            QTimer.singleShot(1000, self._update_web_server_favorites)
        except Exception as e:
            print(f"Failed to start web server: {e}")

    def _sync_playlist_now(self):
        """Sync playlist to web server."""
        if self._web_server.is_running():
            tracks = self.playlist_widget.get_view_tracks()
            print(f"[WEB] Initial sync: {len(tracks)} tracks")
            self._web_server.update_playlist(tracks)

    def _stop_web_server(self):
        """Stop the web server."""
        self._web_server.stop()

    def _update_web_server_playlist(self):
        """Update playlist in web server."""
        if self._web_server.is_running():
            self._web_server.update_playlist(self.playlist_widget.get_view_tracks())
    
    def _update_web_server_favorites(self):
        """Update favorites list in web server."""
        from musicplayer.core.db import get_favorite_filepaths
        if self._web_server.is_running():
            self._web_server.update_favorites(get_favorite_filepaths())

    def _update_web_server_state(self):
        """Update web server with current player state."""
        if not self._web_server.is_running():
            return
        
        # This update can be frequent, so we also sync favorites here
        self._update_web_server_favorites()

        # Use current playing filepath from widget, not from core playlist (which may be sorted differently)
        view_tracks = self.playlist_widget.get_view_tracks()
        playing_fp = self._current_playing_filepath
        
        # Find current track in view_tracks (the actual playing order, not sorted order)
        current_track = None
        current_index = -1
        if playing_fp:
            for i, t in enumerate(view_tracks):
                if t.filepath == playing_fp:
                    current_track = t
                    current_index = i
                    break
        
        if not current_track:
            return

        sort_mode = get_playlist_sort_mode()
        
        self._web_server.update_state(
            self.player.is_playing(),
            self.player.get_position(),
            self.player.get_duration(),
            self.player.get_volume(),
            self.playlist.get_repeat_mode()
        )
        self._web_server.update_sort_mode(sort_mode)
        self._web_server.update_playlist_title(self.playlist_title_label.text() or "")
        self._web_server.update_track(current_track)
        self._web_server.update_current_index(current_index)

        if not hasattr(self, '_web_last_track_fp'):
            self._web_last_track_fp = current_track.filepath
            return

        if self._web_last_track_fp != current_track.filepath:
            self._web_last_track_fp = current_track.filepath
            tracks = self.playlist_widget.get_view_tracks()
            self._web_server.update_playlist(tracks)
            print(f"[WEB] Playlist update: {len(tracks)} tracks, playing: {current_track.filepath}")


