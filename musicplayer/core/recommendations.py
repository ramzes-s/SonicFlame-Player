"""
Recommendations Module

Provides algorithms for finding similar tracks based on various criteria
(genre, audio features).
"""

import math
import sys
import json
import functools
from pathlib import Path
from typing import List, Optional
from musicplayer.core.db import TrackInfo
from musicplayer.core import settings as app_settings
from musicplayer import config as cfg
import random

# --- Weights and thresholds ---
WEIGHT_GENRE = 0.36
WEIGHT_TEMPO = 0.34
WEIGHT_ENERGY = 0.24
WEIGHT_MOOD = 0.14
PENALTY_ARTIST = -0.1

# Use ranges from config
MIN_TEMPO = cfg.MIN_TEMPO
MAX_TEMPO = cfg.MAX_TEMPO
MIN_ENERGY = cfg.MIN_ENERGY
MAX_ENERGY = cfg.MAX_ENERGY
MIN_MOOD = cfg.MIN_MOOD
MAX_MOOD = cfg.MAX_MOOD

# Other constants
METRIC_SINGLE_DIM_THRESHOLD_FOR_SIMILARITY_SCORE = 0.14

PARTIAL_GENRE_BOOST_FACTOR = 1.15
MAX_GENRES_FOR_COMPARISON = 2
SIMILARITY_THRESHOLD_BASE = 0.65


def get_similarity_threshold() -> float:
    """Dynamic threshold from user settings: 0.60 + (precision / 100)."""
    return SIMILARITY_THRESHOLD_BASE + (app_settings.get_similarity_precision() / 100.0)


def _normalize_metric(value: float, min_val: float, max_val: float) -> float:
    """Normalize a metric to a 0-1 range based on real min/max values."""
    if max_val - min_val == 0:
        return 0.0 # Avoid division by zero if range is 0
    return (value - min_val) / (max_val - min_val)


def _get_list_from_string(s: Optional[str]) -> List[str]:
    """Helper to convert a comma/semicolon separated string to a list."""
    if not s:
        return []
    # Split by comma or semicolon, then strip whitespace and filter empty strings
    items = [item.strip() for item in s.replace(';', ',').split(',') if item.strip()]
    # Preserve order while removing duplicates
    return list(dict.fromkeys(items))


def _get_genre_path(filename: str) -> Path:
    """Resolve path to a file in res/genres/ (works in dev and frozen builds)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "res" / "genres" / filename
    return Path(__file__).resolve().parent.parent.parent / "res" / "genres" / filename


@functools.lru_cache(maxsize=1)
def _load_genre_groups() -> dict[str, int]:
    """Load genre_groups.json and return a dict: canonical_genre -> group_index."""
    path = _get_genre_path("genre_groups.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for idx, group in enumerate(data["groups"]):
        for genre in group["genres"]:
            result[genre] = idx
    return result


@functools.lru_cache(maxsize=1)
def _load_genre_map() -> dict[str, str]:
    """Load genre_map.json and return a dict: raw_name -> canonical_name."""
    path = _get_genre_path("genre_map.json")
    return json.loads(path.read_text(encoding="utf-8"))


def calculate_similarity(track1: TrackInfo, track2: TrackInfo) -> float:
    """
    Calculates a similarity score between two tracks based on genre and individual audio features,
    applying a penalty for matching artists.
    Score is between 0.0 and 1.0, where 1.0 is identical.
    """
    if track1.filepath == track2.filepath: # A track is always 100% similar to itself
        return 1.0
    
    genre_score = 0.0
    tempo_score = 0.0
    energy_score = 0.0
    mood_score = 0.0
    artist_penalty = 0.0

    # 1. Genre Similarity (Weighted: WEIGHT_GENRE)
    raw1 = _get_list_from_string(track1.genre)[:MAX_GENRES_FOR_COMPARISON]
    raw2 = _get_list_from_string(track2.genre)[:MAX_GENRES_FOR_COMPARISON]

    if raw1 and raw2:
        genre_map = _load_genre_map()
        groups = _load_genre_groups()

        norm1 = [genre_map.get(g, g) for g in raw1]
        norm2 = [genre_map.get(g, g) for g in raw2]

        used1 = [False] * len(norm1)
        used2 = [False] * len(norm2)
        total = 0.0

        # Phase 1: exact matches (weight 1.0)
        for i, g1 in enumerate(norm1):
            for j, g2 in enumerate(norm2):
                if used2[j]:
                    continue
                if g1 == g2:
                    total += 1.0
                    used1[i] = True
                    used2[j] = True
                    break

        # Phase 2: group matches for remaining genres (weight 0.9)
        for i, g1 in enumerate(norm1):
            if used1[i]:
                continue
            for j, g2 in enumerate(norm2):
                if used2[j]:
                    continue
                g1_grp = groups.get(g1, -1)
                g2_grp = groups.get(g2, -1)
                if g1_grp != -1 and g1_grp == g2_grp:
                    total += 0.9
                    used1[i] = True
                    used2[j] = True
                    break

        denom = max(len(norm1), len(norm2))
        genre_score = total / denom if denom else 0.0
        if 0 < genre_score < 1.0:
            genre_score = min(1.0, genre_score * PARTIAL_GENRE_BOOST_FACTOR)
    elif not raw1 and not raw2:
        genre_score = 0.1

    # 2. Audio Features Similarity (Individual Scores)
    # Normalize tempo, energy, mood to 0-1 range using real min/max
    norm_tempo1 = _normalize_metric(track1.tempo, MIN_TEMPO, MAX_TEMPO)
    norm_energy1 = _normalize_metric(track1.energy, MIN_ENERGY, MAX_ENERGY)
    norm_mood1 = _normalize_metric(track1.mood, MIN_MOOD, MAX_MOOD)

    norm_tempo2 = _normalize_metric(track2.tempo, MIN_TEMPO, MAX_TEMPO)
    norm_energy2 = _normalize_metric(track2.energy, MIN_ENERGY, MAX_ENERGY)
    norm_mood2 = _normalize_metric(track2.mood, MIN_MOOD, MAX_MOOD)

    # Calculate individual similarity scores for each metric
    # Tempo score
    tempo_diff = abs(norm_tempo1 - norm_tempo2)
    tempo_score = max(0.0, 1.0 - (tempo_diff / METRIC_SINGLE_DIM_THRESHOLD_FOR_SIMILARITY_SCORE))

    # Energy score
    energy_diff = abs(norm_energy1 - norm_energy2)
    energy_score = max(0.0, 1.0 - (energy_diff / METRIC_SINGLE_DIM_THRESHOLD_FOR_SIMILARITY_SCORE))

    # Mood score
    mood_diff = abs(norm_mood1 - norm_mood2)
    mood_score = max(0.0, 1.0 - (mood_diff / METRIC_SINGLE_DIM_THRESHOLD_FOR_SIMILARITY_SCORE))

    # 3. Artist Penalty
    artists1 = _get_list_from_string(track1.artist)
    artists2 = _get_list_from_string(track2.artist)

    if artists1 and artists2:
        common_artists = set(artists1).intersection(set(artists2))
        if common_artists:
            artist_penalty = PENALTY_ARTIST

    # 4. Combined Similarity Score
    total_similarity = (
        (WEIGHT_GENRE * genre_score) +
        (WEIGHT_TEMPO * tempo_score) +
        (WEIGHT_ENERGY * energy_score) +
        (WEIGHT_MOOD * mood_score) +
        artist_penalty
    )
    
    # NEW: Additional filter - if mood_score is 0, the track does not fit
    if mood_score == 0.0:
        total_similarity = 0.0

    total_similarity = max(0.0, total_similarity)

    return total_similarity


def find_similar_tracks(
    current_track: TrackInfo,
    all_tracks: List[TrackInfo],
    limit: int = 10,
    min_similarity_threshold: Optional[float] = None
) -> List[TrackInfo]:
    """
    Finds tracks similar to the current_track from a list of all available tracks.

    Args:
        current_track: The track to find similar ones for.
        all_tracks: A list of all tracks in the library.
        limit: The maximum number of similar tracks to return.
        min_similarity_threshold: Minimum similarity score to be considered similar.

    Returns:
        A sorted and shuffled list of similar TrackInfo objects.
    """
    if min_similarity_threshold is None:
        min_similarity_threshold = get_similarity_threshold()

    print(f"[Recommendations] min_similarity_threshold = {min_similarity_threshold:.2f}")

    similarities = []
    for track in all_tracks:
        if track.filepath == current_track.filepath:
            continue # Don't compare a track to itself

        similarity = calculate_similarity(current_track, track)
        if similarity >= min_similarity_threshold:
            similarities.append((similarity, track))

    # Sort by similarity score in descending order
    similarities.sort(key=lambda x: x[0], reverse=True)

    # Apply shuffle to the top 'limit' tracks (NEW)
    if similarities:
        # Take top 'limit' tracks
        top_similar = similarities[:limit]
        random.shuffle(top_similar) # Shuffle them
        return [track for score, track in top_similar]
    
    return [] # Return empty list if no similar tracks found