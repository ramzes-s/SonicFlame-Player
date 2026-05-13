"""
Playback and navigation logic.
"""

import os

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMessageBox, QDialog

from musicplayer.core.db import (
    ensure_cover_for_track,
    is_favorite as db_is_favorite,
    increment_play_count,
    get_track,
    upsert_track,
    delete_track,
    extract_metadata,
)
from musicplayer.ui.remove_track_dialog import MissingTrackDialog, remove_track_from_library
from musicplayer.utils.audio_scanner import AudioScanner


class PlaybackManager:
    """Manages track playback, navigation, and tag editing."""

    def __init__(self, main_window):
        self._mw = main_window

    def play_track_at_view_index(self, view_index: int):
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if not (0 <= view_index < len(view_tracks)):
            return

        track = view_tracks[view_index]
        if not os.path.exists(track.filepath):
            dialog = MissingTrackDialog(track.title, track.artist, track.filepath, self._mw)
            if dialog.exec() == QMessageBox.Yes:
                QTimer.singleShot(0, lambda fp=track.filepath: self._handle_missing_track(fp))
            return

        if self._mw._current_playing_filepath == track.filepath and self._mw.player.get_state() == QMediaPlayer.PlayingState:
            return

        self._mw.playlist.play_track_at(view_index)
        self._mw._current_playing_filepath = track.filepath
        self._mw.settings._data["last_track"] = track.filepath
        self._mw.settings._data["last_folder"] = str(os.path.dirname(track.filepath))

        if self._mw.settings.favorites_mode:
            self._mw.settings.playlist_type = "Favorites"
        elif self._mw.settings.top_mode:
            self._mw.settings.playlist_type = "Top"
        elif self._mw.settings.playlist_type not in ("Folder", "Favorites", "Top"):
            self._mw.settings.playlist_type = "Playlist"

        self._mw.player.load_source(track)

        if not track.has_cover or not track.cover_data:
            track.cover_data = ensure_cover_for_track(track.filepath)
            track.has_cover = bool(track.cover_data)

        self._apply_dynamic_color(track)
        self._mw.track_info_widget.update_track_info(track)
        self._mw.playlist_widget.set_current_track_by_filepath(track.filepath)
        self._mw.playlist_widget.set_playing_track(track.filepath)
        self._mw.controls_widget.set_current_track_favorite(track.filepath, db_is_favorite(track.filepath))
        self._update_mini_track(track)
        self._mw.player.play()
        self._mw.controls_widget.set_play_state(True)
        self._mw.settings.batch_save()

        QTimer.singleShot(100, self._mw._web_integration.update_state)

    def _update_mini_track(self, track):
        if self._mw._mini_widget and self._mw._mini_widget.isVisible():
            self._mw._mini_widget.set_track_info(track.artist, track.title)

    def _apply_dynamic_color(self, track):
        if not self._mw.settings.dynamic_color:
            return
        from musicplayer.ui.accent_style import apply_accent_to_main_window
        from musicplayer.utils.color_extractor import extract_accent_color

        new_color = extract_accent_color(track.cover_data) if track.cover_data else "#ed6a02"
        from musicplayer import config as cfg
        cfg.ACCENT_COLOR = new_color
        self._mw.settings._data["accent_color"] = new_color
        apply_accent_to_main_window(self._mw)
        if hasattr(self._mw.playlist_widget, 'list_widget'):
            self._mw.playlist_widget.list_widget.viewport().update()
        self._mw.ipc_server.send_accent_color(new_color)

    def play_track_from_db(self, track):
        if not os.path.exists(track.filepath):
            dialog = MissingTrackDialog(track.title, track.artist, track.filepath, self._mw)
            if dialog.exec() == QMessageBox.Yes:
                QTimer.singleShot(0, lambda fp=track.filepath: self._handle_missing_track(fp))
            return

        self._mw._current_playing_filepath = track.filepath
        self._mw.settings.last_track = track.filepath
        self._mw.settings.last_folder = os.path.dirname(track.filepath)
        self._mw.player.load_source(track)

        if not track.has_cover or not track.cover_data:
            track.cover_data = ensure_cover_for_track(track.filepath)
            track.has_cover = bool(track.cover_data)

        self._apply_dynamic_color(track)
        self._mw.track_info_widget.update_track_info(track)
        self._mw.controls_widget.set_current_track_favorite(track.filepath, db_is_favorite(track.filepath))
        self._mw.player.play()
        self._mw.controls_widget.set_play_state(True)

    def play_from_library(self, filepath: str):
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        try:
            idx = next(i for i, t in enumerate(view_tracks) if t.filepath == filepath)
            self.play_track_at_view_index(idx)
            return
        except StopIteration:
            pass

        track = get_track(filepath)
        if track:
            self._bring_to_front()
            if self._mw._current_folder_path == os.path.dirname(filepath):
                self.play_track_from_db(track)
            else:
                self._mw.settings.playlist_type = "Playlist"
                self._mw._scan_folder_and_play(os.path.dirname(filepath), filepath)

    def play_folder_and_track(self, folder_path: str, target_filepath: str):
        self._mw._current_folder_path = folder_path
        self._mw.settings.last_folder = folder_path
        self._mw.playlist.clear()
        self._mw.playlist_widget.clear()
        self._mw.playlist_widget._view_tracks = self._mw.playlist_widget._full_tracks
        self._mw.playlist_widget.delegate.tracks_ref = self._mw.playlist_widget._view_tracks

        if self._mw.sidebar._favorites_active:
            self._mw.sidebar._favorites_active = False
            self._mw.sidebar.favorites_btn.set_active(False)
            self._mw.settings.favorites_mode = False

        self._mw.title_bar.set_playlist_title(os.path.basename(folder_path))
        self._mw.title_bar.set_show_separator(True)
        self._mw.title_bar.set_scanning_status_style("color: #888888; font-size: 11px;")
        self._mw.title_bar.set_scanning_status("Загрузка...", True)
        self._mw._blink_animation.start()

        if self._mw.scanner and self._mw.scanner.isRunning():
            self._mw.scanner.cancel()

        self._mw.scanner = AudioScanner(folder_path, use_cache=True)
        self._mw._removed_tracks_count = 0
        self._mw.scanner.scanning_started.connect(self._on_scan_started)
        self._mw.scanner.track_scanned.connect(self._on_track_scanned)
        self._mw.scanner.scanning_progress.connect(self._on_scan_progress)
        self._mw.scanner.tracks_removed.connect(self._on_tracks_removed)
        self._mw.scanner.scanning_finished.connect(lambda tracks: self._on_scan_finished_and_play(tracks, target_filepath))
        self._mw.scanner.scanning_error.connect(self._on_scan_error)
        self._mw.scanner.start()

    def _on_scan_started(self, folder_path: str):
        pass

    def _on_track_scanned(self, track):
        self._mw.playlist.add_tracks([track])
        self._mw.playlist_widget.add_track(track)

    def _on_scan_progress(self, current: int, total: int):
        self._mw.title_bar.set_scanning_status(f"Сканирование: {current}/{total}")

    def _on_tracks_removed(self, count: int):
        self._mw._removed_tracks_count += count

    def _on_scan_error(self, error_msg: str):
        self._mw._blink_animation.stop()
        self._mw.title_bar.hide_scanning_status()
        self._mw.sidebar.set_all_buttons_enabled(True)
        QMessageBox.warning(self._mw, "Scan Error", error_msg)

    def _on_scan_finished_and_play(self, tracks: list, target_filepath: str):
        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style("color: #AAAAAA; font-size: 11px;")

        removed = self._mw._removed_tracks_count
        status = f"Загружено: {len(tracks)} треков"
        if removed > 0:
            status += f". Не найдено: {removed}"
        self._mw.title_bar.set_scanning_status(status)
        QTimer.singleShot(3000, lambda: (
            self._mw.title_bar.set_scanning_status(f"{len(tracks)}", True)
        ))
        self._mw.sidebar.set_all_buttons_enabled(True)

        if self._mw.playlist.get_track_count() == 0 and tracks:
            self._mw.playlist.set_tracks(tracks)
            self._mw.playlist_widget.load_tracks(self._mw.playlist.get_tracks())

        self._mw._update_playlist_title()
        self._mw.ipc_server.send_refresh()

        try:
            idx = next(i for i, t in enumerate(self._mw.playlist_widget.get_view_tracks()) if t.filepath == target_filepath)
            self.play_track_at_view_index(idx)
        except StopIteration:
            if tracks:
                self.play_track_at_view_index(0)

    def _handle_missing_track(self, filepath: str):
        remove_track_from_library(filepath, self._mw.playlist_widget, self._mw.playlist, self._mw)
        self._mw.playlist_widget._display_tracks()
        self._mw.playlist_widget.list_widget.viewport().update()

    def next(self):
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if not view_tracks:
            return

        current_fp = self._mw._current_playing_filepath
        current_index = -1
        for i, t in enumerate(view_tracks):
            if t.filepath == current_fp:
                current_index = i
                break

        repeat_mode = self._mw.playlist.get_repeat_mode()

        if repeat_mode == "one":
            self._mw.player.set_position(0)
            self._mw.player.play()
            return

        next_index = current_index + 1
        if next_index >= len(view_tracks):
            if repeat_mode == "all":
                next_index = 0
            else:
                self._mw.player.stop()
                return

        self.play_track_at_view_index(next_index)

    def previous(self):
        if self._mw.player.get_position() > 3000:
            self._mw.player.set_position(0)
            return

        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if not view_tracks:
            return

        current_fp = self._mw._current_playing_filepath
        current_index = -1
        for i, t in enumerate(view_tracks):
            if t.filepath == current_fp:
                current_index = i
                break

        prev_index = current_index - 1
        repeat_mode = self._mw.playlist.get_repeat_mode()

        if prev_index < 0:
            if repeat_mode == "all":
                prev_index = len(view_tracks) - 1
            else:
                prev_index = 0

        self.play_track_at_view_index(prev_index)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self._mw._current_playing_filepath:
                increment_play_count(self._mw._current_playing_filepath)
            self.next()

    def on_track_selected(self, index: int):
        self.play_track_at_view_index(index)

    def on_favorite_clicked(self, index: int):
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if 0 <= index < len(view_tracks):
            track = view_tracks[index]
            new_state = self._mw.playlist_widget.favorites.toggle_favorite(track.filepath)
            if self._mw.sidebar._favorites_active:
                self._mw.playlist_widget.show_favorites_only()
            else:
                self._mw.playlist_widget.list_widget.viewport().update()
            if self._mw._current_playing_filepath:
                self._mw.playlist_widget.set_playing_track(self._mw._current_playing_filepath)
            if self._mw._current_playing_filepath == track.filepath:
                self._mw.controls_widget.set_current_track_favorite(track.filepath, new_state)
            self._mw._web_integration.update_favorites()

    def on_badge_clicked(self, index: int):
        from musicplayer.ui.tag_editor import TagEditorDialog
        from PySide6.QtCore import QUrl

        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if not (0 <= index < len(view_tracks)):
            return

        track = view_tracks[index]
        old_filepath = track.filepath
        was_playing = self._mw._current_playing_filepath == old_filepath and self._mw.player.is_playing()
        position = self._mw.player.get_position() if was_playing else 0

        if was_playing:
            self._mw.player.stop()
            self._mw.player.player.setSource(QUrl())

        dialog = TagEditorDialog(track.filepath, self._mw, update_player=True)
        result = dialog.exec()

        if dialog.delete_confirmed:
            remove_track_from_library(old_filepath, self._mw.playlist_widget, self._mw.playlist, self._mw)
            try:
                os.remove(old_filepath)
            except OSError as e:
                QMessageBox.critical(self._mw, "Ошибка удаления файла", f"Не удалось удалить файл:{e}")
            return

        if result == QDialog.DialogCode.Accepted:
            new_filepath = dialog.file_path
            if os.path.exists(new_filepath):
                if os.path.normpath(new_filepath) != os.path.normpath(old_filepath):
                    delete_track(old_filepath)
                updated_track = extract_metadata(new_filepath)
                if updated_track:
                    upsert_track(updated_track, os.path.getmtime(new_filepath))
                    full_track = get_track(new_filepath) or updated_track
                    self._mw.playlist_widget.update_track_data(old_filepath, full_track)
                    if self._mw._current_playing_filepath == old_filepath:
                        self._mw._current_playing_filepath = new_filepath
                    if self._mw._current_playing_filepath:
                        self._mw.playlist_widget.set_playing_track(self._mw._current_playing_filepath)
                    if was_playing:
                        self._mw.track_info_widget.update_track_info(full_track)
                        self._mw.player.load_source(full_track)
                        QTimer.singleShot(100, lambda pos=position: self._resume_after_tag_edit(pos))
        else:
            if was_playing:
                old_track = next((t for t in view_tracks if t.filepath == old_filepath), None)
                if old_track:
                    self._mw.player.load_source(old_track)
                QTimer.singleShot(100, lambda pos=position: self._resume_after_tag_edit(pos))

    def _resume_after_tag_edit(self, position: int):
        self._mw.player.player.setPosition(position)
        self._mw.player.play()

    def _bring_to_front(self):
        """Bring window to front and give it focus."""
        from PySide6.QtWidgets import QApplication
        import ctypes

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

    def on_dynamic_color_toggled(self, enabled: bool):
        if not enabled:
            return
        current_filepath = self._mw._current_playing_filepath
        if current_filepath:
            try:
                track = next(t for t in self._mw.playlist_widget.get_view_tracks() if t.filepath == current_filepath)
                self._apply_dynamic_color(track)
            except StopIteration:
                pass