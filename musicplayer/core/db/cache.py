"""
Cache Module

Handles cover art file caching and artists cache management.
"""

import hashlib
import time
from pathlib import Path
from typing import List, Optional

from musicplayer.core.db.connection import get_connection, COVERS_DIR, get_db_mtime


# ---- Cover art file cache ----


def _get_cover_path(filepath: str) -> Path:
    """Get the cache file path for a track's cover art (WebP)."""
    safe_name = hashlib.md5(filepath.encode("utf-8")).hexdigest()
    return COVERS_DIR / f"{safe_name}.webp"


def get_cover_path(filepath: str) -> Path:
    """Public wrapper for _get_cover_path."""
    return _get_cover_path(filepath)


def _save_cover(filepath: str, cover_data: bytes):
    """Save cover art to file cache, converting to WebP with quality limit."""
    cover_path = _get_cover_path(filepath)
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(cover_data))

        # Limit dimensions to max 800px on the longest side
        max_size = 800
        if img.width > max_size or img.height > max_size:
            ratio = max_size / max(img.width, img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Use quality=85 (visually lossless but much smaller) instead of lossless
        img.save(cover_path, "WEBP", quality=85)
    except Exception:
        # Fallback: save raw data if conversion fails
        try:
            with open(cover_path, "wb") as f:
                f.write(cover_data)
        except IOError:
            pass


def _load_cover(filepath: str) -> Optional[bytes]:
    """Load cover art from the file cache."""
    cover_path = _get_cover_path(filepath)
    if cover_path.exists():
        try:
            with open(cover_path, "rb") as f:
                return f.read()
        except IOError:
            pass
    return None


def get_covers_cache_size() -> int:
    """Total size of all cached cover image files."""
    count, total = get_covers_cache_info()
    return total


_covers_cache = None
_covers_cache_time = 0
_collages_cache = None
_collages_cache_time = 0
_CACHE_TTL = 1800  # 30 minutes


def get_covers_cache_info():
    """Return (file_count, total_size_bytes) for cover cache.
    Results are cached for 30 minutes."""
    global _covers_cache, _covers_cache_time
    now = time.time()
    if _covers_cache is not None and (now - _covers_cache_time) < _CACHE_TTL:
        return _covers_cache
    if not COVERS_DIR.exists():
        _covers_cache = (0, 0)
        _covers_cache_time = now
        return _covers_cache
    count = 0
    total = 0
    for f in COVERS_DIR.iterdir():
        if f.is_file():
            count += 1
            total += f.stat().st_size
    _covers_cache = (count, total)
    _covers_cache_time = now
    return _covers_cache


def get_artist_collage_cache_info():
    """Return (file_count, total_size_bytes) for artist collage cache.
    Results are cached for 30 minutes."""
    global _collages_cache, _collages_cache_time
    from musicplayer import config as cfg
    now = time.time()
    if _collages_cache is not None and (now - _collages_cache_time) < _CACHE_TTL:
        return _collages_cache
    d = cfg.ARTIST_COLLAGES_DIR
    if not d.exists():
        _collages_cache = (0, 0)
        _collages_cache_time = now
        return _collages_cache
    count = 0
    total = 0
    for f in d.iterdir():
        if f.is_file():
            count += 1
            total += f.stat().st_size
    _collages_cache = (count, total)
    _collages_cache_time = now
    return _collages_cache


# ---- Artist View Cache ----


def get_artists_cache_status() -> bool:
    """
    Check if the artists cache is valid by comparing the database modification
    time with the timestamp stored in the cache_metadata table.
    Returns True if the cache is up-to-date, False otherwise.
    """
    from musicplayer.core.db.connection import DB_PATH

    if not DB_PATH.exists():
        return False

    db_mtime = get_db_mtime()

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT last_updated_mtime FROM cache_metadata WHERE cache_name = 'artists'"
        )
        row = cursor.fetchone()
        if row is None:
            return False  # Cache has never been created

        last_updated_mtime = row[0]
        return db_mtime <= last_updated_mtime + 1


def get_cached_artists() -> List[dict]:
    """
    Retrieve all artists from the artists_cache table.
    Returns a list of dictionaries, each representing an artist.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT name, track_count, collage_path FROM artists_cache ORDER BY name COLLATE NOCASE"
        )
        return [
            {"name": row[0], "track_count": row[1], "collage_path": row[2]}
            for row in cursor.fetchall()
        ]


def update_artists_cache(artists_data: List[dict]):
    """
    Update the artists cache with fresh data. This involves clearing the
    old cache, inserting the new data, and updating the cache metadata timestamp.
    """
    db_mtime = get_db_mtime()
    if not artists_data:
        return

    with get_connection() as conn:
        conn.execute("DELETE FROM artists_cache")
        conn.executemany(
            "INSERT INTO artists_cache (name, track_count, collage_path) VALUES (:name, :track_count, :collage_path)",
            artists_data
        )
        conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (cache_name, last_updated_mtime) VALUES ('artists', ?)",
            (db_mtime,)
        )


def delete_cover(filepath: str):
    """Delete cover art from cache for a track."""
    cover_path = _get_cover_path(filepath)
    if cover_path.exists():
        try:
            cover_path.unlink()
        except OSError:
            pass