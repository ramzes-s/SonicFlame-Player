"""
Helper Utilities Module

Common utility functions for formatting, validation, etc.
"""

from pathlib import Path
from PySide6.QtGui import QColor # ADDED
import numpy as np # ADDED
from musicplayer import config as cfg


# Supported audio file extensions for quick validation
SUPPORTED_AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.m4a', '.mp4',
}


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value from its actual range to a 0-1 range."""
    # Clip the value to be within the defined min/max bounds
    clipped_value = np.clip(value, min_val, max_val)
    # Perform normalization
    return (clipped_value - min_val) / (max_val - min_val)

def get_color_from_features(tempo: float, energy: float, mood: float) -> QColor:
    """
    Converts tempo, energy, and mood values into a QColor using HSV.
    This version normalizes the features from their real-world observed
    ranges before mapping them to color components.

    - Hue (the color itself) is from Mood.
    - Saturation ("white tint") is from Energy. Low energy = more tinted.
    - Value (brightness) is from Tempo. All colors are bright.
    """
    # Use ranges from config
    min_mood, max_mood = cfg.MIN_MOOD, cfg.MAX_MOOD
    min_tempo, max_tempo = cfg.MIN_TEMPO, cfg.MAX_TEMPO
    min_energy, max_energy = cfg.MIN_ENERGY, cfg.MAX_ENERGY

    # 2. Normalize each feature from its actual range to a [0, 1] scale.
    norm_mood = _normalize(mood, min_mood, max_mood)
    norm_tempo = _normalize(tempo, min_tempo, max_tempo)
    norm_energy = _normalize(energy, min_energy, max_energy)

    # 3. Map the normalized [0, 1] values to HSV components.
    # Hue from Mood (full 0-359 degree range)
    hue = int(norm_mood * 359)

    # Saturation from Energy (controls the "white tint")
    # Low energy = lower saturation (more white). Subtle range.
    saturation = int(180 + norm_energy * 75) # Range [180, 255]

    # Value (Brightness) from Tempo
    # Keep in a high and narrow range to ensure all colors are bright.
    value = int(220 + norm_tempo * 35) # Range [220, 255]

    return QColor.fromHsv(hue, saturation, value)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Examples:
        0 -> "0:00"
        65 -> "1:05"
        3661 -> "61:01"
    """
    if seconds <= 0:
        return "0:00"
    
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    
    return f"{minutes}:{seconds:02d}"


def is_audio_file(filepath: str) -> bool:
    """Check if a file has a supported audio extension."""
    return Path(filepath).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Remove path components and return just the filename."""
    return Path(filename).name


def get_folder_path(filepath: str) -> str:
    """Get the parent folder path for a file."""
    return str(Path(filepath).parent)
