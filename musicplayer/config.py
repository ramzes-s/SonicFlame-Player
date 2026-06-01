"""
Application Configuration

Single source of truth for global constants like accent colors and cache paths.
"""

import sys
from pathlib import Path

# Application version
APP_VERSION = "1.1.5"

# Debug logging toggle — set False to disable file logging
LOG_DEBUG = True

# Global accent color — change here to update the entire app
ACCENT_COLOR = "#ed6a02"

# Database version for schema compatibility checking
DB_VERSION = 1

# Global colors
TEXT_COLOR = "#FFFFFF"
DIVIDER_COLOR = "rgba(80, 80, 80, 0.5)"

# Audio analysis duration (seconds)
ANALYSIS_DURATION = 30
# Audio feature normalization ranges (single source for all modules)
TEMPO_MIN = 50.0
TEMPO_MAX = 190.0
ENERGY_MIN = 0.01
ENERGY_MAX = 1.0
MOOD_MIN = 0.01
MOOD_MAX = 1.0
FLUX_MIN = 0.0
FLUX_MAX = 140.0
HPSS_NORM_MIN = 0.5
HPSS_NORM_MAX = 1.0



# Tolerance baseline — единая константа чувствительности для всех 6 измерений.
# Итоговый допуск = TOL_BASELINE * 0.5 * (1 − precision/40 × 0.5).
# При precision=0 → 50% от baseline; при precision=40 → 25% от baseline.
TOL_BASELINE = 0.36

# Recommendation weights and thresholds
GENRE_WEIGHT = 0.4  # жанр
PENALTY_ARTIST = -0.08
PENALTY_LANGUAGE = -0.3

# Веса измерений аудиопрофиля (взвешенное геометрическое среднее)
AUDIO_WEIGHT_TEMPO  = 0.30  # BPM — базовый темпоритм
AUDIO_WEIGHT_ENERGY = 0.25  # onset strength — интенсивность/плотность звука
AUDIO_WEIGHT_MOOD   = 0.22  # spectral centroid — яркость/эмоциональный окрас
AUDIO_WEIGHT_ZCR    = 0.20  # zero-crossing rate — шумность/резкость
AUDIO_WEIGHT_FLUX   = 0.25  # spectral flux — изменчивость/хаотичность
AUDIO_WEIGHT_HPSS   = 0.22  # harmonic-percussive ratio — ритмичность vs мелодичность


PARTIAL_GENRE_BOOST_FACTOR = 1.15
MAX_GENRES_FOR_COMPARISON = 2
SIMILARITY_THRESHOLD_BASE = 0.9

# Project root directory (resolves correctly in dev and frozen modes)
if getattr(sys, 'frozen', False):
    PROJECT_DIR = Path(sys.executable).parent
else:
    PROJECT_DIR = Path(__file__).parent.parent

# Cache directory and subpaths
CACHE_DIR = PROJECT_DIR / ".cache"
DB_PATH = CACHE_DIR / "musicplayer.db"
COVERS_DIR = CACHE_DIR / "covers"
ARTIST_COLLAGES_DIR = CACHE_DIR / "artist_collages"
SETTINGS_FILE = CACHE_DIR / "settings.json"
COL_WIDTHS_FILE = CACHE_DIR / "library_col_widths.json"


def get_accent_color() -> str:
    """Get the current accent color (always reads the live value)."""
    return ACCENT_COLOR
