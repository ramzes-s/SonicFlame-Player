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
    """Validate that a filepath is contained within base_dir.

    Resolves symlinks/junctions and normalises case for case-insensitive
    filesystems (Windows). Returns False if base_dir is not provided —
    containment cannot be verified without it.

    Args:
        filepath: The path to validate
        base_dir: Directory that filepath must be inside

    Returns:
        True if filepath is inside base_dir, False otherwise
    """
    if not filepath or not base_dir:
        return False

    try:
        real_filepath = os.path.realpath(os.path.normcase(filepath))
        real_base = os.path.realpath(os.path.normcase(base_dir))
    except (OSError, ValueError):
        return False

    if real_filepath == real_base:
        return True
    return real_filepath.startswith(real_base + os.sep)


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
                    mood REAL DEFAULT 0,
                    zero_crossing_rate REAL DEFAULT 0,
                    spectral_flux REAL DEFAULT 0,
                    hpss_ratio REAL DEFAULT 0,
                    is_favorite INTEGER DEFAULT 0
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
            conn.execute("""
                CREATE TABLE system_data (
                    key TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO system_data (key, value)
                VALUES ('db_version_compare', ?)
            """, (str(config.DB_VERSION),))
            return

        # Table exists — migrate missing columns

        # Drop old favorites table — now using is_favorite column in library
        conn.execute("DROP TABLE IF EXISTS favorites")

        # Ensure is_favorite column exists in library
        cursor = conn.execute("PRAGMA table_info(library)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'is_favorite' not in columns:
            conn.execute("ALTER TABLE library ADD COLUMN is_favorite INTEGER DEFAULT 0")

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
        # ---- System Data (key-value store) ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_data (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)


def check_db_version() -> Optional[str]:
    """Check DB version compatibility. Returns error message or None if OK."""
    db_version_str = None
    try:
        from musicplayer.core.db.system import get_system_value
        db_version_str = get_system_value('db_version_compare')
    except Exception:
        pass
    try:
        db_version = int(db_version_str) if db_version_str is not None else 0
    except (ValueError, TypeError):
        return None
    if db_version > config.DB_VERSION:
        return (
            f"База данных создана более новой версией программы "
            f"(версия БД: {db_version}, версия программы: {config.DB_VERSION}).\n"
            f"Пожалуйста, обновите программу."
        )
    if db_version < config.DB_VERSION:
        return (
            f"База данных устарела и несовместима с текущей версией программы "
            f"(версия БД: {db_version}, требуемая версия: {config.DB_VERSION}).\n"
            f"Требуется обновление базы данных."
        )
    return None


def get_db_mtime() -> float:
    """Get last modification time of the database file."""
    if DB_PATH.exists():
        return os.path.getmtime(DB_PATH)
    return 0.0