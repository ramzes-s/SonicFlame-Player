"""
Folder sync — background sync of the folders table at startup.
Queries all parent folders from library and upserts them into the folders table.
After sync, automatically detects folders where track count on disk differs from DB.
"""

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from musicplayer.core.db.folders import upsert_folder, delete_folder
from musicplayer.core.db.queries import get_all_folders
from musicplayer.core.db.tracks import delete_track
from musicplayer.core.db.broken_tracks import get_broken_counts_for_all_folders, delete_broken_tracks_in_subtree
from musicplayer.core.db.connection import get_connection

SUPPORTED_EXTS = ('.mp3', '.flac', '.m4a', '.mp4')


class FolderSyncWorker(QThread):
    finished = Signal()
    dirty_folders = Signal(list)

    def run(self):
        # Collect all folders from library (computed from filepaths)
        folders = list(get_all_folders())

        # Step 1: purge folders no longer on disk — delete tracks first, then folder
        missing = [(fp, cnt) for fp, cnt in folders if not os.path.isdir(fp)]
        if missing:
            print(f"[folder_sync] Папок нет на диске ({len(missing)}):")
            for fp, _ in missing:
                # Delete tracks via Python filter — reliable, no SQL LIKE pitfalls
                prefix = fp.rstrip(os.sep) + os.sep
                with get_connection() as conn:
                    cursor = conn.execute("SELECT filepath FROM library")
                    for (filepath,) in cursor.fetchall():
                        if filepath.startswith(prefix):
                            print(f"  [folder_sync] Удаление трека: {filepath}")
                            delete_track(filepath)
                # Clean up broken tracks for this subtree
                delete_broken_tracks_in_subtree(fp)

        # Step 2: sync remaining folders into the folders table
        for folder_path, cnt in folders:
            if os.path.isdir(folder_path) or cnt == 0:
                upsert_folder(folder_path, cnt)
            else:
                # Folder gone + tracks already deleted above — remove from folders
                delete_folder(folder_path)
                print(f"  [folder_sync] Удалена папка с диска: {folder_path}")

        # Step 3: get known broken file counts per folder
        broken_counts = get_broken_counts_for_all_folders()

        # Step 4: detect dirty folders among remaining (existing) folders
        dirty = []
        for folder_path, db_count in folders:
            if not os.path.isdir(folder_path):
                continue
            try:
                disk_count = sum(
                    1 for _ in Path(folder_path).glob("**/*")
                    if _.suffix.lower() in SUPPORTED_EXTS
                )
            except (PermissionError, OSError):
                continue
            broken_count = broken_counts.get(folder_path, 0)
            effective_count = db_count + broken_count
            if disk_count != effective_count:
                dirty.append(folder_path)
                print(f"  [folder_sync] {folder_path}")
                print(f"    БД: {db_count}  Диск: {disk_count}  Бита: {broken_count}  Разница: {disk_count - effective_count:+d}")

        if dirty:
            print(f"[folder_sync] Требуют рескана ({len(dirty)}):")
            for fp in dirty:
                print(f"  {fp}")

        self.dirty_folders.emit(dirty)
        self.finished.emit()


def sync_folders_async(parent=None, on_dirty=None):
    """Create, start and clean up a background folder sync worker.
    If on_dirty is provided, it will be called with the list of dirty folder paths."""
    worker = FolderSyncWorker(parent)
    worker.finished.connect(worker.deleteLater)
    if on_dirty:
        worker.dirty_folders.connect(on_dirty)
    worker.start()
