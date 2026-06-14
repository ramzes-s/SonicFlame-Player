"""
Query Helpers Module

Provides helper functions for filtering, sorting, and complex queries.
"""

import os
import math
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional
from musicplayer.core.db.connection import get_connection, normalize_path
from musicplayer.core.db.tracks import (
    TrackInfo, _row_to_track_with_cover, _row_to_track, get_track
)


# ---- Filter building ----


def _escape_like_pattern(text: str) -> str:
    r"""Escape special characters in SQL LIKE pattern.
    Escapes: % _ \ to treat them as literal characters.
    """
    # Order matters: escape backslash first
    return text.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')


def _build_filter_clauses(search_term: str, genre_filter: str, folder_filter: str,
                          fav_only: bool) -> Tuple[str, List]:
    """Helper to build WHERE clauses and parameters for filtering."""
    where_clauses = []
    params = []

    if fav_only:
        where_clauses.append("is_favorite = 1")

    if genre_filter:
        where_clauses.append("genre LIKE ?")
        escaped_genre = _escape_like_pattern(genre_filter)
        params.append(f"%{escaped_genre}%")

    if folder_filter:
        normalized_folder = normalize_path(folder_filter)
        # Escape LIKE wildcards in folder path
        escaped_folder = _escape_like_pattern(normalized_folder)
        where_clauses.append("filepath LIKE ?")
        params.append(escaped_folder + os.sep + '%')

    if search_term:
        # Escape special LIKE characters so user can search for literal % or _
        escaped_search = _escape_like_pattern(search_term)
        search_like = f"%{escaped_search}%"
        where_clauses.append("(title LIKE ? COLLATE NOCASE OR artist LIKE ? COLLATE NOCASE OR album LIKE ? COLLATE NOCASE)")
        params.extend([search_like, search_like, search_like])

    if not where_clauses:
        return "", []

    return " WHERE " + " AND ".join(where_clauses), params


# ---- Library queries ----


def _validate_int(value: int, default: int, min_val: int = 0, max_val: int = 1000000) -> int:
    """Validate and sanitize integer parameter."""
    try:
        value = int(value)
        return max(min_val, min(max_val, value))
    except (TypeError, ValueError):
        return default


def get_filtered_library_track_count(
    search_term: str = "",
    genre_filter: str = "",
    folder_filter: str = "",
    fav_only: bool = False
) -> int:
    """Get total number of tracks in the library that match filters."""
    where_sql, params = _build_filter_clauses(search_term, genre_filter, folder_filter, fav_only)

    query = f"SELECT COUNT(*) FROM library{where_sql}"

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]


def get_analyzed_track_count() -> int:
    """Get total number of tracks that have been analyzed (tempo > 0.0)."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM library WHERE tempo > 0.0")
            return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def get_library_tracks_page(
    offset: int,
    limit: int,
    sort_col: str = "title",
    sort_ord: str = "ASC",
    search_term: str = "",
    genre_filter: str = "",
    folder_filter: str = "",
    fav_only: bool = False
) -> List[TrackInfo]:
    """Get a page of library tracks with filtering and sorting."""
    # Validate and sanitize integer parameters
    offset = _validate_int(offset, 0)
    limit = _validate_int(limit, 50, 1, 500)

    where_sql, params = _build_filter_clauses(search_term, genre_filter, folder_filter, fav_only)

    # Map UI sort names to DB columns - whitelist approach
    sort_map = {
        "Название": "title COLLATE NOCASE",
        "Артист": "artist COLLATE NOCASE",
        "Альбом": "album COLLATE NOCASE",
        "Жанр": "genre COLLATE NOCASE",
        "Папка": "filepath",
        "Длительность": "duration",
        "Битрейт": "bitrate",
        "Топ": "play_count",
        "★": "mood",
        "♡": "is_favorite"
    }

    # Validate sort_col against whitelist - prevent SQL injection in ORDER BY
    if sort_col in sort_map:
        order_col = sort_map[sort_col]
    else:
        order_col = "title COLLATE NOCASE"

    # Validate sort direction - only allow ASC or DESC
    order_dir = "DESC" if sort_ord.upper() == "DESC" else "ASC"
    order_clause = f"{order_col} {order_dir}, title COLLATE NOCASE ASC"

    params.extend([limit, offset])

    query = f"""
        SELECT filepath, title, artist, album, duration,
               has_cover, genre, is_lossless, COALESCE(play_count, 0) as play_count,
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
        {where_sql}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [_row_to_track_with_cover(row) for row in rows]


# ---- Genre and folder queries ----


def get_all_genres() -> List[str]:
    """Get all unique genres from the library."""
    genres = set()
    with get_connection() as conn:
        cursor = conn.execute("SELECT genre FROM library WHERE genre != '' AND genre IS NOT NULL")
        for row in cursor.fetchall():
            genre_str = row[0]
            for sep in ['/', ';', ',']:
                for g in genre_str.split(sep):
                    g = g.strip()
                    if g:
                        genres.add(g)
    return sorted(genres)


def get_all_folders() -> List[Tuple[str, int]]:
    """Get all folders with their track counts, sorted by path."""
    folder_map = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT filepath FROM library")
        for row in cursor.fetchall():
            try:
                parent_folder = str(Path(row[0]).parent)
                folder_map[parent_folder] = folder_map.get(parent_folder, 0) + 1
            except Exception:
                pass
    return sorted(folder_map.items())


# ---- Top tracks ----


def get_top_tracks(limit: int = 100) -> List[TrackInfo]:
    """Get top tracks by play count (min 1 play, max `limit` tracks)."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, mtime,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                   COALESCE(language, '') as language,
                   COALESCE(is_favorite, 0) as is_favorite,
                   COALESCE(year, 0) as year
            FROM library
            WHERE play_count > 0
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

        results = []
        for row in cursor.fetchall():
            filepath = row[0]
            db_mtime = row[8]

            from musicplayer.core.db.cache import _load_cover as load_cover
            has_cover = bool(row[5])
            cover_data = load_cover(filepath) if has_cover else None
            if cover_data is None:
                has_cover = False

            from musicplayer.core.db.tracks import TrackInfo as TI
            track = TI(
                filepath=filepath,
                title=row[1] or "",
                artist=row[2] or "Unknown Artist",
                album=row[3] or "Unknown Album",
                duration=row[4] or 0.0,
                has_cover=has_cover,
                cover_data=cover_data,
                genre=row[6] or "",
                is_lossless=bool(row[7]),
                play_count=row[9] if len(row) > 9 else 0,
                bitrate=row[10] if len(row) > 10 else 0,
                tempo=row[11] if len(row) > 11 else 0.0,
                energy=row[12] if len(row) > 12 else 0.0,
                mood=row[13] if len(row) > 13 else 0.0,
                hpss_ratio=row[14] if len(row) > 14 else 0.0,
                zero_crossing_rate=row[15] if len(row) > 15 else 0.0,
                spectral_flux=row[16] if len(row) > 16 else 0.0,
                is_favorite=bool(row[18]) if len(row) > 18 else False,
                year=row[19] if len(row) > 19 else 0,
            )

            try:
                if os.path.exists(filepath):
                    current_mtime = os.path.getmtime(filepath)
                    if current_mtime > db_mtime:
                        from musicplayer.core.db.tracks import extract_metadata
                        updated_track = extract_metadata(filepath)
                        if updated_track:
                            from musicplayer.core.db.tracks import upsert_track
                            upsert_track(updated_track, current_mtime)
                            track = updated_track
            except Exception:
                pass

            results.append(track)

        return results


# ---- Similar tracks ----


def find_similar_tracks(filepath: str, limit: int = 20) -> List[TrackInfo]:
    """Find tracks similar to given track based on tempo, energy, and mood."""
    source_track = get_track(filepath)
    if not source_track or source_track.tempo == 0.0:
        return []

    norm_tempo_src = source_track.tempo / 250.0
    norm_energy_src = source_track.energy
    norm_mood_src = source_track.mood

    similar_tracks: List[Tuple[float, TrackInfo]] = []

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, mtime,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                   COALESCE(language, '') as language,
                   COALESCE(is_favorite, 0) as is_favorite,
                   COALESCE(year, 0) as year
            FROM library
            WHERE filepath != ? AND tempo > 0.0
        """, (filepath,))

        for row in cursor.fetchall():
            track = _row_to_track_with_cover(row)

            norm_tempo_other = track.tempo / 250.0
            norm_energy_other = track.energy
            norm_mood_other = track.mood

            distance = math.sqrt(
                2.0 * (norm_tempo_src - norm_tempo_other)**2 +
                1.0 * (norm_energy_src - norm_energy_other)**2 +
                1.5 * (norm_mood_src - norm_mood_other)**2
            )
            similar_tracks.append((distance, track))

    similar_tracks.sort(key=lambda x: x[0])
    return [track for _, track in similar_tracks[:limit]]