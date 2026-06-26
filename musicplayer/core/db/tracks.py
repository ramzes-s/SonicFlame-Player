"""
Track Operations Module

Handles track CRUD operations, metadata extraction, and row conversion.
"""

import os
import re
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
                 zero_crossing_rate: float = 0.0,
                 spectral_flux: float = 0.0,
                 hpss_ratio: float = 0.0,
                 mtime: float = 0.0,
                 language: str = "",
                 is_favorite: bool = False,
                 year: int = 0):
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
        self.zero_crossing_rate = zero_crossing_rate
        self.spectral_flux = spectral_flux
        self.hpss_ratio = hpss_ratio
        self.mtime = mtime
        self.language = language
        self.is_favorite = is_favorite
        self.year = year

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
            "language": self.language,
            "is_lossless": self.is_lossless,
            "play_count": self.play_count,
            "bitrate": self.bitrate,
            "tempo": self.tempo,
            "energy": self.energy,
            "mood": self.mood,
            "zero_crossing_rate": self.zero_crossing_rate,
            "spectral_flux": self.spectral_flux,
            "hpss_ratio": self.hpss_ratio,
            "is_favorite": self.is_favorite,
            "year": self.year,
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
            zero_crossing_rate=data.get("zero_crossing_rate", 0.0),
            spectral_flux=data.get("spectral_flux", 0.0),
            hpss_ratio=data.get("hpss_ratio", 0.0),
            is_favorite=data.get("is_favorite", False),
            year=data.get("year", 0),
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
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                   mtime,
                   COALESCE(language, '') as language,
                   COALESCE(is_favorite, 0) as is_favorite,
                   COALESCE(year, 0) as year
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
    current_zero_crossing_rate = 0.0
    current_spectral_flux = 0.0
    current_hpss_ratio = 0.0
    current_is_favorite = False

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT play_count, tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio, is_favorite FROM library WHERE filepath = ?",
            (track.filepath,)
        )
        row = cursor.fetchone()
        if row:
            current_count, current_tempo, current_energy, current_mood, current_zero_crossing_rate, current_spectral_flux, current_hpss_ratio, current_is_favorite = row

        final_tempo = getattr(track, 'tempo', 0.0)
        if final_tempo == 0.0 and current_tempo != 0.0:
            final_tempo = current_tempo

        final_energy = getattr(track, 'energy', 0.0)
        if final_energy == 0.0 and current_energy != 0.0:
            final_energy = current_energy

        final_mood = getattr(track, 'mood', 0.0)
        if final_mood == 0.0 and current_mood != 0.0:
            final_mood = current_mood

        final_zero_crossing_rate = getattr(track, 'zero_crossing_rate', 0.0)
        if final_zero_crossing_rate == 0.0 and current_zero_crossing_rate != 0.0:
            final_zero_crossing_rate = current_zero_crossing_rate

        final_spectral_flux = getattr(track, 'spectral_flux', 0.0)
        if final_spectral_flux == 0.0 and current_spectral_flux != 0.0:
            final_spectral_flux = current_spectral_flux

        final_hpss_ratio = getattr(track, 'hpss_ratio', 0.0)
        if final_hpss_ratio == 0.0 and current_hpss_ratio != 0.0:
            final_hpss_ratio = current_hpss_ratio

        final_play_count = getattr(track, 'play_count', 0)
        if preserve_play_count:
            final_play_count = current_count

        final_is_favorite = getattr(track, 'is_favorite', False)
        if row is not None:
            final_is_favorite = current_is_favorite

        conn.execute("""
            INSERT OR REPLACE INTO library
                (filepath, mtime, title, artist, album, duration,
                 has_cover, genre, is_lossless, play_count, bitrate,
                 tempo, energy, mood,
                 zero_crossing_rate, spectral_flux, hpss_ratio,
                 language, is_favorite, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            final_zero_crossing_rate,
            final_spectral_flux,
            final_hpss_ratio,
            getattr(track, 'language', ''),
            1 if final_is_favorite else 0,
            getattr(track, 'year', 0),
        ))

    if track.has_cover and track.cover_data:
        _save_cover(track.filepath, track.cover_data)


def update_track_analysis(filepath: str, tempo: float, energy: float, mood: float,
                          zero_crossing_rate: float = 0.0,
                          spectral_flux: float = 0.0,
                          hpss_ratio: float = 0.0):
    """Update only the analysis fields for a track."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE library SET
                tempo = ?,
                energy = ?,
                mood = ?,
                zero_crossing_rate = ?,
                spectral_flux = ?,
                hpss_ratio = ?
            WHERE filepath = ?
        """, (tempo, energy, mood, zero_crossing_rate, spectral_flux, hpss_ratio, filepath))


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
    """Delete a track from the library (and cover file)."""
    # Validate filepath for path traversal
    from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
    music_folder = get_music_folder()
    if not is_safe_filepath(filepath, music_folder):
        print(f"[delete_track] ОТМЕНЕНО: filepath небезопасен — {filepath}")
        return

    from musicplayer.core.db.cache import delete_cover
    delete_cover(filepath)

    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM library WHERE filepath = ?", (filepath,))
        if cursor.rowcount > 0:
            print(f"[delete_track] Удалён из БД: {filepath}")
        else:
            print(f"[delete_track] Не найден в БД: {filepath}")


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
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                   mtime,
                   COALESCE(language, '') as language,
                   COALESCE(is_favorite, 0) as is_favorite,
                   COALESCE(year, 0) as year
            FROM library
        """)
        rows = cursor.fetchall()
    return [_row_to_track(row) for row in rows]


def ensure_cover_for_track(filepath: str) -> Optional[bytes]:
    """
    Ensure cover art is available for a track.
    1. Check if cover exists in file cache — return it if so.
    2. If not, check DB — if has_cover=0 skip mutagen.
    3. If DB says cover exists, extract from file.
    4. If found, save to cache and update DB.
    5. Return cover bytes or None if no cover exists.
    """
    # Step 1: Check cache
    cached = _load_cover(filepath)
    if cached:
        return cached

    # Step 2: Quick DB check — skip mutagen if DB already says no cover
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT has_cover FROM library WHERE filepath = ?", (filepath,))
            row = cursor.fetchone()
            if row is not None and not row[0]:
                return None
    except Exception as e:
        print(f"ensure_cover_for_track: failed to check has_cover in DB — {e}")
        pass

    # Step 3: Extract from file
    track_info = extract_metadata(filepath)
    if track_info and track_info.has_cover and track_info.cover_data:
        # Step 4: Save to cache and update DB
        _save_cover(filepath, track_info.cover_data)
        try:
            with get_connection() as conn:
                conn.execute("""
                    UPDATE library SET has_cover = 1
                    WHERE filepath = ?
                """, (filepath,))
        except Exception as e:
            print(f"ensure_cover_for_track: failed to update has_cover flag — {e}")
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
        except Exception as e:
            print(f"extract_metadata: failed to get file mtime — {e}")
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

        # Detect language: prefer metadata tag, fall back to unicode range
        language = _get_language_tag(tags) if hasattr(audio, 'tags') and audio.tags is not None else ''
        if not language:
            language = _detect_language(title + ' ' + artist)

        # Extract year from metadata
        year = _extract_year(tags) if hasattr(audio, 'tags') and audio.tags is not None else 0

        return TrackInfo(
            filepath=filepath,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            has_cover=cover_data is not None,
            cover_data=cover_data,
            genre=genre,
            language=language,
            is_lossless=is_lossless,
            bitrate=bitrate,
            mtime=file_mtime,
            year=year,
        )

    except Exception as e:
        print(f"extract_metadata: failed to parse audio file — {e}")
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


# Unicode range patterns for language detection
_UNICODE_CYRILLIC = re.compile(r'[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]')
_UNICODE_CJK = re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF]')
_UNICODE_JAPANESE = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
_UNICODE_KOREAN = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF]')
_UNICODE_ARABIC = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
_UNICODE_HEBREW = re.compile(r'[\u0590-\u05FF]')
_UNICODE_GREEK = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
_UNICODE_THAI = re.compile(r'[\u0E00-\u0E7F]')
_UNICODE_DEVANAGARI = re.compile(r'[\u0900-\u097F]')


def _detect_language(text: str) -> str:
    """Detect language from text using unicode ranges. Returns ISO 639-1 code."""
    if not text:
        return ''
    # Count non-ASCII script chars
    cyrillic = len(_UNICODE_CYRILLIC.findall(text))
    cjk = len(_UNICODE_CJK.findall(text))
    japanese = len(_UNICODE_JAPANESE.findall(text))
    korean = len(_UNICODE_KOREAN.findall(text))
    arabic = len(_UNICODE_ARABIC.findall(text))
    hebrew = len(_UNICODE_HEBREW.findall(text))
    greek = len(_UNICODE_GREEK.findall(text))
    thai = len(_UNICODE_THAI.findall(text))
    devanagari = len(_UNICODE_DEVANAGARI.findall(text))
    total = cyrillic + cjk + japanese + korean + arabic + hebrew + greek + thai + devanagari
    if total == 0:
        return 'en'
    lang_scores = {
        'ja': japanese + (cjk if japanese > 0 else 0),
        'ko': korean,
        'zh': cjk,
        'ru': cyrillic,
        'ar': arabic,
        'he': hebrew,
        'el': greek,
        'th': thai,
        'hi': devanagari,
    }
    return max(lang_scores, key=lang_scores.get)


# ISO 639-2 (3-letter) → ISO 639-1 (2-letter) mapping for common languages
_ISO639_2_TO_1 = {
    'ara': 'ar', 'bul': 'bg', 'cat': 'ca', 'ces': 'cs', 'cze': 'cs',
    'chi': 'zh', 'zho': 'zh', 'hrv': 'hr', 'dan': 'da', 'dut': 'nl',
    'nld': 'nl', 'eng': 'en', 'est': 'et', 'fin': 'fi', 'fre': 'fr',
    'fra': 'fr', 'deu': 'de', 'ger': 'de', 'ell': 'el', 'gre': 'el',
    'heb': 'he', 'hin': 'hi', 'hun': 'hu', 'isl': 'is', 'ind': 'id',
    'ita': 'it', 'jpn': 'ja', 'kor': 'ko', 'lav': 'lv', 'lit': 'lt',
    'msa': 'ms', 'may': 'ms', 'nor': 'no', 'pol': 'pl', 'por': 'pt',
    'ron': 'ro', 'rum': 'ro', 'rus': 'ru', 'srp': 'sr', 'slo': 'sk',
    'slk': 'sk', 'slv': 'sl', 'spa': 'es', 'swe': 'sv', 'tha': 'th',
    'tur': 'tr', 'ukr': 'uk', 'vie': 'vi',
}


def _get_language_tag(tags) -> str:
    """Extract language from audio file metadata tags.
    Returns ISO 639-1 2-letter code, or empty string if not found."""
    try:
        # ID3 tags (MP3) — TLAN frame
        if hasattr(tags, 'getall'):
            val = tags.getall('TLAN')
            if val:
                lang = str(val[0]).strip()
                if len(lang) == 3:
                    return _ISO639_2_TO_1.get(lang.lower(), lang.lower())
                return lang.lower()[:2]

        # Vorbis comments (FLAC, OGG)
        if hasattr(tags, '__getitem__'):
            try:
                val = tags['language']
                if val:
                    lang = str(val[0]).strip() if isinstance(val, list) else str(val).strip()
                    if len(lang) == 3:
                        return _ISO639_2_TO_1.get(lang.lower(), lang.lower())
                    return lang.lower()[:2]
            except (KeyError, IndexError):
                pass

        # MP4/M4A — no standard language tag for content; fall through
    except Exception as e:
        print(f"_get_language_tag: failed to extract language tag — {e}")
        pass
    return ''


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
                    return _join_tag_values(val, key)

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
                    return _join_tag_values(val, key)
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
                    return _join_tag_values(val, key)
            except (KeyError, IndexError):
                pass

    except Exception as e:
        print(f"_get_tag: failed to extract tag '{key}' — {e}")
        pass

    # Return empty string (not filename) for non-title fields
    if key != 'title':
        return ""
    return Path(filepath).stem


def _normalize_genre_separators(genre: str) -> str:
    """Normalise genre separators to semicolons: / and , become ; spaces are trimmed."""
    if not genre:
        return genre
    genre = genre.replace('/', ';').replace(',', ';')
    parts = [p.strip() for p in genre.split(';') if p.strip()]
    return ';'.join(parts)


def _join_tag_values(val, key: str) -> str:
    """Join multiple tag values; for genre join with ';', otherwise take first."""
    parts = [str(v) for v in (val if isinstance(val, list) else [val]) if v]
    if not parts:
        return ''
    if key == 'genre':
        return _normalize_genre_separators(';'.join(parts))
    return parts[0]


def _extract_year(tags) -> int:
    """Extract 4-digit year from audio file metadata tags."""
    date_str = ""
    try:
        if hasattr(tags, 'getall'):
            for frame_id in ['TDRC', 'TYER', 'TDRL']:
                val = tags.getall(frame_id)
                if val:
                    date_str = str(val[0]).strip()
                    break
        if not date_str and hasattr(tags, '__getitem__'):
            for key in ('date', 'year'):
                try:
                    val = tags[key]
                    if val:
                        date_str = str(val[0] if isinstance(val, list) else val).strip()
                        break
                except (KeyError, IndexError):
                    pass
        if not date_str and hasattr(tags, '__getitem__'):
            try:
                val = tags['©day']
                if val:
                    date_str = str(val[0] if isinstance(val, list) else val).strip()
            except (KeyError, IndexError):
                pass
    except Exception as e:
        print(f"_extract_year: failed to extract year — {e}")
        pass
    if not date_str:
        return 0
    m = re.search(r'\b(\d{4})\b', date_str)
    return int(m.group(1)) if m else 0


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

    except Exception as e:
        print(f"_extract_cover: failed to extract cover art — {e}")
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
                   COALESCE(mood, 0.0) as mood,
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                   COALESCE(spectral_flux, 0.0) as spectral_flux,
                    mtime,
                    COALESCE(language, '') as language,
                    COALESCE(is_favorite, 0) as is_favorite,
                    COALESCE(year, 0) as year
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
                   COALESCE(hpss_ratio, 0.0) as hpss_ratio,
                   COALESCE(zero_crossing_rate, 0.0) as zero_crossing_rate,
                    COALESCE(spectral_flux, 0.0) as spectral_flux,
                    mtime,
                    COALESCE(language, '') as language,
                    COALESCE(is_favorite, 0) as is_favorite,
                    COALESCE(year, 0) as year
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
            except Exception as e:
                print(f"get_tracks_by_folder: failed to check parent directory — {e}")
                pass

        return results


def get_folder_filepaths(folder_path: str):
    """Get all filepaths in the library for a specific folder."""
    import os as os_module

    folder = Path(folder_path)
    like_pattern = str(folder) + os_module.sep + "%"

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT filepath FROM library WHERE filepath LIKE ?",
            (like_pattern,)
        )
        results: set = set()
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