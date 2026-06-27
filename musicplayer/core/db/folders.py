"""
Folders Module

Handles folder operations and folder-specific queries.
"""

from typing import Optional
from musicplayer.core.db.connection import get_connection, normalize_path


def upsert_folder(folder_path: str, track_count: int, last_scanned: Optional[float] = None):
    """Insert or update a folder with track count and optional last scan time."""
    # Validate folder_path for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(folder_path, music_folder):
        return

    folder_path = normalize_path(folder_path)
    with get_connection() as conn:
        if last_scanned is not None:
            conn.execute("""
                INSERT INTO folders (folder_path, track_count, last_scanned)
                VALUES (?, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    track_count = excluded.track_count,
                    last_scanned = excluded.last_scanned
            """, (folder_path, track_count, last_scanned))
        else:
            conn.execute("""
                INSERT INTO folders (folder_path, track_count)
                VALUES (?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    track_count = excluded.track_count
            """, (folder_path, track_count))


def get_folder_track_count(folder_path: str) -> Optional[int]:
    """Get track count for a folder, or None if folder not in DB."""
    # Validate folder_path for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(folder_path, music_folder):
        return None

    with get_connection() as conn:
        cursor = conn.execute("SELECT track_count FROM folders WHERE folder_path = ?", (folder_path,))
        row = cursor.fetchone()
        return row[0] if row else None


def delete_folder(folder_path: str):
    """Delete a folder from the folders table."""
    # Validate folder_path for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(folder_path, music_folder):
        return

    with get_connection() as conn:
        conn.execute("DELETE FROM folders WHERE folder_path = ?", (folder_path,))