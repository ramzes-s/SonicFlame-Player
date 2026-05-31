"""
Helper Utilities Module

Common utility functions for formatting, validation, etc.
"""

from pathlib import Path
from PySide6.QtGui import QColor
import numpy as np
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
    - Hue  ← Tempo:  green (120°) for slow → red (0°) for fast
    - Sat  ← Energy: low = muted, high = vibrant
    - Val  ← Mood:   low = dim, high = bright
    """
    t = max(cfg.TEMPO_MIN, min(cfg.TEMPO_MAX, tempo))
    norm_t = _normalize(t, cfg.TEMPO_MIN, cfg.TEMPO_MAX)
    norm_e = _normalize(energy, cfg.ENERGY_MIN, cfg.ENERGY_MAX)
    norm_m = _normalize(mood, cfg.MOOD_MIN, cfg.MOOD_MAX)

    hue = int(120 * (1.0 - norm_t ** 0.464))   # 120° (green) → 0° (red), orange ≈130 BPM
    sat = int(80 + norm_e * 175)              # 80–255: muted → vibrant
    val = int(180 + norm_m * 75)              # 180–255: dim → bright

    return QColor.fromHsv(hue, sat, val)


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
