"""
Broken tracks table — tracks audio files that fail metadata extraction.
Used to:
- Show user a list of problematic files in settings
- Subtract broken count from disk count to avoid false dirty-folder detection
"""

import os
from pathlib import Path

from musicplayer.core.db.connection import get_connection


def create_broken_tracks_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS broken_tracks (
                filepath TEXT PRIMARY KEY NOT NULL,
                folder_path TEXT NOT NULL,
                error TEXT DEFAULT '',
                detected_at REAL NOT NULL DEFAULT (julianday('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_broken_tracks_folder
            ON broken_tracks(folder_path)
        """)


def add_broken_track(filepath: str, folder_path: str, error: str = ""):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO broken_tracks (filepath, folder_path, error, detected_at)
            VALUES (?, ?, ?, julianday('now'))
        """, (filepath, folder_path, error))


def clear_broken_tracks_for_folder(folder_path: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM broken_tracks WHERE folder_path = ?", (folder_path,))


def delete_broken_tracks_in_subtree(folder_path: str):
    """Remove all broken entries whose folder is under (or equal to) folder_path."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM broken_tracks WHERE folder_path = ? OR folder_path LIKE ?",
            (folder_path, folder_path + os.sep + '%')
        )


def clear_broken_track(filepath: str):
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM broken_tracks WHERE filepath = ?", (filepath,))
    except Exception:
        pass


def get_broken_count_for_folder(folder_path: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM broken_tracks WHERE folder_path = ?",
            (folder_path,)
        )
        return cursor.fetchone()[0]


def get_broken_counts_for_all_folders() -> dict:
    """Returns {folder_path: count} counting broken files recursively — each
    broken file is counted for all ancestor folders, not just its direct parent."""
    result = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT folder_path FROM broken_tracks")
        for row in cursor.fetchall():
            p = Path(row[0])
            for parent in [p] + list(p.parents):
                key = str(parent)
                result[key] = result.get(key, 0) + 1
    return result


def get_all_broken_tracks() -> list:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT filepath, folder_path, error, detected_at FROM broken_tracks ORDER BY filepath"
        )
        return cursor.fetchall()


def get_broken_track_count() -> int:
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM broken_tracks")
        return cursor.fetchone()[0]
