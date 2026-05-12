"""
Track Operations Module

Handles track CRUD operations, metadata extraction, and row conversion.
"""

import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from mutagen import File as MutagenFile

from musicplayer.core.db.connection import get_connection
from musicplayer.core.db.cache import _save_cover, _load_cover


# ---- TrackInfo class ----


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
        self.cover_data = cover_data
        self.genre = genre or ""
        self.is_lossless = is_lossless
        self.play_count = play_count
        self.bitrate = bitrate
        self.tempo = tempo
        self.energy = energy
        self.mood = mood
        self.mtime = mtime

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
            "tempo": self.tempo,
            "energy": self.energy,
            "mood": self.mood,
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
            tempo=data.get("tempo", 0.0),
            energy=data.get("energy", 0.0),
            mood=data.get("mood", 0.0),
        )

    def __repr__(self):
        return f"TrackInfo('{self.title}' by '{self.artist}')"


# ---- Row conversion helpers ----


def _row_to_track(row: tuple) -> TrackInfo:
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


def _row_to_track_with_cover(row: tuple) -> TrackInfo:
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


# ---- Track operations ----


def get_track_mtime(filepath: str) -> Optional[float]:
    """Get stored mtime for a track, or None if not in DB."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT mtime FROM library WHERE filepath = ?", (filepath,))
        row = cursor.fetchone()
        return row[0] if row else None


def get_track(filepath: str) -> Optional[TrackInfo]:
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


def upsert_track(track: TrackInfo, mtime: float, preserve_play_count: bool = True):
    """
    Insert or update a track in the library. Saves cover to file cache.
    If preserve_play_count is True, keep the existing play_count value.
    Also preserves existing analysis data (tempo, energy, mood).
    Normalizes metadata before saving.
    """
    from musicplayer.core.normalize import normalize_track

    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(track.filepath, music_folder):
        return

    normalized = normalize_track(track)

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

    final_tempo = getattr(track, 'tempo', 0.0)
    if final_tempo == 0.0 and current_tempo != 0.0:
        final_tempo = current_tempo

    final_energy = getattr(track, 'energy', 0.0)
    if final_energy == 0.0 and current_energy != 0.0:
        final_energy = current_energy

    final_mood = getattr(track, 'mood', 0.0)
    if final_mood == 0.0 and current_mood != 0.0:
        final_mood = current_mood

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
            normalized.filepath,
            mtime,
            normalized.title,
            normalized.artist,
            normalized.album,
            normalized.duration,
            1 if normalized.has_cover else 0,
            normalized.genre,
            1 if normalized.is_lossless else 0,
            final_play_count,
            getattr(track, 'bitrate', 0),
            final_tempo,
            final_energy,
            final_mood,
        ))

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
    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return

    from musicplayer.core.db.cache import delete_cover
    delete_cover(filepath)

    with get_connection() as conn:
        conn.execute("DELETE FROM favorites WHERE filepath = ?", (filepath,))
        conn.execute("DELETE FROM library WHERE filepath = ?", (filepath,))


def get_all_library_tracks_light() -> List[TrackInfo]:
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


def extract_metadata(filepath: str) -> Optional[TrackInfo]:
    """
    Extract metadata from an audio file using mutagen.
    Supports MP3, FLAC, MP4/M4A formats.

    Returns TrackInfo object or None if extraction fails.
    """
    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        return None

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

        # Normalize metadata before returning
        from musicplayer.core.normalize import normalize_metadata
        normalized = normalize_metadata(
            title=title,
            artist=artist,
            album=album,
            genre=genre
        )
        title = normalized.get('title', title)
        artist = normalized.get('artist', artist)
        album = normalized.get('album', album)
        genre = normalized.get('genre', genre)

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

    except Exception:
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


def get_tracks_by_artist(artist_name: str) -> List[TrackInfo]:
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


def get_tracks_by_folder(folder_path: str) -> List[TrackInfo]:
    """Get all tracks belonging to a specific folder."""
    import os as os_module
    from musicplayer.core.db.queries import _escape_like_pattern

    folder = Path(folder_path)
    folder_str = str(folder)
    # Escape LIKE wildcards in folder path
    escaped_folder = _escape_like_pattern(folder_str)

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
        """, (escaped_folder + os_module.sep + "%",))

        results = []
        for row in cursor.fetchall():
            track = _row_to_track_with_cover(row)
            try:
                if Path(track.filepath).parent == folder:
                    results.append(track)
            except Exception:
                pass

        return results


def get_folder_filepaths(folder_path: str):
    """Get all filepaths in the library for a specific folder."""
    import os as os_module
    from typing import Set
    from musicplayer.core.db.queries import _escape_like_pattern

    folder = Path(folder_path)
    folder_str = str(folder)
    # Escape LIKE wildcards in folder path
    escaped_folder = _escape_like_pattern(folder_str)

    with get_connection() as conn:
        cursor = conn.execute("SELECT filepath FROM library WHERE filepath LIKE ?", (escaped_folder + os_module.sep + "%",))
        results: Set[str] = set()
        for row in cursor.fetchall():
            try:
                if Path(row[0]).parent == folder:
                    results.add(row[0])
            except Exception:
                pass
        return results


def delete_folder_tracks(folder_path: str):
    """Delete all tracks from a specific folder."""
    # Validate folder_path for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(folder_path, music_folder):
        return

    to_delete = get_folder_filepaths(folder_path)
    for fp in to_delete:
        delete_track(fp)