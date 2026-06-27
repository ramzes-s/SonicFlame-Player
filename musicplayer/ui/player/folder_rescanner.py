"""
Folder rescanner — scans a list of folders in background, one by one,
using AudioScanner. Zero UI side-effects — only DB operations.
Signals let the UI react if needed.
"""

import time
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer

from musicplayer.utils.audio_scanner import AudioScanner
from musicplayer.core.db.folders import upsert_folder
from musicplayer.core.db.broken_tracks import (
    delete_broken_tracks_in_subtree,
    add_broken_track,
)


class FolderRescanner(QObject):
    progress = Signal(int, int)
    folder_scanned = Signal(str, int)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folders = []
        self._index = 0
        self._scanner = None

    def scan(self, folders: list[str]):
        self._folders = list(folders)
        self._index = 0
        self._scan_next()

    def cancel(self):
        if self._scanner and self._scanner.isRunning():
            self._scanner.cancel()
        self._folders = []
        self._index = 0

    def _scan_next(self):
        if self._index >= len(self._folders):
            self.finished.emit()
            return

        folder = self._folders[self._index]
        self.progress.emit(self._index + 1, len(self._folders))

        self._scanner = AudioScanner(folder, use_cache=True)
        self._scanner.scanning_finished.connect(self._on_folder_done)
        self._scanner.start()

    def _on_folder_done(self, tracks):
        self._scanner.scanning_finished.disconnect()

        folder = self._folders[self._index]
        track_count = len(tracks)
        upsert_folder(folder, track_count, last_scanned=time.time())

        # Save broken files to DB for accurate diff on next startup.
        # Use the file's actual parent directory so get_broken_counts_for_all_folders
        # can assign it to the correct folder level.
        delete_broken_tracks_in_subtree(folder)
        for filepath, error in self._scanner.broken_files:
            parent_folder = str(Path(filepath).parent)
            add_broken_track(filepath, parent_folder, error)

        broken_count = len(self._scanner.broken_files)
        print(f"[rescanner] {folder} — {track_count} треков, {broken_count} битых")
        self.folder_scanned.emit(folder, track_count)

        self._index += 1
        QTimer.singleShot(0, self._scan_next)
