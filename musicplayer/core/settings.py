"""
App Settings Module

Persistent storage for user preferences:
- Last opened folder path
- Favorites mode active/inactive
- Repeat mode
- Volume level
- Playlist sort mode
"""

import json
import sys
from pathlib import Path
from typing import Optional


def _get_exe_dir() -> Path:
    """Get the directory containing the exe (or project root in dev mode)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


SETTINGS_DIR = _get_exe_dir() / ".cache"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

def _read_settings_json():
    try:
        if not SETTINGS_FILE.exists():
            return {}
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_settings_json(data):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

_app_settings_instances = []

def ensure_default_playlist_sort_mode():
    data = _read_settings_json()
    if "playlist_sort_mode" not in data:
        data["playlist_sort_mode"] = "artist"
        _write_settings_json(data)

def get_playlist_sort_mode():
    data = _read_settings_json()
    return data.get("playlist_sort_mode", "artist")

def set_playlist_sort_mode(mode: str):
    if mode not in ("artist", "title", "newest", "shuffle"):
        mode = "artist"
    data = _read_settings_json()
    if data.get("playlist_sort_mode") == mode:
        return
    data["playlist_sort_mode"] = mode
    _write_settings_json(data)
    for instance in _app_settings_instances:
        instance._data["playlist_sort_mode"] = mode

# Ensure default on import
ensure_default_playlist_sort_mode()

class AppSettings:
    """Manages persistent application settings."""

    def __init__(self):
        _app_settings_instances.append(self)
        self._data = {
            "last_folder": None,
            "last_track": None,
            "music_folder": None,
            "accent_color": None,
            "dynamic_color": False,
            "favorites_mode": False,
            "top_mode": False,
            "repeat_mode": "none",  # none, all, one
            "volume": 0.5,
            "mini_widget_on_minimize": False,
            "web_server_enabled": False,
            "web_server_port": 8080,
            "playlist_sort_mode": "artist",
        }
        self._load()

    def _load(self):
        """Load settings from disk."""
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._data.update(data)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        """Persist settings to disk."""
        try:
            current_data = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            current_data.update(self._data)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def batch_save(self):
        """Persist multiple settings at once without triggering individual saves."""
        try:
            current_data = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            current_data.update(self._data)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    @property
    def last_folder(self) -> Optional[str]:
        return self._data.get("last_folder")

    @last_folder.setter
    def last_folder(self, value: Optional[str]):
        self._data["last_folder"] = value
        self._save()

    @property
    def last_track(self) -> Optional[str]:
        return self._data.get("last_track")

    @last_track.setter
    def last_track(self, value: Optional[str]):
        self._data["last_track"] = value
        self._save()

    @property
    def music_folder(self) -> Optional[str]:
        return self._data.get("music_folder")

    @music_folder.setter
    def music_folder(self, value: Optional[str]):
        self._data["music_folder"] = value
        self._save()

    @property
    def favorites_mode(self) -> bool:
        return self._data.get("favorites_mode", False)

    @favorites_mode.setter
    def favorites_mode(self, value: bool):
        self._data["favorites_mode"] = value
        self._save()

    @property
    def top_mode(self) -> bool:
        return self._data.get("top_mode", False)

    @top_mode.setter
    def top_mode(self, value: bool):
        self._data["top_mode"] = value
        self._save()

    @property
    def repeat_mode(self) -> str:
        return self._data.get("repeat_mode", "none")

    @repeat_mode.setter
    def repeat_mode(self, value: str):
        if value in ("none", "all", "one"):
            self._data["repeat_mode"] = value
            self._save()

    @property
    def volume(self) -> float:
        return self._data.get("volume", 0.5)

    @volume.setter
    def volume(self, value: float):
        self._data["volume"] = value
        self._save()

    @property
    def mini_widget_on_minimize(self) -> bool:
        return self._data.get("mini_widget_on_minimize", False)

    @mini_widget_on_minimize.setter
    def mini_widget_on_minimize(self, value: bool):
        self._data["mini_widget_on_minimize"] = value
        self._save()

    @property
    def dynamic_color(self) -> bool:
        return self._data.get("dynamic_color", False)

    @dynamic_color.setter
    def dynamic_color(self, value: bool):
        self._data["dynamic_color"] = value
        self._save()

    @property
    def playlist_type(self) -> str:
        return self._data.get("playlist_type", "Folder")

    @playlist_type.setter
    def playlist_type(self, value: str):
        if value in ("Folder", "Favorites", "Top", "Playlist"):
            self._data["playlist_type"] = value
            self._save()

    @property
    def web_server_enabled(self) -> bool:
        return self._data.get("web_server_enabled", False)

    @web_server_enabled.setter
    def web_server_enabled(self, value: bool):
        self._data["web_server_enabled"] = value
        self._save()

    @property
    def web_server_port(self) -> int:
        return self._data.get("web_server_port", 8080)

    @web_server_port.setter
    def web_server_port(self, value: int):
        self._data["web_server_port"] = value
        self._save()
