import os
from musicplayer.core.db import get_filtered_library_track_count, get_covers_cache_size

ACCENT_PRESETS = [
    ("#ed6a02", "Orange"),
    ("#ff4444", "Red"),
    ("#e91e63", "Pink"),
    ("#9c27b0", "Purple"),
    ("#673ab7", "Deep Purple"),
    ("#3f51b5", "Indigo"),
    ("#2196f3", "Blue"),
    ("#00bcd4", "Cyan"),
    ("#009688", "Teal"),
    ("#4caf50", "Green"),
    ("#8bc34a", "Light Green"),
    ("#ffc150", "Yellow"),
    ("#977c64", "Brown"),
    ("#84a2be", "Gray"),
    ("#607884", "Slate"),
]

FORBIDDEN_PORTS = {21, 22, 80, 443}


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"


def get_library_track_count() -> int:
    try:
        return get_filtered_library_track_count()
    except Exception:
        return 0
