"""
Folder sync — background sync of the folders table at startup.
Queries all parent folders from library and upserts them into the folders table.
After sync, automatically detects folders where track count on disk differs from DB.
"""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from musicplayer.core.db.folders import upsert_folder
from musicplayer.core.db.queries import get_all_folders
from musicplayer.core.db.broken_tracks import get_broken_counts_for_all_folders

SUPPORTED_EXTS = ('.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav', '.wma')


class FolderSyncWorker(QThread):
    finished = Signal()
    dirty_folders = Signal(list)

    def run(self):
        # Step 1: sync folders table from library
        folders = list(get_all_folders())
        for folder_path, cnt in folders:
            upsert_folder(folder_path, cnt)

        # Step 2: get known broken file counts per folder
        broken_counts = get_broken_counts_for_all_folders()

        # Step 3: detect dirty folders (DB count + broken vs disk count)
        dirty = []
        for folder_path, db_count in folders:
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
