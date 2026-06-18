"""
Playback and navigation logic.
"""

import logging
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QDialog
from musicplayer.ui.widgets.styled_message_box import StyledMessageBox
from musicplayer import config as cfg

from musicplayer.core.db import (
    ensure_cover_for_track,
    increment_play_count,
    get_track,
    upsert_track,
    delete_track,
    extract_metadata,
    is_favorite as db_is_favorite,
)
from musicplayer.ui.remove_track_dialog import show_missing_track_dialog, remove_track_from_library
from musicplayer.utils.audio_scanner import AudioScanner
from musicplayer.ui.player.managers import PlayerManagerBase

logger = logging.getLogger(__name__)


class PlaybackManager(PlayerManagerBase):
    """Manages track playback, navigation, and tag editing."""

    def __init__(self, main_window):
        self._mw = main_window

    def play_track_at_view_index(self, view_index: int):
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        if not (0 <= view_index < len(view_tracks)):
            return

        track = view_tracks[view_index]
        if not os.path.exists(track.filepath):
            result = show_missing_track_dialog(track.title, track.artist, track.filepath, self._mw)
            if result == 1:
                def _delayed_missing(fp=track.filepath):
                    try:
                        self._handle_missing_track(fp)
                    except RuntimeError:
                        pass
                QTimer.singleShot(0, _delayed_missing)
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
            # Re-update SMTC with the cover now available
            self._mw.player._smtc.update_track_info(track)

        self._apply_dynamic_color(track)
        self._mw.track_info_widget.update_track_info(track)
        self._mw.playlist_widget.set_current_track_by_filepath(track.filepath)
        self._mw.playlist_widget.set_playing_track(track.filepath)
        self._mw.controls_widget.set_current_track_favorite(track.filepath, track.is_favorite)
        self._update_mini_track(track)
        self._mw.player.play()
        self._mw.controls_widget.set_play_state(True)
        self._mw.settings.batch_save()

        def _delayed_sync():
            try:
                self._mw._web_integration.update_state()
            except RuntimeError:
                pass
        QTimer.singleShot(100, _delayed_sync)

    def _update_mini_track(self, track):
        if self._mw._mini_widget and self._mw._mini_widget.isVisible():
            self._mw._mini_widget.set_track_info(track.artist, track.title)

    def _apply_dynamic_color(self, track):
        if not self._mw.settings.dynamic_color:
            return
        from musicplayer.ui.accent_style import apply_accent_to_main_window
        from musicplayer.utils.color_extractor import extract_accent_color

        new_color = extract_accent_color(track.cover_data) if track.cover_data else "#ed6a02"
        cfg.ACCENT_COLOR = new_color
        self._mw.settings._data["accent_color"] = new_color
        apply_accent_to_main_window(self._mw, settings_dialog=getattr(self._mw, '_settings_dialog', None))
        if hasattr(self._mw.playlist_widget, 'list_widget'):
            self._mw.playlist_widget.list_widget.viewport().update()
        self._mw.ipc_server.send_accent_color(new_color)

    def play_track_from_db(self, track):
        if not os.path.exists(track.filepath):
            result = show_missing_track_dialog(track.title, track.artist, track.filepath, self._mw)
            if result == 1:
                def _delayed_missing(fp=track.filepath):
                    try:
                        self._handle_missing_track(fp)
                    except RuntimeError:
                        pass
                QTimer.singleShot(0, _delayed_missing)
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
        self._mw.controls_widget.set_current_track_favorite(track.filepath, track.is_favorite)
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

        self._reset_sidebar_state()
        self._mw.title_bar.set_playlist_title(os.path.basename(folder_path))
        self._mw.title_bar.set_show_separator(True)
        self._mw.title_bar.set_scanning_status_style(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 11px;")
        self._mw.title_bar.set_scanning_status("Загрузка...", True)
        self._mw._blink_animation.start()

        old_scanner = self._mw.scanner
        if old_scanner:
            try:
                old_scanner.scanning_finished.disconnect()
                old_scanner.scanning_error.disconnect()
            except (TypeError, RuntimeError):
                pass
            if old_scanner.isRunning():
                old_scanner.cancel()
            old_scanner.deleteLater()

        self._mw.scanner = AudioScanner(folder_path, use_cache=True)
        self._mw._removed_tracks_count = 0
        self._mw.scanner.scanning_finished.connect(lambda tracks: self._on_scan_finished_and_play(tracks, target_filepath))
        self._mw.scanner.scanning_error.connect(self._on_scan_error)
        self._mw.scanner.start()

    def _on_scan_error(self, error_msg: str):
        self._mw._blink_animation.stop()
        self._mw.title_bar.hide_scanning_status()
        self._mw.sidebar.set_all_buttons_enabled(True)
        self._mw.controls_widget.set_action_buttons_enabled(True)
        self._mw.title_bar.set_sort_enabled(True)
        StyledMessageBox.critical(self._mw, "Scan Error", key=error_msg)

    def _on_scan_finished_and_play(self, tracks: list, target_filepath: str):
        self._mw._blink_animation.stop()
        self._mw.title_bar.set_scanning_status_style(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 11px;")

        removed = self._mw._removed_tracks_count
        status = f"Загружено: {len(tracks)} треков"
        if removed > 0:
            status += f". Не найдено: {removed}"
        self._mw.title_bar.set_scanning_status(status)
        def _delayed_show_count(tc=len(tracks)):
            try:
                self._mw.title_bar.set_scanning_status(f"{tc}", True)
            except RuntimeError:
                pass
        QTimer.singleShot(3000, _delayed_show_count)
        self._mw.sidebar.set_all_buttons_enabled(True)
        self._mw.controls_widget.set_action_buttons_enabled(True)
        self._mw.title_bar.set_sort_enabled(True)

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
            track.is_favorite = new_state
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
        logger.info("Tag editor opened for: %s (was_playing=%s, pos=%d)", old_filepath, was_playing, position)

        if was_playing:
            self._mw.player.stop()
            self._mw.player.player.setSource(QUrl())

        dialog = TagEditorDialog(track.filepath, self._mw, update_player=True)
        dialog.exec()

        delete_confirmed = dialog.delete_confirmed
        save_confirmed = dialog.save_confirmed
        new_filepath = dialog.file_path

        # Destroy dialog explicitly before any UI updates to avoid Qt re-entrancy
        dialog.deleteLater()
        del dialog

        if delete_confirmed:
            logger.info("Track delete confirmed: %s", old_filepath)
            remove_track_from_library(old_filepath, self._mw.playlist_widget, self._mw.playlist, self._mw)
            try:
                os.remove(old_filepath)
                logger.info("File deleted from disk: %s", old_filepath)
            except OSError as e:
                logger.error("Failed to delete file from disk: %s", e, exc_info=True)
                StyledMessageBox.critical(self._mw, "Ошибка удаления файла", key=f"Не удалось удалить файл: {e}")
            return

        if save_confirmed:
            logger.info("Save confirmed — old=%s, new=%s", old_filepath, new_filepath)
            was_favorite = False
            old_analysis = {}
            if os.path.normpath(new_filepath) != os.path.normpath(old_filepath):
                logger.info("File was renamed, deleting old track from DB: %s", old_filepath)
                old_track = get_track(old_filepath)
                if old_track:
                    was_favorite = old_track.is_favorite
                    old_analysis = {
                        'tempo': old_track.tempo,
                        'energy': old_track.energy,
                        'mood': old_track.mood,
                        'zero_crossing_rate': old_track.zero_crossing_rate,
                        'spectral_flux': old_track.spectral_flux,
                        'hpss_ratio': old_track.hpss_ratio,
                        'play_count': old_track.play_count,
                    }
                delete_track(old_filepath)
            logger.info("Extracting metadata from: %s", new_filepath)
            updated_track = extract_metadata(new_filepath)
            if updated_track:
                updated_track.is_favorite = was_favorite
                for key, val in old_analysis.items():
                    setattr(updated_track, key, val)
                try:
                    upsert_track(updated_track, os.path.getmtime(new_filepath), preserve_play_count=False)
                    logger.info("Upsert OK for: %s", new_filepath)
                except Exception as e:
                    logger.error("UPSERT CRASHED: %s", e, exc_info=True)
                try:
                    full_track = get_track(new_filepath) or updated_track
                    logger.info("get_track returned: %s", full_track)
                except Exception as e:
                    logger.error("GET_TRACK CRASHED: %s", e, exc_info=True)
                    full_track = updated_track
                # Defer UI updates to next event loop cycle to let Qt settle after dialog close
                def _delayed_tag_edit(fp=old_filepath, nfp=new_filepath, ft=full_track, wp=was_playing, pos=position):
                    try:
                        self._finish_tag_edit(fp, nfp, ft, wp, pos)
                    except RuntimeError:
                        pass
                QTimer.singleShot(0, _delayed_tag_edit)
            else:
                logger.error("extract_metadata returned None for: %s", new_filepath)
        else:
            logger.info("Save cancelled — resuming playback")
            if was_playing:
                def _delayed_resume(fp=old_filepath, pos=position):
                    try:
                        self._resume_after_cancel(fp, pos)
                    except RuntimeError:
                        pass
                QTimer.singleShot(100, _delayed_resume)

    def _finish_tag_edit(self, old_filepath, new_filepath, full_track, was_playing, position):
        """Post-save UI updates (deferred to avoid Qt re-entrancy crash)."""
        try:
            self._mw.playlist_widget.update_track_data(old_filepath, full_track)
            logger.info("update_track_data OK")
        except Exception as e:
            logger.error("UPDATE_TRACK_DATA CRASHED: %s", e, exc_info=True)
        if self._mw._current_playing_filepath == old_filepath:
            self._mw._current_playing_filepath = new_filepath
            logger.info("Updated _current_playing_filepath to: %s", new_filepath)
        if self._mw._current_playing_filepath:
            try:
                self._mw.playlist_widget.set_playing_track(self._mw._current_playing_filepath)
            except Exception as e:
                logger.error("SET_PLAYING_TRACK CRASHED: %s", e, exc_info=True)
        if was_playing and full_track:
            self._mw.track_info_widget.update_track_info(full_track)
            try:
                logger.info("Reloading player source for resume at pos=%d", position)
                self._mw.player.load_source(full_track)
            except Exception as e:
                logger.error("Failed to load source after tag edit: %s", e, exc_info=True)
            def _delayed_resume(pos=position):
                try:
                    self._resume_after_tag_edit(pos)
                except RuntimeError:
                    pass
            QTimer.singleShot(100, _delayed_resume)

    def _resume_after_cancel(self, old_filepath, position):
        """Resume playback after cancel (deferred)."""
        view_tracks = self._mw.playlist_widget.get_view_tracks()
        old_track = next((t for t in view_tracks if t.filepath == old_filepath), None)
        if old_track:
            self._mw.player.load_source(old_track)
        def _delayed_resume(pos=position):
            try:
                self._resume_after_tag_edit(pos)
            except RuntimeError:
                pass
        QTimer.singleShot(100, _delayed_resume)

    def _resume_after_tag_edit(self, position: int):
        if self._mw.player.player.source().isEmpty():
            logger.warning("Player source is empty, skipping resume")
            return
        self._mw.player.player.setPosition(position)
        self._mw.player.play()

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