"""
Application Configuration

Single source of truth for global constants like accent colors.
"""

# Application version
APP_VERSION = "0.9.56"

# Global accent color — change here to update the entire app
ACCENT_COLOR = "#ed6a02"

# Global colors
TEXT_COLOR = "#FFFFFF"
DIVIDER_COLOR = "rgba(80, 80, 80, 0.5)"

# Audio feature normalization ranges (from recommendations.py)
MIN_TEMPO = 60
MAX_TEMPO = 200

MIN_ENERGY = 0.01
MAX_ENERGY = 1.0

MIN_MOOD = 0.01
MAX_MOOD = 0.8


def get_accent_color() -> str:
    """Get the current accent color (always reads the live value)."""
    return ACCENT_COLOR
