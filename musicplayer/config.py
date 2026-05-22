"""
Application Configuration

Single source of truth for global constants like accent colors and cache paths.
"""

import sys
from pathlib import Path

# Application version
APP_VERSION = "0.9.82"

# Global accent color — change here to update the entire app
ACCENT_COLOR = "#ed6a02"

# Global colors
TEXT_COLOR = "#FFFFFF"
DIVIDER_COLOR = "rgba(80, 80, 80, 0.5)"

# Audio feature normalization ranges (from recommendations.py)
MIN_TEMPO = 40
MAX_TEMPO = 200

MIN_ENERGY = 0.01
MAX_ENERGY = 1.0

MIN_MOOD = 0.01
MAX_MOOD = 1.0

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
