"""
Database Module

SQLite-based persistent storage for all track metadata.
Tracks library with file modification time tracking for smart sync.
Cover art is stored as individual files in .cache/covers/ (not in DB).
"""

import os
import sys
import time
import sqlite3
import hashlib
import math
from pathlib import Path
from typing import List, Optional, Set, Tuple
from contextlib import contextmanager
from mutagen import File as MutagenFile
from mutagen.id3 import ID3


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


# ---- Artist View Cache ----

def get_artists_cache_status() -> bool:
    """
    Check if the artists cache is valid by comparing the database modification
    time with the timestamp stored in the cache_metadata table.
    Returns True if the cache is up-to-date, False otherwise.
    """
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
        # The cache is valid if the DB file hasn't been modified since the cache was last built.
        # We allow a small tolerance (e.g., 1 second) for timing inaccuracies.
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
        # Perform all operations in a single transaction
        conn.execute("DELETE FROM artists_cache")
        conn.executemany(
            "INSERT INTO artists_cache (name, track_count, collage_path) VALUES (:name, :track_count, :collage_path)",
            artists_data
        )
        conn.execute(
            "INSERT OR REPLACE INTO cache_metadata (cache_name, last_updated_mtime) VALUES ('artists', ?)",
            (db_mtime,)
        )


# ---- Cover art file cache ----

def _get_cover_path(filepath: str) -> Path:
    """Get the cache file path for a track's cover art (WebP)."""
    safe_name = hashlib.md5(filepath.encode("utf-8")).hexdigest()
    return COVERS_DIR / f"{safe_name}.webp"


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
    if not COVERS_DIR.exists():
        return 0
    total = 0
    for f in COVERS_DIR.iterdir():
        if f.is_file():
            total += f.stat().st_size
    return total


# ---- Library operations ----

def get_track_mtime(filepath: str) -> Optional[float]:
    """Get stored mtime for a track, or None if not in DB."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT mtime FROM library WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()
        return row[0] if row else None


def get_track(filepath: str) -> Optional["TrackInfo"]:
    """Get track from library by filepath. Loads cover from file cache."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   mtime
            FROM library WHERE filepath = ?
        """, (filepath,))
        row = cursor.fetchone()
        return _row_to_track_with_cover(row) if row else None


def upsert_track(track: "TrackInfo", mtime: float, preserve_play_count: bool = True):
    """
    Insert or update a track in the library. Saves cover to file cache.
    If preserve_play_count is True, keep the existing play_count value.
    Also preserves existing analysis data (tempo, energy, mood).
    """
    current_count = 0
    current_tempo = 0.0
    current_energy = 0.0
    current_mood = 0.0

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT play_count, tempo, energy, mood FROM library WHERE filepath = ?",
            (track.filepath,)
        )
        row = cursor.fetchone()
        if row:
            current_count, current_tempo, current_energy, current_mood = row

    # If new track data doesn't have analysis, use the old values
    final_tempo = getattr(track, 'tempo', 0.0)
    if final_tempo == 0.0 and current_tempo != 0.0:
        final_tempo = current_tempo

    final_energy = getattr(track, 'energy', 0.0)
    if final_energy == 0.0 and current_energy != 0.0:
        final_energy = current_energy

    final_mood = getattr(track, 'mood', 0.0)
    if final_mood == 0.0 and current_mood != 0.0:
        final_mood = current_mood

    # Handle play count preservation
    final_play_count = getattr(track, 'play_count', 0)
    if preserve_play_count:
        final_play_count = current_count

    

    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO library
                (filepath, mtime, title, artist, album, duration,
                 has_cover, genre, is_lossless, play_count, bitrate,
                 tempo, energy, mood)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            track.filepath,
            mtime,
            track.title,
            track.artist,
            track.album,
            track.duration,
            1 if track.has_cover else 0,
            track.genre,
            1 if track.is_lossless else 0,
            final_play_count,
            getattr(track, 'bitrate', 0),
            final_tempo,
            final_energy,
            final_mood,
        ))

    # Save cover art to file cache
    if track.has_cover and track.cover_data:
        _save_cover(track.filepath, track.cover_data)


def update_track_analysis(filepath: str, tempo: float, energy: float, mood: float):
    """Update only the analysis fields for a track."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE library SET
                tempo = ?,
                energy = ?,
                mood = ?
            WHERE filepath = ?
        """, (tempo, energy, mood, filepath))


def increment_play_count(filepath: str) -> int:
    """Increment the play count for a track. Returns the new count."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE library SET play_count = COALESCE(play_count, 0) + 1
            WHERE filepath = ?
        """, (filepath,))
        cursor = conn.execute("SELECT play_count FROM library WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()
        return row[0] if row else 0


def delete_track(filepath: str):
    """Delete a track from the library (and favorites, and cover file)."""
    cover_path = _get_cover_path(filepath)
    if cover_path.exists():
        try:
            cover_path.unlink()
        except OSError:
            pass

    with get_connection() as conn:
        conn.execute("DELETE FROM favorites WHERE filepath = ?", (filepath,))
        conn.execute("DELETE FROM library WHERE filepath = ?", (filepath,))


def _build_filter_clauses(search_term, genre_filter, folder_filter, fav_only, fav_set):
    """Helper to build WHERE clauses and parameters for filtering."""
    where_clauses = []
    params = []

    if fav_only:
        if not fav_set: return " WHERE 0", [] # No favorites, return no results
        # Create placeholders for all favorites
        placeholders = ','.join('?' for _ in fav_set)
        where_clauses.append(f"filepath IN ({placeholders})")
        params.extend(list(fav_set))

    if genre_filter:
        where_clauses.append("genre = ?")
        params.append(genre_filter)

    if folder_filter:
        # Normalize the folder filter path
        normalized_folder = normalize_path(folder_filter)
        where_clauses.append("filepath LIKE ?")
        params.append(normalized_folder + os.sep + '%')

    if search_term:
        # Use COLLATE NOCASE for case-insensitive Unicode search
        search_like = f"%{search_term}%"
        where_clauses.append("(title LIKE ? COLLATE NOCASE OR artist LIKE ? COLLATE NOCASE OR album LIKE ? COLLATE NOCASE)")
        params.extend([search_like, search_like, search_like])
    
    if not where_clauses:
        return "", []

    return " WHERE " + " AND ".join(where_clauses), params


def get_filtered_library_track_count(
    search_term: str = "",
    genre_filter: str = "",
    folder_filter: str = "",
    fav_only: bool = False
) -> int:
    """Get total number of tracks in the library that match filters."""
    fav_set = get_favorite_filepaths() if fav_only else set()
    where_sql, params = _build_filter_clauses(search_term, genre_filter, folder_filter, fav_only, fav_set)
    
    query = f"SELECT COUNT(*) FROM library{where_sql}"
    
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]


def get_analyzed_track_count() -> int:
    """Get total number of tracks that have been analyzed (tempo > 0.0)."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM library WHERE tempo > 0.0")
        return cursor.fetchone()[0]


def get_library_tracks_page(
    offset: int,
    limit: int,
    sort_col: str = "title",
    sort_ord: str = "ASC",
    search_term: str = "",
    genre_filter: str = "",
    folder_filter: str = "",
    fav_only: bool = False
) -> List["TrackInfo"]:
    """
    Get a page of library tracks with filtering and sorting.
    """
    fav_set = get_favorite_filepaths() if fav_only else set()
    where_sql, params = _build_filter_clauses(search_term, genre_filter, folder_filter, fav_only, fav_set)

    # Map UI sort names to DB columns
    sort_map = {
        "Название": "title COLLATE NOCASE",
        "Артист": "artist COLLATE NOCASE",
        "Альбом": "album COLLATE NOCASE",
        "Жанр": "genre COLLATE NOCASE",
        "Папка": "filepath", # Approximated by filepath
        "Длительность": "duration",
        "Битрейт": "bitrate",
        "Топ": "play_count",
        "★": "mood",
        "♡": f"CASE WHEN filepath IN ({','.join('?' for _ in fav_set)}) THEN 1 ELSE 0 END"
    }
    
    # Add favorites to params for the ORDER BY clause if sorting by favorite
    if sort_col == "♡":
        params.extend(list(fav_set))

    order_col = sort_map.get(sort_col, "title COLLATE NOCASE")
    order_dir = "DESC" if sort_ord.upper() == "DESC" else "ASC"
    
    # Add secondary sort criteria for stability
    order_clause = f"{order_col} {order_dir}, title COLLATE NOCASE ASC"

    # Add limit and offset to params
    params.extend([limit, offset])

    query = f"""
        SELECT filepath, title, artist, album, duration,
               has_cover, genre, is_lossless, COALESCE(play_count, 0) as play_count,
               COALESCE(bitrate, 0) as bitrate,
               COALESCE(tempo, 0.0) as tempo,
               COALESCE(energy, 0.0) as energy,
               COALESCE(mood, 0.0) as mood,
               mtime
        FROM library
        {where_sql}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """
    
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [_row_to_track_with_cover(row) for row in rows]


def get_all_library_tracks_light() -> List["TrackInfo"]:
    """
    Get all tracks from the library, but without loading cover data.
    Useful for operations that need all track metadata but don't need images.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   mtime
            FROM library
        """)
        rows = cursor.fetchall()
    return [_row_to_track(row) for row in rows]


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
    # This might be slow, consider rebuilding this data periodically
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


def get_tracks_by_folder(folder_path: str) -> List["TrackInfo"]:
    """Get all tracks belonging to a specific folder."""
    folder = Path(folder_path)
    folder_str = str(folder)

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood,
                   mtime
            FROM library
            WHERE filepath LIKE ?
            ORDER BY filepath
        """, (folder_str + os.sep + "%",))

        results = []
        for row in cursor.fetchall():
            track = _row_to_track_with_cover(row)
            try:
                if Path(track.filepath).parent == folder:
                    results.append(track)
            except Exception:
                pass

        return results


def get_tracks_by_artist(artist_name: str) -> List["TrackInfo"]:
    """
    Get all tracks by a specific artist, including collaborations.
    Search is case-insensitive and handles various separators.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, 
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood
            FROM library
            WHERE 
                artist = ? COLLATE NOCASE
               OR artist LIKE ? || ' & %' COLLATE NOCASE
               OR artist LIKE ? || ' ft. %' COLLATE NOCASE
               OR artist LIKE ? || ' feat. %' COLLATE NOCASE
               OR artist LIKE ? || ' vs %' COLLATE NOCASE
               OR artist LIKE ? || ' vs. %' COLLATE NOCASE
               OR artist LIKE ? || ' / %' COLLATE NOCASE
               OR artist LIKE ? || ', %' COLLATE NOCASE
               OR artist LIKE ? || '/%' COLLATE NOCASE
               OR artist LIKE ? || '&%' COLLATE NOCASE
               OR artist LIKE ? || ',%' COLLATE NOCASE
            ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, title COLLATE NOCASE
        """, (
            artist_name, artist_name, artist_name, artist_name, artist_name,
            artist_name, artist_name, artist_name, artist_name, artist_name,
            artist_name
            ))
        rows = cursor.fetchall()

    return [_row_to_track_with_cover(row) for row in rows]



def get_folder_filepaths(folder_path: str) -> Set[str]:
    """Get all filepaths in the library for a specific folder."""
    folder = Path(folder_path)
    folder_str = str(folder)

    with get_connection() as conn:
        cursor = conn.execute("SELECT filepath FROM library WHERE filepath LIKE ?", (folder_str + os.sep + "%",))
        results = set()
        for row in cursor.fetchall():
            try:
                if Path(row[0]).parent == folder:
                    results.add(row[0])
            except Exception:
                pass
        return results


def delete_folder_tracks(folder_path: str):
    """Delete all tracks from a specific folder."""
    folder = Path(folder_path)
    to_delete = get_folder_filepaths(folder_path)

    for fp in to_delete:
        delete_track(fp)


def _row_to_track(row) -> "TrackInfo":
    """Convert a database row (without cover data) to TrackInfo."""
    track = TrackInfo(
        filepath=row[0],
        title=row[1] or "",
        artist=row[2] or "Unknown Artist",
        album=row[3] or "Unknown Album",
        duration=row[4] or 0.0,
        has_cover=bool(row[5]),
        cover_data=None,
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
        track.mtime = row[13]
    return track


def _row_to_track_with_cover(row) -> "TrackInfo":
    """Convert a database row to TrackInfo, loading cover from file cache."""
    filepath = row[0]
    has_cover = bool(row[5])

    cover_data = None
    if has_cover:
        cover_data = _load_cover(filepath)
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
        track.mtime = row[13]
    return track


# ---- Favorites operations ----

def is_favorite(filepath: str) -> bool:
    """Check if a track is in favorites."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT 1 FROM favorites WHERE filepath = ?", (filepath,))
        return cursor.fetchone() is not None


def toggle_favorite(filepath: str) -> bool:
    """Toggle favorite status. Returns new state (True = favorite)."""
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


# ---- Folders operations ----

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


# ---- Favorites operations ----

def get_favorite_tracks() -> List["TrackInfo"]:
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


# ---- Top tracks (most played) ----

def get_top_tracks(limit: int = 50) -> List["TrackInfo"]:
    """
    Get top tracks by play count (min 1 play, max `limit` tracks).
    Sorted by play_count descending.
    Checks file mtime and re-extracts metadata if file was modified.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, mtime,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood
            FROM library
            WHERE play_count > 0
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

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
                track.play_count = row[9]
            if len(row) > 10:
                track.bitrate = row[10]

            # Check mtime — if file changed, re-extract metadata
            try:
                if os.path.exists(filepath):
                    current_mtime = os.path.getmtime(filepath)
                    if current_mtime > db_mtime:
                        updated_track = extract_metadata(filepath)
                        if updated_track:
                            upsert_track(updated_track, current_mtime)
                            track = updated_track
            except Exception:
                pass

            results.append(track)

        return results


def find_similar_tracks(filepath: str, limit: int = 20) -> List["TrackInfo"]:
    """
    Finds tracks in the library similar to the given track based on
    tempo, energy, and mood using Euclidean distance.
    Returns a list of TrackInfo objects, excluding the source track.
    """
    source_track = get_track(filepath)
    if not source_track or source_track.tempo == 0.0: # Only compare analyzed tracks
        return []

    # Normalize features (approximate ranges, might need calibration)
    # Tempo: 0-250 BPM (approx) -> 0-1
    # Energy: 0-1 (already normalized, from librosa RMS)
    # Mood (spectral centroid): 0-1 (already normalized, from librosa)
    
    # Simple normalization for tempo: divide by a max expected tempo (e.g., 250 BPM)
    norm_tempo_src = source_track.tempo / 250.0
    norm_energy_src = source_track.energy
    norm_mood_src = source_track.mood

    similar_tracks: List[Tuple[float, "TrackInfo"]] = [] # (distance, TrackInfo)

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT filepath, title, artist, album, duration,
                   has_cover, genre, is_lossless, mtime,
                   COALESCE(play_count, 0) as play_count,
                   COALESCE(bitrate, 0) as bitrate,
                   COALESCE(tempo, 0.0) as tempo,
                   COALESCE(energy, 0.0) as energy,
                   COALESCE(mood, 0.0) as mood
            FROM library
            WHERE filepath != ? AND tempo > 0.0 -- Exclude source and only compare analyzed tracks
        """, (filepath,))

        for row in cursor.fetchall():
            track = _row_to_track_with_cover(row) # Use existing helper to build TrackInfo
            
            # Normalize features for comparison
            norm_tempo_other = track.tempo / 250.0
            norm_energy_other = track.energy
            norm_mood_other = track.mood

            # Calculate Euclidean distance (weights can be adjusted)
            # Weights: tempo (2.0), energy (1.0), mood (1.5) - just an example, needs tuning
            distance = math.sqrt(
                2.0 * (norm_tempo_src - norm_tempo_other)**2 +
                1.0 * (norm_energy_src - norm_energy_other)**2 +
                1.5 * (norm_mood_src - norm_mood_other)**2
            )
            similar_tracks.append((distance, track))

    similar_tracks.sort(key=lambda x: x[0]) # Sort by distance

    return [track for _, track in similar_tracks[:limit]]


def ensure_cover_for_track(filepath: str) -> Optional[bytes]:
    """
    Ensure cover art is available for a track.
    1. Check if cover exists in file cache — return it if so.
    2. If not, extract cover from the audio file.
    3. If found, save to cache and update DB.
    4. Return cover bytes or None if no cover exists.
    """
    # Step 1: Check cache
    cached = _load_cover(filepath)
    if cached:
        return cached

    # Step 2: Extract from file
    track_info = extract_metadata(filepath)
    if track_info and track_info.has_cover and track_info.cover_data:
        # Step 3: Save to cache and update DB
        _save_cover(filepath, track_info.cover_data)
        try:
            mtime = os.path.getmtime(filepath)
            with get_connection() as conn:
                conn.execute("""
                    UPDATE library SET has_cover = 1
                    WHERE filepath = ?
                """, (filepath,))
        except Exception:
            pass
        return track_info.cover_data

    # Step 4: No cover found
    return None

# ---- Metadata Extraction ----

class TrackInfo:
    """Represents metadata for a single audio track."""
    
    def __init__(self, filepath: str, title: str = "", artist: str = "",
                 album: str = "", duration: float = 0.0,
                 has_cover: bool = False, cover_data: Optional[bytes] = None,
                 genre: str = "", is_lossless: bool = False,
                 play_count: int = 0, bitrate: int = 0,
                 tempo: float = 0.0, energy: float = 0.0, mood: float = 0.0,
                 mtime: float = 0.0):
                 self.filepath = filepath
                 self.title = title or Path(filepath).stem
                 self.artist = artist or "Unknown Artist"
                 self.album = album or "Unknown Album"
                 self.duration = duration
                 self.has_cover = has_cover
                 self.cover_data = cover_data  # Raw image bytes
                 self.genre = genre or ""
                 self.is_lossless = is_lossless  # True for FLAC, WAV, ALAC
                 self.play_count = play_count
                 self.bitrate = bitrate  # Bitrate in kbps
                 self.tempo = tempo  # ADDED
                 self.energy = energy  # ADDED
                 self.mood = mood    # ADDED
                 self.mtime = mtime  # File modification time from DB
    def to_dict(self) -> dict:
        """Serialize to dict (excluding cover data for JSON storage)."""
        return {
            "filepath": self.filepath,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "has_cover": self.has_cover,
            "genre": self.genre,
            "is_lossless": self.is_lossless,
            "play_count": self.play_count,
            "bitrate": self.bitrate,
            "tempo": self.tempo,    # ADDED
            "energy": self.energy,  # ADDED
            "mood": self.mood,      # ADDED
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackInfo":
        """Deserialize from dict (cover must be loaded separately)."""
        return cls(
            filepath=data["filepath"],
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=data.get("duration", 0.0),
            has_cover=data.get("has_cover", False),
            genre=data.get("genre", ""),
            is_lossless=data.get("is_lossless", False),
            play_count=data.get("play_count", 0),
            bitrate=data.get("bitrate", 0),
            tempo=data.get("tempo", 0.0),      # ADDED
            energy=data.get("energy", 0.0),    # ADDED
            mood=data.get("mood", 0.0),        # ADDED
        )
    
    def __repr__(self):
        return f"TrackInfo('{self.title}' by '{self.artist}')"

def extract_metadata(filepath: str) -> Optional["TrackInfo"]:
    """
    Extract metadata from an audio file using mutagen.
    Supports MP3, FLAC, MP4/M4A formats.

    Returns TrackInfo object or None if extraction fails.
    """
    try:
        audio = MutagenFile(filepath, easy=False)
        if audio is None:
            return None

        # Get mtime for sorting
        file_mtime = 0.0
        try:
            file_mtime = os.path.getmtime(filepath)
        except Exception:
            pass

        # Get duration
        duration = audio.info.length if hasattr(audio, 'info') else 0.0

        # Get bitrate
        bitrate = 0
        if hasattr(audio, 'info') and hasattr(audio.info, 'bitrate'):
            br = audio.info.bitrate
            if br is not None:
                bitrate = br // 1000  # Convert bps to kbps

        # Determine if lossless format
        is_lossless = _is_lossless_format(filepath, audio)

        # Extract tags based on format
        title = ""
        artist = ""
        album = ""
        genre = ""
        cover_data = None

        if hasattr(audio, 'tags') and audio.tags is not None:
            tags = audio.tags

            # Try to get text metadata
            title = _get_tag(tags, 'title', filepath)
            artist = _get_tag(tags, 'artist', filepath)
            album = _get_tag(tags, 'album', filepath)
            genre = _get_tag(tags, 'genre', filepath)

            # Try to extract cover art
            cover_data = _extract_cover(audio, tags)

        return TrackInfo(
            filepath=filepath,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            has_cover=cover_data is not None,
            cover_data=cover_data,
            genre=genre,
            is_lossless=is_lossless,
            bitrate=bitrate,
            mtime=file_mtime,
        )

    except Exception as e:
        # Silently fail - no logging needed
        return None

def _is_lossless_format(filepath: str, audio) -> bool:
    """Check if the audio file is lossless (FLAC, ALAC, WAV)."""
    ext = Path(filepath).suffix.lower()
    if ext in {'.flac', '.wav', '.aiff', '.ape', '.wv'}:
        return True
    # Check for ALAC in M4A
    if ext in {'.m4a', '.mp4'}:
        if hasattr(audio, 'info') and hasattr(audio.info, 'codec_description'):
            codec = getattr(audio.info, 'codec_description', '').lower()
            if 'alac' in codec or 'apple lossless' in codec:
                return True
    return False

def _get_tag(tags, key: str, filepath: str) -> str:
    """Extract a tag value, handling different formats."""
    try:
# ID3 tags (MP3)
        if hasattr(tags, 'getall'):
            tag_map = {
                'title': ['TIT2'],
                'artist': ['TPE1'],
                'album': ['TALB'],
                'genre': ['TCON'],
            }
            for tag_key in tag_map.get(key, []):
                val = tags.getall(tag_key)
                if val:
                    return str(val[0])

        # Vorbis comments (FLAC, OGG)
        if hasattr(tags, '__getitem__'):
            tag_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'genre': 'genre',
            }
            try:
                val = tags[tag_map.get(key, key)]
                if val:
                    return str(val[0]) if isinstance(val, list) else str(val)
            except (KeyError, IndexError):
                pass

        # MP4/M4A
        if hasattr(tags, '__getitem__'):
            tag_map = {
                'title': '©nam',
                'artist': '©ART',
                'album': '©alb',
                'genre': '©gen',
            }
            try:
                val = tags[tag_map.get(key, key)]
                if val:
                    return str(val[0]) if isinstance(val, list) else str(val)
            except (KeyError, IndexError):
                pass

        # MP4/M4A
        if hasattr(tags, '__getitem__'):
            tag_map = {
                'title': '©nam',
                'artist': '©ART',
                'album': '©alb',
                'genre': '©gen',
            }
            try:
                val = tags[tag_map.get(key, key)]
                if val:
                    return str(val[0]) if isinstance(val, list) else str(val)
            except (KeyError, IndexError):
                pass

    except Exception:
        pass

    # Return empty string (not filename) for non-title fields
    if key != 'title':
        return ""
    return Path(filepath).stem

def _extract_cover(audio, tags) -> Optional[bytes]:
    """Extract cover art from audio file."""
    try:
        # MP3 (ID3)
        if hasattr(tags, 'getall'):
            apic_frames = tags.getall('APIC')
            if apic_frames:
                return apic_frames[0].data
            
            # Try v2.3/v2.4 frames
            for frame_id in tags.keys():
                if frame_id.startswith('APIC'):
                    frame = tags[frame_id]
                    if hasattr(frame, 'data'):
                        return frame.data
        
        # FLAC
        if hasattr(audio, 'pictures') and audio.pictures:
            return audio.pictures[0].data
        
        # MP4/M4A
        if hasattr(tags, 'get') and 'covr' in tags:
            cover_list = tags['covr']
            if cover_list:
                return bytes(cover_list[0])
    
    except Exception:
        pass
    
    return None


def get_db_mtime() -> float:
    """Get last modification time of the database file."""
    if DB_PATH.exists():
        return os.path.getmtime(DB_PATH)
    return 0.0
