"""
Dialogs Module

Common dialog classes for the music player.
"""

from pathlib import Path
from PySide6.QtWidgets import QMessageBox


class MissingTrackDialog(QMessageBox):
    """
    Dialog shown when a track file is missing.
    Asks user whether to remove the track from the library.
    """

    def __init__(self, track_title: str, track_artist: str, filepath: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Трек не найден")
        self.setIcon(QMessageBox.Warning)

        file_name = Path(filepath).name
        self.setText(
            f"<b>Файл не найден:</b><br><br>"
            f"<i>{track_title}</i> — {track_artist}<br>"
            f"<span style='color: #888888; font-size: 11px;'>{file_name}</span><br><br>"
            f"Удалить запись из библиотеки?"
        )

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

    delete_track(filepath)

    if playlist_widget:
        original_full = playlist_widget._full_tracks
        playlist_widget._full_tracks = [
            t for t in original_full if t.filepath != filepath
        ]

        if playlist_widget._view_tracks is original_full:
            playlist_widget._view_tracks = playlist_widget._full_tracks
        else:
            playlist_widget._view_tracks = [
                t for t in playlist_widget._view_tracks if t.filepath != filepath
            ]

        playlist_widget.delegate.tracks_ref = playlist_widget._view_tracks

        playlist_widget.list_widget.clear()
        for i, track in enumerate(playlist_widget._view_tracks):
            from musicplayer.ui.playlist_view import PlaylistItem
            item = PlaylistItem(track, i)
            playlist_widget.list_widget.addItem(item)
        playlist_widget._current_index = -1

        playlist_widget.list_widget.viewport().update()

    if playlist:
        full_tracks = playlist.get_tracks()
        updated_tracks = [t for t in full_tracks if t.filepath != filepath]
        playlist.set_tracks(updated_tracks)

        current_track = playlist.get_current_track()
        if current_track and current_track.filepath == filepath:
            if len(updated_tracks) > 0:
                playlist.play_track_at(0)
            else:
                playlist._current_index = -1

    if main_window:
        if main_window._current_playing_filepath == filepath:
            main_window._current_playing_filepath = None
            main_window.controls_widget.set_current_track_favorite("", False)
            main_window.player.stop()

    return True