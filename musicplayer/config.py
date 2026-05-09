"""
Application Configuration

Single source of truth for global constants like accent colors.
"""

# Application version
APP_VERSION = "0.9.5"

# Global accent color — change here to update the entire app
ACCENT_COLOR = "#ed6a02"

# Global colors
TEXT_COLOR = "#FFFFFF"
DIVIDER_COLOR = "rgba(80, 80, 80, 0.5)"


def get_accent_color() -> str:
    """Get the current accent color (always reads the live value)."""
    return ACCENT_COLOR
