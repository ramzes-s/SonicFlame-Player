"""
Library Settings

Handles persistence of library UI settings like column widths.
"""

import json

from musicplayer import config

CACHE_DIR = config.CACHE_DIR
COL_WIDTHS_FILE = config.COL_WIDTHS_FILE

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
        except Exception as e:
            print(f"settings.load_col_widths: failed to load column widths: {e}")
    return dict(DEFAULT_COL_WIDTHS)


def save_col_widths(widths: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(COL_WIDTHS_FILE, "w", encoding="utf-8") as f:
            json.dump(widths, f, indent=2)
    except Exception as e:
        print(f"settings.save_col_widths: failed to save column widths: {e}")