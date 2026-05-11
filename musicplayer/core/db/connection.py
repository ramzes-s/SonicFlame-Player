"""
Database Connection Module

Handles SQLite connection setup, WAL mode, and path configuration.
"""

import os
import sys
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional


def _get_exe_dir() -> Path:
    """Get the directory containing the exe (or project root in dev mode)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


def normalize_path(path_str: str) -> str:
    """Normalize path separators to os.sep for consistent storage and comparison."""
    return path_str.replace("/", os.sep).replace("\\", os.sep)


# Database location
DB_DIR = _get_exe_dir() / ".cache"
DB_PATH = DB_DIR / "musicplayer.db"
COVERS_DIR = DB_DIR / "covers"


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