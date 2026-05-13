"""
Playlist operations: favorites, top, artist, similar tracks.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from musicplayer.core.db import (
    get_favorite_tracks,
    get_top_tracks,
    get_tracks_by_artist,
    get_all_library_tracks_light,
    toggle_favorite as db_toggle_favorite,
)
from musicplayer.core.recommendations import find_similar_tracks


class PlaylistManager:
    """Manages playlist operations: favorites, top, artist view, similar tracks."""

    def __init__(self, main_window):
        self._mw = main_window

    def load_favorites(self, enabled: bool):
        self._mw.title_bar.set_playlist_title("Избранное")
        self._mw.title_bar.set_show_separator(True)
        self._mw.title_bar.set_scanning_status_style("color: #888888; font-size: 11px;")
        self._mw.title_bar.set_scanning_status("Загрузка...", True)
        self._mw._blink_animation.start()

        fav_tracks = get_favorite_tracks()
        self._mw.playlist.clear()
        if fav_tracks:
            self._mw.playlist.set_tracks(fav_tracks)
            self._mw.playlist_widget.load_tracks(self._mw.playlist.get_tracks())
        self._mw.player.stop()
        self._mw._current_playing_filepath = None

        self._reset_sidebar_state()
        self._mw.sidebar._favorites_active = True
        self._mw.sidebar.favorites_btn.set_active(True)
        self._mw.settings.favorites_mode = True
        self._mw.settings.top_mode = False

        if self._mw.playlist.get_track_count() > 0:
            self._mw._play_track_at_view_index(0)
        else:
            self._mw.controls_widget.set_current_track_favorite("", False)

        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style("color: #AAAAAA; font-size: 11px;")
        self._mw.title_bar.set_scanning_status(f"{self._mw.playlist.get_track_count()}", True)

    def load_top(self, enabled: bool):
        self._mw.title_bar.set_playlist_title("Топ")
        self._mw.title_bar.set_show_separator(True)
        self._mw.title_bar.set_scanning_status("Загрузка...", True)
        self._mw.title_bar.set_scanning_status_style("color: #888888; font-size: 11px;")
        self._mw._blink_animation.start()

        top_tracks = get_top_tracks(50)
        self._mw.playlist.clear()
        if top_tracks:
            self._mw.playlist.set_tracks(top_tracks)
            self._mw.playlist_widget.load_tracks(self._mw.playlist.get_tracks())
        self._mw.player.stop()
        self._mw._current_playing_filepath = None

        self._reset_sidebar_state()
        self._mw.sidebar._top_active = True
        self._mw.sidebar.top_btn.set_active(True)
        self._mw.settings.top_mode = True
        self._mw.settings.favorites_mode = False

        if self._mw.playlist.get_track_count() > 0:
            self._mw._play_track_at_view_index(0)
        else:
            self._mw.controls_widget.set_current_track_favorite("", False)

        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style("color: #AAAAAA; font-size: 11px;")
        self._mw.title_bar.set_scanning_status(f"{self._mw.playlist.get_track_count()}", True)

    def load_artist(self, artist_name: str):
        self._mw.title_bar.set_playlist_title(artist_name)
        self._mw.title_bar.set_show_separator(True)
        self._mw.title_bar.set_scanning_status_style("color: #888888; font-size: 11px;")
        self._mw.title_bar.set_scanning_status("Загрузка...", True)
        self._mw._blink_animation.start()

        tracks = get_tracks_by_artist(artist_name)
        if not tracks:
            self._mw._blink_animation.stop()
            return

        self._mw.playlist.clear()
        self._mw.playlist.set_tracks(tracks)
        self._mw.playlist_widget.load_tracks(tracks)

        self._reset_sidebar_state()
        self._mw.settings.playlist_type = "Playlist"

        track_count = self._mw.playlist.get_track_count()
        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style("color: #AAAAAA; font-size: 11px;")

        QTimer.singleShot(200, self._bring_to_front)
        self._mw.title_bar.set_scanning_status(f"{track_count}", True)

        if track_count > 0:
            self._mw.settings.playlist_type = "Playlist"
            self._mw._play_track_at_view_index(0)

    def load_similar_tracks(self):
        current_fp = self._mw._current_playing_filepath
        current_track = None
        if current_fp:
            for t in self._mw.playlist_widget.get_view_tracks():
                if t.filepath == current_fp:
                    current_track = t
                    break
        if not current_track:
            QMessageBox.information(self._mw, "Поиск похожих треков",
                                   "Нет текущего воспроизводимого трека для поиска похожих.")
            return

        from musicplayer.core.db import increment_play_count
        increment_play_count(current_track.filepath)

        self._mw.title_bar.set_scanning_status("Поиск похожих...", True)
        title_suffix = current_track.title[:150] + "..." if len(current_track.title) > 150 else current_track.title
        self._mw.title_bar.set_playlist_title(f"Похожие треки ({title_suffix})")
        self._mw.title_bar.set_show_separator(True)
        self._mw.sidebar.set_all_buttons_enabled(False, include_folder=False)

        all_tracks = get_all_library_tracks_light()
        search_pool = [t for t in all_tracks
                      if t.filepath != current_track.filepath
                      and t.tempo is not None
                      and t.energy is not None
                      and t.mood is not None]

        if not search_pool:
            QMessageBox.information(self._mw, "Поиск похожих треков",
                                   "Недостаточно треков в библиотеке с данными для анализа.")
            self._mw.title_bar.hide_scanning_status()
            self._mw.sidebar.set_all_buttons_enabled(True)
            return

        similar_tracks = find_similar_tracks(current_track, search_pool, limit=100)

        if not similar_tracks:
            QMessageBox.information(self._mw, "Поиск похожих треков",
                                   "Не удалось найти похожие треки.")
            self._mw.title_bar.hide_scanning_status()
            self._mw.sidebar.set_all_buttons_enabled(True)
            return

        self._mw.playlist.clear()
        self._mw.playlist.set_tracks(similar_tracks)
        self._mw.playlist_widget.load_tracks(similar_tracks)

        self._reset_sidebar_state()
        self._mw.settings.playlist_type = "Similar"

        self._mw.title_bar.set_scanning_status(f"{len(similar_tracks)}", True)
        self._mw.sidebar.set_all_buttons_enabled(True)

        if self._mw.playlist.get_track_count() > 0:
            if current_track in similar_tracks:
                try:
                    current_idx = next(i for i, t in enumerate(similar_tracks) if t.filepath == current_track.filepath)
                    self._mw._play_track_at_view_index(current_idx)
                except StopIteration:
                    self._mw._play_track_at_view_index(0)
            else:
                self._mw._play_track_at_view_index(0)

        self._mw._web_integration.update_state()

    def on_control_favorite_toggled(self):
        if self._mw._current_playing_filepath:
            new_state = db_toggle_favorite(self._mw._current_playing_filepath)
            self._mw.controls_widget.set_current_track_favorite(self._mw._current_playing_filepath, new_state)
            self._mw.playlist_widget.list_widget.viewport().update()
            self._mw._web_integration.update_favorites()

    def _reset_sidebar_state(self):
        if self._mw.sidebar._favorites_active:
            self._mw.sidebar._favorites_active = False
            self._mw.sidebar.favorites_btn.set_active(False)
            self._mw.settings.favorites_mode = False
        if self._mw.sidebar._top_active:
            self._mw.sidebar._top_active = False
            self._mw.sidebar.top_btn.set_active(False)
            self._mw.settings.top_mode = False

    def _bring_to_front(self):
        """Bring window to front and give it focus."""
        from PySide6.QtWidgets import QApplication
        import ctypes
        from PySide6.QtCore import Qt

        hwnd = int(self._mw.windowHandle().winId())
        if not hwnd:
            return

        self._mw.showNormal()
        self._mw.setWindowState(self._mw.windowState() & ~Qt.WindowMinimized)
        self._mw.raise_()
        QApplication.processEvents()

        def do_bring():
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.AllowSetForegroundWindow(kernel32.GetCurrentProcessId())
                fgwnd = user32.GetForegroundWindow()
                if fgwnd:
                    fg_tid = user32.GetWindowThreadProcessId(fgwnd, None)
                    our_tid = user32.GetWindowThreadProcessId(hwnd, None)
                    user32.AttachThreadInput(our_tid, fg_tid, True)
                    user32.ShowWindow(hwnd, 9)
                    user32.BringWindowToTop(hwnd)
                    user32.AttachThreadInput(our_tid, fg_tid, False)
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        QTimer.singleShot(100, do_bring)
        QTimer.singleShot(300, do_bring)
        QTimer.singleShot(600, do_bring)