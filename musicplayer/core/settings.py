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
from pathlib import Path
from typing import Optional

from musicplayer import config


SETTINGS_DIR = config.CACHE_DIR
SETTINGS_FILE = config.SETTINGS_FILE

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

def ensure_default_prevent_sleep():
    data = _read_settings_json()
    if "prevent_sleep" not in data:
        data["prevent_sleep"] = True
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

def get_prevent_sleep():
    data = _read_settings_json()
    return data.get("prevent_sleep", True)

def set_prevent_sleep(value: bool):
    data = _read_settings_json()
    data["prevent_sleep"] = value
    _write_settings_json(data)
    for instance in _app_settings_instances:
        instance._data["prevent_sleep"] = value

def ensure_default_similarity_precision():
    data = _read_settings_json()
    if "similarity_precision" not in data:
        data["similarity_precision"] = 20
        _write_settings_json(data)

def get_similarity_precision():
    data = _read_settings_json()
    return data.get("similarity_precision", 20)

def set_similarity_precision(value: int):
    value = max(0, min(40, int(value)))
    data = _read_settings_json()
    if data.get("similarity_precision") == value:
        return
    data["similarity_precision"] = value
    _write_settings_json(data)
    for instance in _app_settings_instances:
        instance._data["similarity_precision"] = value

def ensure_default_analysis_duration():
    data = _read_settings_json()
    if "analysis_duration" not in data:
        data["analysis_duration"] = config.ANALYSIS_DURATION
        _write_settings_json(data)

def get_analysis_duration():
    data = _read_settings_json()
    return data.get("analysis_duration", config.ANALYSIS_DURATION)

def set_analysis_duration(value: int):
    value = max(30, min(60, int(value) // 10 * 10))
    data = _read_settings_json()
    if data.get("analysis_duration") == value:
        return
    data["analysis_duration"] = value
    _write_settings_json(data)
    for instance in _app_settings_instances:
        instance._data["analysis_duration"] = value

# Ensure default on import
ensure_default_playlist_sort_mode()
ensure_default_prevent_sleep()
ensure_default_similarity_precision()
ensure_default_analysis_duration()

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
            "mini_widget_opacity": 40,
            "web_server_enabled": False,
            "web_server_port": 8080,
            "allow_remote_shutdown": False,
            "playlist_sort_mode": "artist",
            "similarity_precision": 20,
            "analysis_duration": config.ANALYSIS_DURATION,
            "audio_output_device": None,
            "use_language_filter": False,
            "language_filter_mode": "off",
            "idle_shutdown_minutes": 60,
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
    def mini_widget_opacity(self) -> int:
        return self._data.get("mini_widget_opacity", 40)

    @mini_widget_opacity.setter
    def mini_widget_opacity(self, value: int):
        self._data["mini_widget_opacity"] = max(0, min(80, int(value)))
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

    @property
    def allow_remote_shutdown(self) -> bool:
        return self._data.get("allow_remote_shutdown", False)

    @allow_remote_shutdown.setter
    def allow_remote_shutdown(self, value: bool):
        self._data["allow_remote_shutdown"] = value
        self._save()

    @property
    def prevent_sleep(self) -> bool:
        return self._data.get("prevent_sleep", True)

    @prevent_sleep.setter
    def prevent_sleep(self, value: bool):
        self._data["prevent_sleep"] = value
        self._save()

    @property
    def similarity_precision(self) -> int:
        return self._data.get("similarity_precision", 20)

    @similarity_precision.setter
    def similarity_precision(self, value: int):
        self._data["similarity_precision"] = max(0, min(40, int(value)))
        self._save()

    @property
    def analysis_duration(self) -> int:
        return self._data.get("analysis_duration", config.ANALYSIS_DURATION)

    @analysis_duration.setter
    def analysis_duration(self, value: int):
        self._data["analysis_duration"] = max(30, min(60, int(value) // 10 * 10))
        self._save()

    @property
    def audio_output_device(self) -> str | None:
        return self._data.get("audio_output_device")

    @audio_output_device.setter
    def audio_output_device(self, value: str | None):
        self._data["audio_output_device"] = value
        self._save()

    @property
    def idle_shutdown_minutes(self) -> int:
        return self._data.get("idle_shutdown_minutes", 60)

    @idle_shutdown_minutes.setter
    def idle_shutdown_minutes(self, value: int):
        self._data["idle_shutdown_minutes"] = max(0, int(value))
        self._save()

    @property
    def use_language_filter(self) -> bool:
        return self._data.get("use_language_filter", False)

    @use_language_filter.setter
    def use_language_filter(self, value: bool):
        self._data["use_language_filter"] = value
        self._save()

    @property
    def language_filter_mode(self) -> str:
        return self._data.get("language_filter_mode", "off")

    @language_filter_mode.setter
    def language_filter_mode(self, value: str):
        if value in ("off", "penalty", "exclude"):
            self._data["language_filter_mode"] = value
            self._save()
