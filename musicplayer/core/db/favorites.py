"""
Favorites Module

Handles favorites operations and favorite tracks retrieval.
"""

import os
from typing import List, Set
from musicplayer.core.db.connection import get_connection
from musicplayer.core.db.cache import _load_cover
from musicplayer.core.db.tracks import (
    TrackInfo, _row_to_track_with_cover, extract_metadata, upsert_track, delete_track
)


def is_favorite(filepath: str) -> bool:
    """Check if a track is in favorites."""
    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return False

    with get_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM favorites WHERE filepath = ?", (filepath,))
        return cursor.fetchone() is not None


def toggle_favorite(filepath: str) -> bool:
    """Toggle favorite status. Returns new state (True = favorite)."""
    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return False

    if is_favorite(filepath):
        with get_connection() as conn:
            conn.execute("DELETE FROM favorites WHERE filepath = ?", (filepath,))
        return False
    else:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO favorites (filepath) VALUES (?)", (filepath,))
        return True


def get_favorite_filepaths() -> Set[str]:
    """Get all favorite track filepaths."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT filepath FROM favorites")
        return {row[0] for row in cursor.fetchall()}


def get_favorite_tracks() -> List[TrackInfo]:
    """Get ALL favorite tracks from the library.
    Checks file mtime against DB and re-extracts metadata if file was modified.
    If a favorite filepath is missing from library, extract metadata on-the-fly.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT l.filepath, l.title, l.artist, l.album, l.duration,
                   l.has_cover, l.genre, l.is_lossless, l.mtime,
                   COALESCE(l.bitrate, 0) as bitrate,
                   COALESCE(l.tempo, 0.0) as tempo,
                   COALESCE(l.energy, 0.0) as energy,
                   COALESCE(l.mood, 0.0) as mood
            FROM favorites f
            INNER JOIN library l ON l.filepath = f.filepath
            ORDER BY l.filepath
        """)

        results = []
        for row in cursor.fetchall():
            filepath = row[0]
            db_mtime = row[8]

            has_cover = bool(row[5])
            cover_data = _load_cover(filepath) if has_cover else None
            if cover_data is None:
                has_cover = False

            track = TrackInfo(
                filepath=filepath,
                title=row[1] or "",
                artist=row[2] or "Unknown Artist",
                album=row[3] or "Unknown Album",
                duration=row[4] or 0.0,
                has_cover=has_cover,
                cover_data=cover_data,
                genre=row[6] or "",
                is_lossless=bool(row[7]),
            )
            if len(row) > 9:
                track.bitrate = row[9]
            if len(row) > 10:
                track.tempo = row[10]
            if len(row) > 11:
                track.energy = row[11]
            if len(row) > 12:
                track.mood = row[12]
            if len(row) > 8:
                track.mtime = row[8]

            # Check mtime — if file changed, re-extract metadata
            try:
                if os.path.exists(filepath):
                    current_mtime = os.path.getmtime(filepath)
                    if current_mtime > db_mtime:
                        updated_track = extract_metadata(filepath)
                        if updated_track:
                            upsert_track(updated_track, current_mtime)
                            track = updated_track
                else:
                    conn.execute("DELETE FROM favorites WHERE filepath = ?", (filepath,))
            except Exception:
                pass

            results.append(track)

        found_filepaths = {r.filepath for r in results}

    # Find favorites not in library — extract metadata on-the-fly
    all_fav_paths = get_favorite_filepaths()
    missing = all_fav_paths - found_filepaths

    for filepath in sorted(missing):
        track = extract_metadata(filepath)
        if track:
            track_mtime = track.mtime if track.mtime else os.path.getmtime(filepath)
            upsert_track(track, track_mtime)
            results.append(track)

    return results