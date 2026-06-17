"""
Audio Scanner Module

QThread-based folder scanning with smart sync:
- Compares file mtime with DB to detect changes
- Adds new files, updates changed files, removes deleted files
- All metadata stored in SQLite database
"""

import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from musicplayer.core.db import (
    init_db,
    upsert_track,
    delete_track,
    get_tracks_by_folder,
    delete_folder_tracks,
    get_folder_filepaths,
    get_track_mtime,
    extract_metadata,
    TrackInfo,
)


# Supported audio file extensions
SUPPORTED_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4'}


class AudioScanner(QThread):
    """
    Background thread for scanning audio files in a folder.

    Scans folder, compares with DB, syncs:
    - New files → extract metadata, add to DB
    - Modified files (mtime changed) → re-extract, update DB
    - Deleted files → remove from DB
    - Unchanged files → use cached data from DB

    Signals:
        scanning_started: Emitted when scan begins
        track_scanned: Emitted for each track found/updated (TrackInfo)
        scanning_progress: Emitted for each file scanned (current, total)
        scanning_finished: Emitted with list of TrackInfo objects
        scanning_error: Emitted if an error occurs
    """

    scanning_started = Signal(str)  # folder_path
    track_scanned = Signal(object)  # TrackInfo - emitted per track
    scanning_progress = Signal(int, int)  # current, total
    scanning_finished = Signal(list)  # List[TrackInfo]
    tracks_removed = Signal(int)  # Number of missing tracks removed from DB
    scanning_error = Signal(str)  # error message

    def __init__(self, folder_path: str, use_cache: bool = True):
        super().__init__()
        self.folder_path = folder_path
        self.use_cache = use_cache
        self._is_cancelled = False

        # Ensure DB is initialized
        init_db()

    def _process_file(self, filepath: Path) -> TrackInfo | None:
        """Processes a single audio file."""
        if self._is_cancelled:
            return None

        fp_str = str(filepath)
        track_info = None

        try:
            # Check if file needs update
            current_mtime = filepath.stat().st_mtime
            db_mtime = get_track_mtime(fp_str)

            if db_mtime is not None and current_mtime <= db_mtime:
                # File unchanged — use cached data from DB
                from musicplayer.core.db import get_track
                track_info = get_track(fp_str)

                # Verify cover file exists if DB says track has cover
                if track_info and track_info.has_cover and not track_info.cover_data:
                    # Cover file missing — re-extract metadata
                    track_info = None

            if track_info is None:
                # New or modified file — extract metadata
                track_info = extract_metadata(fp_str)
                if track_info:
                    upsert_track(track_info, current_mtime)
            
            return track_info
        except Exception:
            # Errors in a single file should not stop the whole scan
            return None

    def run(self):
        """Execute the folder scanning process."""
        try:
            self.scanning_started.emit(self.folder_path)

            folder = Path(self.folder_path)
            if not folder.exists() or not folder.is_dir():
                self.scanning_error.emit(f"Папка не найдена: {self.folder_path}")
                return

            # Collect all supported audio files
            audio_files = sorted(list(
                {f for ext in SUPPORTED_EXTENSIONS for f in folder.glob(f"**/*{ext}")} |
                {f for ext in SUPPORTED_EXTENSIONS for f in folder.glob(f"**/*{ext.upper()}")}
            ))

            if self._is_cancelled:
                return

            # Get existing filepaths from DB for this folder
            db_filepaths = get_folder_filepaths(self.folder_path)
            current_filepaths = {str(f) for f in audio_files}

            # Files to remove: in DB but not on disk
            to_remove = db_filepaths - current_filepaths
            removed_count = len(to_remove)
            if removed_count > 0:
                for fp in to_remove:
                    if self._is_cancelled:
                        return
                    delete_track(fp)
                self.tracks_removed.emit(removed_count)

            if not audio_files:
                self.scanning_finished.emit([])
                return

            total = len(audio_files)
            tracks = []
            
            for i, filepath in enumerate(audio_files):
                if self._is_cancelled:
                    break

                track_info = self._process_file(filepath)
                if track_info:
                    tracks.append(track_info)
                    self.track_scanned.emit(track_info)

                self.scanning_progress.emit(i + 1, total)

            if not self._is_cancelled:
                self.scanning_finished.emit(tracks)

        except Exception as e:
            if not self._is_cancelled:
                self.scanning_error.emit(f"Ошибка сканирования: {str(e)}")

    def cancel(self):
        """Cancel the scanning operation."""
        self._is_cancelled = True
        self.wait()
