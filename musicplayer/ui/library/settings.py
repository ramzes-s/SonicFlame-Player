"""
Library Settings

Handles persistence of library UI settings like column widths.
"""

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
COL_WIDTHS_FILE = CACHE_DIR / "library_col_widths.json"

DEFAULT_COL_WIDTHS = {
    0: 400,
    1: 300,
    2: 230,
    3: 214,
    4: 230,
    5: 110,
    6: 80,
    7: 50,
    8: 40,
    9: 40,
}


def load_col_widths() -> dict:
    if COL_WIDTHS_FILE.exists():
        try:
            with open(COL_WIDTHS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            pass
    return dict(DEFAULT_COL_WIDTHS)


def save_col_widths(widths: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(COL_WIDTHS_FILE, "w", encoding="utf-8") as f:
            json.dump(widths, f, indent=2)
    except Exception:
        pass