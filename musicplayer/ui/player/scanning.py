"""
Scanning logic: folder scanning, progress, callbacks.
"""

from musicplayer import config as cfg
from musicplayer.core.db import upsert_folder
from musicplayer.core.settings import get_playlist_sort_mode
from musicplayer.utils.audio_scanner import AudioScanner
from musicplayer.ui.player.managers import PlayerManagerBase


class ScanningManager(PlayerManagerBase):
    """Manages folder scanning and tracking scan progress."""

    def __init__(self, main_window):
        self._mw = main_window
        self._scanner = None
        self._removed_count = 0

    def scan(self, folder_path: str):
        self._mw._current_folder_path = folder_path
        if self._scanner:
            if self._scanner.isRunning():
                self._scanner.cancel()
            try:
                self._scanner.scanning_started.disconnect()
                self._scanner.track_scanned.disconnect()
                self._scanner.scanning_progress.disconnect()
                self._scanner.tracks_removed.disconnect()
                self._scanner.scanning_finished.disconnect()
                self._scanner.scanning_error.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._scanner.deleteLater()
        self._scanner = AudioScanner(folder_path, use_cache=True)
        self._removed_count = 0
        self._scanner.scanning_started.connect(self._on_started)
        self._scanner.track_scanned.connect(self._on_track_scanned)
        self._scanner.scanning_progress.connect(self._on_progress)
        self._scanner.tracks_removed.connect(self._on_tracks_removed)
        self._scanner.scanning_finished.connect(self._on_finished)
        self._scanner.scanning_error.connect(self._on_error)
        self._scanner.start()

    def cancel(self):
        if self._scanner and self._scanner.isRunning():
            self._scanner.cancel()

    def _on_started(self):
        self._mw.playlist.clear()
        try:
            self._mw.playlist.begin_bulk_add()
        except Exception as e:
            print(f"scanning._on_started: begin_bulk_add failed: {e}")
        self._mw.playlist_widget.clear()
        self._mw.playlist_widget._view_tracks = self._mw.playlist_widget._full_tracks
        self._mw.playlist_widget.delegate.tracks_ref = self._mw.playlist_widget._view_tracks
        self._mw.sidebar.set_all_buttons_enabled(False)
        self._mw.controls_widget.set_action_buttons_enabled(False)
        self._mw.title_bar.set_sort_enabled(False)

    def _on_track_scanned(self, track):
        self._mw.playlist.add_tracks([track])
        self._mw.playlist_widget.add_track(track)

    def _on_progress(self, current: int, total: int):
        self._mw.title_bar.set_scanning_status(f"Сканирование: {current}/{total}")

    def _on_tracks_removed(self, count: int):
        self._removed_count += count

    def _on_finished(self, tracks: list):
        from PySide6.QtCore import QTimer

        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 11px;")

        removed = self._removed_count
        track_count = len(tracks)
        status = f"Загружено: {track_count} треков"
        if removed > 0:
            status += f". Не найдено: {removed}"
        self._mw.title_bar.set_scanning_status(status)

        if self._mw._current_folder_path:
            upsert_folder(self._mw._current_folder_path, track_count)

        def _delayed_show_count():
            try:
                self._mw.title_bar.set_scanning_status(f"{track_count}", True)
            except RuntimeError:
                pass
        QTimer.singleShot(3000, _delayed_show_count)
        self._mw.sidebar.set_all_buttons_enabled(True)
        self._mw.controls_widget.set_action_buttons_enabled(True)
        self._mw.title_bar.set_sort_enabled(True)

        self._reset_sidebar_state()

        if self._mw.playlist.get_track_count() == 0 and tracks:
            try:
                self._mw.playlist.begin_bulk_add()
            except Exception as e:
                print(f"scanning._on_finished: begin_bulk_add failed: {e}")
            self._mw.playlist.load_tracks_no_sort(tracks)
            self._mw.playlist_widget.load_tracks(tracks)
            try:
                self._mw.playlist.end_bulk_add()
            except Exception as e:
                print(f"scanning._on_finished: end_bulk_add (inner) failed: {e}")

        try:
            self._mw.playlist.end_bulk_add()
        except Exception as e:
            print(f"scanning._on_finished: end_bulk_add (outer) failed: {e}")

        sort_mode = get_playlist_sort_mode()
        self._mw.playlist.set_sort_mode(sort_mode)
        self._mw.playlist_widget.load_tracks(self._mw.playlist.get_tracks())
        if hasattr(self._mw, "title_bar"):
            self._mw.title_bar.sort_combo.blockSignals(True)
            index_map = {"artist": 0, "title": 1, "newest": 2, "shuffle": 3}
            self._mw.title_bar.sort_combo.setCurrentIndex(index_map.get(sort_mode, 0))
            self._mw.title_bar.sort_combo.blockSignals(False)

        last_fp = self._mw.settings.last_track
        restored = False
        if last_fp:
            for i, t in enumerate(self._mw.playlist_widget.get_view_tracks()):
                if t.filepath == last_fp:
                    self._mw._play_track_at_view_index(i)
                    restored = True
                    break
        if not restored and self._mw.playlist.get_track_count() > 0:
            self._mw._play_track_at_view_index(0)

        self._mw._update_playlist_title()
        self._mw.ipc_server.send_refresh()

        def _delayed_analysis():
            try:
                self._mw.analysis_manager.start_analysis(self._mw.playlist.get_tracks())
            except RuntimeError:
                pass
        QTimer.singleShot(100, _delayed_analysis)

    def _on_error(self, error_msg: str):
        self._mw._blink_animation.stop()
        self._mw.title_bar.hide_scanning_status()
        self._mw.sidebar.set_all_buttons_enabled(True)
        self._mw.controls_widget.set_action_buttons_enabled(True)
        self._mw.title_bar.set_sort_enabled(True)
        from musicplayer.ui.widgets.styled_message_box import StyledMessageBox
        StyledMessageBox.critical(self._mw, "Scan Error", key=error_msg)