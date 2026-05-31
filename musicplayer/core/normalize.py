"""
Metadata normalization module.
Normalizes titles, artists, and albums by fixing spacing and handling special replacements.
"""

import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from musicplayer.core.db import TrackInfo


def _normalize_text_spacing(text: str) -> str:
    """Add space between letter and opening parenthesis: a( => a ("""
    if not text:
        return text
    return re.sub(r'([a-zA-Zа-яА-ЯёЁ])(\()', r'\1 \2', text)


def _normalize_artist_slash(text: str) -> str:
    """
    Replace / with & in artist field when both sides have 3+ non-space characters.
    Examples:
    - AC/DC - ignored (less than 3 chars each side)
    - Artist1 /Artist2 - ignored (space before /)
    - Artist1/ Artist2 - ignored (space after /)
    - Artist1/Artist2 => Artist1 & Artist2
    - Multiple slashes: A/B/C/D => A & B & C & D
    """
    if not text:
        return text

    if '/' not in text:
        return text

    parts = text.split('/')
    if len(parts) < 2:
        return text

    result_parts = [parts[0].strip()]

    for i in range(1, len(parts)):
        left = result_parts[-1]
        right = parts[i].strip()

        if len(left) >= 3 and len(right) >= 3:
            result_parts[-1] = left
            result_parts.append(right)
            result_parts.insert(-1, '&')
        else:
            result_parts[-1] = left + '/' + right

    return ' '.join(result_parts)


def _normalize_field(text: Optional[str]) -> Optional[str]:
    """Apply spacing normalization to a field."""
    if not text:
        return text
    return _normalize_text_spacing(text)


def _normalize_artist(text: Optional[str]) -> Optional[str]:
    """Apply spacing and slash normalization to artist field."""
    if not text:
        return text
    text = _normalize_text_spacing(text)
    text = _normalize_artist_slash(text)
    return text


def normalize_title(text: Optional[str]) -> Optional[str]:
    """Normalize title: add space before parenthesis."""
    if not text:
        return text
    return _normalize_text_spacing(text)


def normalize_artist(text: Optional[str]) -> Optional[str]:
    """Normalize artist: add space before parenthesis + replace / with &."""
    if not text:
        return text
    text = _normalize_text_spacing(text)
    text = _normalize_artist_slash(text)
    return text


def normalize_album(text: Optional[str]) -> Optional[str]:
    """Normalize album: add space before parenthesis."""
    if not text:
        return text
    return _normalize_text_spacing(text)


def normalize_track_metadata(
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    genre: Optional[str] = None
) -> dict:
    """Normalize all metadata fields using appropriate methods for each."""
    result = {}

    if title is not None:
        result['title'] = normalize_title(title)

    if artist is not None:
        result['artist'] = normalize_artist(artist)

    if album is not None:
        result['album'] = normalize_album(album)

    if genre is not None:
        result['genre'] = genre

    return result


def normalize_all_in_database():
    """Normalize all tracks in the database. (Deprecated - normalization now happens on scan)"""
    pass


def normalize_track(track) -> "TrackInfo":
    """Normalize a TrackInfo object using appropriate methods for each field."""
    from musicplayer.core.db import TrackInfo

    return TrackInfo(
        filepath=track.filepath,
        title=normalize_title(track.title),
        artist=normalize_artist(track.artist),
        album=normalize_album(track.album),
        duration=track.duration,
        has_cover=track.has_cover,
        cover_data=track.cover_data,
        genre=track.genre,
        is_lossless=track.is_lossless,
        bitrate=track.bitrate,
        mtime=track.mtime,
        tempo=getattr(track, 'tempo', 0.0),
        energy=getattr(track, 'energy', 0.0),
        mood=getattr(track, 'mood', 0.0),
        zero_crossing_rate=getattr(track, 'zero_crossing_rate', 0.0),
        spectral_flux=getattr(track, 'spectral_flux', 0.0),
        hpss_ratio=getattr(track, 'hpss_ratio', 0.0),
    )


def normalize_metadata(title: Optional[str] = None, artist: Optional[str] = None,
                       album: Optional[str] = None, genre: Optional[str] = None) -> dict:
    """Normalize metadata fields using appropriate methods for each field."""
    result = {}

    if title is not None:
        result['title'] = normalize_title(title)

    if artist is not None:
        result['artist'] = normalize_artist(artist)

    if album is not None:
        result['album'] = normalize_album(album)

    if genre is not None:
        result['genre'] = genre

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        normalize_all_in_database()
    else:
        print("Usage: python normalize.py --run")