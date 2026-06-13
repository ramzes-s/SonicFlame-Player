"""
Recommendations Module — Parameter Reference / Справочник параметров

GENRE_WEIGHT=0.30 — вес жанра; основан на метках из метаданных / genre tags from metadata
AUDIO_WEIGHT_TEMPO=0.30 / ENERGY=0.20 / MOOD=0.20 / ZCR=0.15 / FLUX=0.30 / HPSS=0.15 — веса аудиоизмерений / audio dim weights
PENALTY_ARTIST=-0.08 — штраф за одного и того же исполнителя (избегаем дублей) / same-artist penalty
PARTIAL_GENRE_BOOST_FACTOR=1.15 — усилитель при частичном совпадении жанров / partial match boost
TOL_BASELINE=0.20 — базовая чувствительность, precision масштабирует от 50% до 25% / base sensitivity
SIMILARITY_THRESHOLD_BASE=0.5 — база порога отбора, растёт с precision / selection threshold base
MAX_GENRES_FOR_COMPARISON=2   — макс. число жанров для сравнения / max genres to compare

Provides algorithms for finding similar tracks based on genre and audio features.
"""

import sys
import json
import functools
from pathlib import Path
from typing import List, Optional
import numpy as np
from musicplayer import config
from musicplayer.core.db import TrackInfo
from musicplayer.core import settings as app_settings
import random

# All constants sourced from config.py (single source of truth)
REC_TEMPO_MIN = config.TEMPO_MIN
REC_TEMPO_MAX = config.TEMPO_MAX
REC_FLUX_MIN = config.FLUX_MIN
REC_FLUX_MAX = config.FLUX_MAX
HPSS_NORM_MIN = config.HPSS_NORM_MIN
HPSS_NORM_MAX = config.HPSS_NORM_MAX


def get_similarity_threshold() -> float:
    """Selection threshold: 0.35 + precision/100."""
    return config.SIMILARITY_THRESHOLD_BASE + (app_settings.get_similarity_precision() / 100.0)

def get_dim_tolerances(precision: int) -> dict:
    """Per-dimension tolerances = TOL_BASELINE * 0.5 * (1 - precision/40*0.5).
    At precision=0 → 50% of TOL_BASELINE; at precision=40 → 25% of TOL_BASELINE.
    scale formula: 0.5 * (1 - precision/40 * 0.5) → [0.5, 0.25]."""
    v = config.TOL_BASELINE * 0.5 * (1.0 - (precision / 40.0) * 0.5)
    return {'tempo': v, 'energy': v, 'mood': v, 'zcr': v, 'flux': v, 'hpss': v}


def _normalize_metric(value: float, min_val: float, max_val: float) -> float:
    """Normalize a metric to a 0-1 range based on real min/max values."""
    if max_val - min_val == 0:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def _get_list_from_string(s: Optional[str]) -> List[str]:
    """Helper to convert a semicolon-separated string to a list."""
    if not s:
        return []
    items = [item.strip() for item in s.split(';') if item.strip()]
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


def _normalize_genre_for_compare(g: str) -> str:
    """Normalize genre string for comparison: lowercase, hyphens→spaces, strip."""
    return g.lower().replace('-', ' ').strip()


def _dim_similarity(v1: float, v2: float, threshold: float) -> float:
    """Similarity for one dimension: 1.0 − diff/threshold, floored at 0."""
    return max(0.0, 1.0 - abs(v1 - v2) / threshold)


def _normalize_track(track: TrackInfo):
    """Normalise a track's 6 audio dimensions into [0,1] space.
    Returns dict with keys 'tempo','energy','mood','zcr','flux','hpss'."""
    return {
        'tempo':  _normalize_metric(track.tempo, REC_TEMPO_MIN, REC_TEMPO_MAX),
        'energy': track.energy,
        'mood':   track.mood,
        'zcr':    track.zero_crossing_rate,
        'flux':   max(REC_FLUX_MIN, min(track.spectral_flux / REC_FLUX_MAX, 1.0)),
        'hpss':   np.clip((track.hpss_ratio - HPSS_NORM_MIN) / (HPSS_NORM_MAX - HPSS_NORM_MIN), 0, 1),
    }


def _compute_dimsims(n1: dict, n2: dict, tols: dict) -> dict:
    """Compute per-dim similarities from two normalised dicts and tolerances."""
    sims = {}
    for key in ('tempo','energy','mood','zcr','flux','hpss'):
        sims[key] = _dim_similarity(n1[key], n2[key], tols[key])
    return sims


def calculate_similarity(track1: TrackInfo, track2: TrackInfo, dim_tols: dict = None, lang_filter_mode: str = "off") -> float:
    """
    Calculates a similarity score between two tracks.
    
    Score is a weighted sum of genre + 6 audio dim similarities
    (no normalisation to 1.0 — weights and threshold are tuned independently).
    dim_tols: dict with keys 'tempo','energy','mood','zcr','flux','hpss' (values 0-1).
    lang_filter_mode: "off" — skip, "penalty" — apply PENALTY_LANGUAGE, "exclude" — return 0.0.
    """
    if track1.filepath == track2.filepath:
        return 0.1
    
    if dim_tols is None:
        dim_tols = get_dim_tolerances(app_settings.get_similarity_precision())

    # ---- 0. Language Exclude (early exit) ----
    if lang_filter_mode == "exclude" and track1.language and track2.language:
        if track1.language != track2.language:
            return 0.0

    genre_score = 0.0
    artist_penalty = 0.0

    # ---- 1. Genre ----
    raw1 = _get_list_from_string(track1.genre)[:config.MAX_GENRES_FOR_COMPARISON]
    raw2 = _get_list_from_string(track2.genre)[:config.MAX_GENRES_FOR_COMPARISON]

    if raw1 and raw2:
        genre_map = _load_genre_map()
        groups = _load_genre_groups()

        norm1 = [genre_map.get(g, g) for g in raw1]
        norm2 = [genre_map.get(g, g) for g in raw2]

        used1 = [False] * len(norm1)
        used2 = [False] * len(norm2)
        total = 0.0

        for i, g1 in enumerate(norm1):
            for j, g2 in enumerate(norm2):
                if used2[j]:
                    continue
                if _normalize_genre_for_compare(g1) == _normalize_genre_for_compare(g2):
                    total += 1.0
                    used1[i] = True
                    used2[j] = True
                    break

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
            genre_score = min(1.0, genre_score * config.PARTIAL_GENRE_BOOST_FACTOR)
    elif not raw1 and not raw2:
        genre_score = 0.1

    # ---- 2. Audio Profile (6 dimensions) ----
    n1 = _normalize_track(track1)
    n2 = _normalize_track(track2)
    sims = _compute_dimsims(n1, n2, dim_tols)

    # ---- 3. Zero-kill: any dim outside tolerance → reject (precision > 20) ----
    if dim_tols is not None:
        prec = int((1.0 - dim_tols['tempo'] / (config.TOL_BASELINE * 0.5)) * 80 + 0.5)
        if prec > 20 and any(s == 0.0 for s in sims.values()):
            return 0.0

    # ---- 4. Weighted sum (no normalisation to 1.0) ----
    total_similarity = max(0.0,
        config.GENRE_WEIGHT * genre_score +
        config.AUDIO_WEIGHT_TEMPO * sims['tempo'] +
        config.AUDIO_WEIGHT_ENERGY * sims['energy'] +
        config.AUDIO_WEIGHT_MOOD * sims['mood'] +
        config.AUDIO_WEIGHT_ZCR * sims['zcr'] +
        config.AUDIO_WEIGHT_FLUX * sims['flux'] +
        config.AUDIO_WEIGHT_HPSS * sims['hpss'])

    # ---- 5. Artist Penalty ----
    artists1 = _get_list_from_string(track1.artist)
    artists2 = _get_list_from_string(track2.artist)
    if artists1 and artists2:
        if set(artists1).intersection(set(artists2)):
            total_similarity = max(0.0, total_similarity + config.PENALTY_ARTIST)

    # ---- 6. Language Penalty ----
    if lang_filter_mode == "penalty" and track1.language and track2.language:
        if track1.language != track2.language:
            total_similarity = max(0.0, total_similarity + config.PENALTY_LANGUAGE)

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

    prec = app_settings.get_similarity_precision()
    dim_tols = get_dim_tolerances(prec)
    lang_filter_mode = app_settings.AppSettings().language_filter_mode

    scale = 0.5 * (1.0 - (prec / 40.0) * 0.5)
    print(f"[Recommendations] reference → tempo={current_track.tempo:.1f} energy={current_track.energy:.3f} mood={current_track.mood:.3f} zcr={current_track.zero_crossing_rate:.3f} flux={current_track.spectral_flux:.2f} hpss={current_track.hpss_ratio:.3f} lang={current_track.language}")
    print(f"[Recommendations] precision={prec} | selection≥{min_similarity_threshold:.2f} | scale={scale:.3f} (BL×{scale:.3f}) | tol={scale * config.TOL_BASELINE:.3f} | lang_filter={lang_filter_mode}")

    similarities = []
    ref_norm = _normalize_track(current_track)
    for track in all_tracks:
        if track.filepath == current_track.filepath:
            continue

        similarity = calculate_similarity(current_track, track, dim_tols, lang_filter_mode=lang_filter_mode)
        if similarity >= min_similarity_threshold:
            similarities.append((similarity, track))
            cand_norm = _normalize_track(track)
            sims = _compute_dimsims(ref_norm, cand_norm, dim_tols)
            print(f"[Recommendations]   candidate → {similarity:.3f} | "
                  f"tempo={track.tempo:.1f} ({sims['tempo']:.2f}) energy={track.energy:.3f} ({sims['energy']:.2f}) "
                  f"mood={track.mood:.3f} ({sims['mood']:.2f}) zcr={track.zero_crossing_rate:.3f} ({sims['zcr']:.2f}) "
                  f"flux={track.spectral_flux:.2f} ({sims['flux']:.2f}) hpss={track.hpss_ratio:.3f} ({sims['hpss']:.2f}) "
                  f"lang={track.language}")

    # Sort by similarity score in descending order
    similarities.sort(key=lambda x: x[0], reverse=True)

    # Apply shuffle to the top 'limit' tracks (NEW)
    if similarities:
        # Take top 'limit' tracks
        top_similar = similarities[:limit]
        random.shuffle(top_similar) # Shuffle them
        return [track for score, track in top_similar]
    
    return [] # Return empty list if no similar tracks found