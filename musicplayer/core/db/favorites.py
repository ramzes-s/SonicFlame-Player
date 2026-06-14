"""
Favorites Module

Handles favorites operations using the is_favorite column in the library table.
"""

import os
from typing import List, Set
from musicplayer.core.db.connection import get_connection
from musicplayer.core.db.cache import _load_cover
from musicplayer.core.db.tracks import (
    TrackInfo, _row_to_track_with_cover, extract_metadata, upsert_track
)


def is_favorite(filepath: str) -> bool:
    """Check if a track is in favorites."""
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return False

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT is_favorite FROM library WHERE filepath = ?", (filepath,)
        )
        row = cursor.fetchone()
        return bool(row[0]) if row is not None else False


def toggle_favorite(filepath: str) -> bool:
    """Toggle favorite status. Returns new state (True = favorite)."""
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return False

    with get_connection() as conn:
        conn.execute("""
            UPDATE library SET is_favorite = CASE WHEN is_favorite THEN 0 ELSE 1 END
            WHERE filepath = ?
        """, (filepath,))
        cursor = conn.execute(
            "SELECT is_favorite FROM library WHERE filepath = ?", (filepath,)
        )
        row = cursor.fetchone()
        return bool(row[0]) if row is not None else False


def get_favorite_filepaths() -> Set[str]:
    """Get all favorite track filepaths."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT filepath FROM library WHERE is_favorite = 1")
        return {row[0] for row in cursor.fetchall()}


def get_favorite_tracks() -> List[TrackInfo]:
    """Get ALL favorite tracks from the library."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                   mtime,
                   COALESCE(language, '') as language,
                   COALESCE(is_favorite, 0) as is_favorite,
                   COALESCE(year, 0) as year
            FROM library
            WHERE is_favorite = 1
            ORDER BY filepath
        """)

        results = []
        for row in cursor.fetchall():
            filepath = row[0]
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
            if len(row) > 8:
                track.play_count = row[8]
            if len(row) > 9:
                track.bitrate = row[9]
            if len(row) > 10:
                track.tempo = row[10]
            if len(row) > 11:
                track.energy = row[11]
            if len(row) > 12:
                track.mood = row[12]
            if len(row) > 13:
                track.hpss_ratio = row[13]
            if len(row) > 14:
                track.zero_crossing_rate = row[14]
            if len(row) > 15:
                track.spectral_flux = row[15]
            if len(row) > 16:
                track.mtime = row[16]
            if len(row) > 17:
                track.language = row[17]
            if len(row) > 18:
                track.is_favorite = bool(row[18])
            if len(row) > 19:
                track.year = row[19] or 0

            results.append(track)

    return results
