"""
Web Integration Module

Handles web server functionality for remote control via browser.
Exports WebIntegration class that manages all web-related functionality.
"""

from PySide6.QtCore import QObject, QTimer
import os

from musicplayer.core.web_server import WebServer
from musicplayer.core.settings import get_playlist_sort_mode
from musicplayer.core.db import get_favorite_filepaths


class WebIntegration(QObject):
    """
    Manages web server integration for remote player control.
    """

    def __init__(self, main_window):
        super().__init__()
        self._main_window = main_window
        self._web_server = WebServer()
        self._web_last_track_fp = None
        self._wire_signals()

    def _wire_signals(self):
        """Connect web server signals to main window actions."""
        ws = self._web_server
        ws.play_requested.connect(self._main_window.player.play)
        ws.pause_requested.connect(self._main_window.player.pause)
        ws.next_requested.connect(self._main_window._on_next)
        ws.previous_requested.connect(self._main_window._on_previous)
        ws.volume_requested.connect(self._main_window.player.set_volume)
        ws.seek_requested.connect(self._main_window.player.set_position)
        ws.play_track_requested.connect(lambda idx: self._main_window._play_track_at_view_index(idx))
        ws.play_folder_requested.connect(self._on_play_folder)
        ws.toggle_favorite_requested.connect(self._on_toggle_favorite)
        ws.toggle_repeat_requested.connect(self._on_toggle_repeat)
        ws.play_favorites_requested.connect(lambda: self._main_window._on_favorites_toggled(True))
        ws.play_top_requested.connect(lambda: self._main_window._on_top_toggled(True))
        ws.play_similar_requested.connect(self._main_window._on_similar_tracks_requested)

    def start(self, port: int = 8080):
        """Start the web server."""
        try:
            self._web_server.start_async(port)
            QTimer.singleShot(1000, self._sync_playlist)
            QTimer.singleShot(1000, self._update_favorites)
            print(f"[WebIntegration] Web server started on port {port}")
        except Exception as e:
            print(f"[WebIntegration] Failed to start web server: {e}")

    def stop(self):
        """Stop the web server."""
        self._web_server.stop()

    def is_running(self) -> bool:
        """Check if web server is running."""
        return self._web_server.is_running()

    def set_enabled(self, enabled: bool):
        """Enable or disable the web server."""
        if enabled:
            if not self.is_running():
                self.start(self._main_window.settings.web_server_port)
        else:
            self.stop()

    def set_port(self, port: int):
        """Change web server port (restarts server if running)."""
        if self.is_running():
            self.stop()
            self.start(port)

    def _on_play_folder(self, folder_path: str):
        """Handle play folder request from web UI."""
        if not os.path.isdir(folder_path):
            print(f"[WebIntegration] Folder not found: {folder_path}")
            return
        music_folder = self._main_window.settings.music_folder
        if music_folder and os.path.isdir(music_folder):
            folder_norm = os.path.normpath(folder_path)
            music_norm = os.path.normpath(music_folder)
            if not folder_norm.startswith(music_norm + os.sep) and folder_norm != music_norm:
                print(f"[WebIntegration] Folder outside music directory: {folder_path}")
                return
        self._main_window._scan_folder(folder_path)

    def _on_toggle_favorite(self):
        """Handle favorite toggle request from web UI."""
        self._main_window.controls_widget.favorite_toggled.emit()

    def _on_toggle_repeat(self):
        """Cycle through repeat modes: none -> all -> one -> none."""
        from musicplayer.core.playlist import RepeatMode
        current = self._main_window.playlist.get_repeat_mode()
        if current == RepeatMode.NONE:
            new_mode = RepeatMode.ALL
        elif current == RepeatMode.ALL:
            new_mode = RepeatMode.ONE
        else:
            new_mode = RepeatMode.NONE
        self._main_window.playlist.set_repeat_mode(new_mode)
        self._main_window.controls_widget.set_repeat_mode(new_mode)
        if self._web_server.is_running():
            self._web_server.update_state(
                self._main_window.player.is_playing(),
                self._main_window.player.get_position(),
                self._main_window.player.get_duration(),
                self._main_window.player.get_volume(),
                new_mode
            )

    def _sync_playlist(self):
        """Sync playlist to web server."""
        if self._web_server.is_running():
            tracks = self._main_window.playlist_widget.get_view_tracks()
            self._web_server.update_playlist(tracks)

    def update_playlist(self):
        """Update playlist in web server."""
        if self._web_server.is_running():
            self._web_server.update_playlist(self._main_window.playlist_widget.get_view_tracks())

    def update_favorites(self):
        """Update favorites list in web server."""
        if self._web_server.is_running():
            self._web_server.update_favorites(get_favorite_filepaths())

    def update_state(self):
        """Update web server with current player state."""
        if not self._web_server.is_running():
            return

        self.update_favorites()

        view_tracks = self._main_window.playlist_widget.get_view_tracks()
        playing_fp = self._main_window._current_playing_filepath

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
            self._main_window.player.is_playing(),
            self._main_window.player.get_position(),
            self._main_window.player.get_duration(),
            self._main_window.player.get_volume(),
            self._main_window.playlist.get_repeat_mode()
        )
        self._web_server.update_sort_mode(sort_mode)
        self._web_server.update_playlist_title(self._main_window.title_bar.get_playlist_title() or "")
        self._web_server.update_track(current_track)
        self._web_server.update_current_index(current_index)

        if not hasattr(self, '_web_last_track_fp'):
            self._web_last_track_fp = current_track.filepath
            return

        if self._web_last_track_fp != current_track.filepath:
            self._web_last_track_fp = current_track.filepath
            tracks = self._main_window.playlist_widget.get_view_tracks()
            self._web_server.update_playlist(tracks)