"""
Folders Module

Handles folder operations and folder-specific queries.
"""

from typing import Optional
from musicplayer.core.db.connection import get_connection, normalize_path


def upsert_folder(folder_path: str, track_count: int):
    """Insert or update a folder with track count."""
    folder_path = normalize_path(folder_path)
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO folders (folder_path, track_count)
            VALUES (?, ?)
        """, (folder_path, track_count))


def get_folder_track_count(folder_path: str) -> Optional[int]:
    """Get track count for a folder, or None if folder not in DB."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT track_count FROM folders WHERE folder_path = ?", (folder_path,))
        row = cursor.fetchone()
        return row[0] if row else None


def delete_folder(folder_path: str):
    """Delete a folder from the folders table."""
    with get_connection() as conn:
        conn.execute("DELETE FROM folders WHERE folder_path = ?", (folder_path,))