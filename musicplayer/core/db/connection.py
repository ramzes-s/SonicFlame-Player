"""
Database Connection Module

Handles SQLite connection setup, WAL mode, and path configuration.
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from musicplayer import config


def normalize_path(path_str: str) -> str:
    """Normalize path separators to os.sep for consistent storage and comparison."""
    return path_str.replace("/", os.sep).replace("\\", os.sep)


def is_safe_filepath(filepath: str, base_dir: Optional[str] = None) -> bool:
    """Validate that a filepath is safe and doesn't contain path traversal.
    
    Args:
        filepath: The path to validate
        base_dir: Optional base directory to check containment against
        
    Returns:
        True if path is safe, False otherwise
    """
    if not filepath:
        return False
    
    # Check for path traversal attempts
    normalized = os.path.normpath(filepath)
    if '..' in normalized.split(os.sep):
        return False
    
    # Check for absolute path escaping (e.g., C:\..\..\)
    abs_path = os.path.abspath(normalized)
    if base_dir:
        abs_base = os.path.abspath(base_dir)
        # Ensure the path is within the base directory
        if not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
            return False
    
    return True


def get_music_folder() -> Optional[str]:
    """Get the configured music folder from settings."""
    try:
        from musicplayer.core.settings import AppSettings
        settings = AppSettings()
        return settings.music_folder
    except Exception:
        return None


# Database location
DB_DIR = config.CACHE_DIR
DB_PATH = config.DB_PATH
COVERS_DIR = config.COVERS_DIR


@contextmanager
def get_connection(db_path: Path = DB_PATH):
    """Get a database connection with WAL mode enabled."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist, migrate schema if needed."""
    with get_connection() as conn:
        # Check if library table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='library'"
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Fresh install — create tables with latest schema
            conn.execute("""
                CREATE TABLE library (
                    filepath TEXT PRIMARY KEY NOT NULL,
                    mtime REAL NOT NULL,
                    title TEXT DEFAULT '',
                    artist TEXT DEFAULT 'Unknown Artist',
                    album TEXT DEFAULT 'Unknown Album',
                    duration REAL DEFAULT 0,
                    has_cover INTEGER DEFAULT 0,
                    genre TEXT DEFAULT '',
                    is_lossless INTEGER DEFAULT 0,
                    play_count INTEGER DEFAULT 0,
                    bitrate INTEGER DEFAULT 0,
                    tempo REAL DEFAULT 0,
                    energy REAL DEFAULT 0,
                    mood REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE favorites (
                    filepath TEXT PRIMARY KEY NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE folders (
                    folder_path TEXT PRIMARY KEY NOT NULL,
                    track_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_library_mtime ON library(mtime)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_library_artist_album_title ON library(artist, album, title)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_library_play_count ON library(play_count)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_library_genre ON library(genre)
            """)
            return

        # Table exists — migrate missing columns

        # Ensure favorites table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'"
        )
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE favorites (
                    filepath TEXT PRIMARY KEY NOT NULL
                )
            """)

        # Ensure folders table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='folders'"
        )
        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE folders (
                    folder_path TEXT PRIMARY KEY NOT NULL,
                    track_count INTEGER DEFAULT 0
                )
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_library_mtime ON library(mtime)
        """)
        # ---- Artist View Cache ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artists_cache (
                name TEXT PRIMARY KEY NOT NULL,
                track_count INTEGER NOT NULL,
                collage_path TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                cache_name TEXT PRIMARY KEY NOT NULL,
                last_updated_mtime REAL NOT NULL
            )
        """)


def get_db_mtime() -> float:
    """Get last modification time of the database file."""
    if DB_PATH.exists():
        return os.path.getmtime(DB_PATH)
    return 0.0