"""
PluginHub — controlled bridge between the player and plugins.

Plugins receive this object in their register() function.
It exposes only the methods a plugin needs, with safety guards.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from musicplayer import config as cfg

from .info import PluginInfo

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

_ALLOWED_CONFIG_KEYS = frozenset({
    "PROJECT_DIR", "CACHE_DIR", "DB_PATH", "COVERS_DIR",
    "ARTIST_COLLAGES_DIR", "SETTINGS_FILE", "COL_WIDTHS_FILE",
    "PLUGINS_DIR", "ENABLE_PLUGINS",
    "BG_COLOR", "SECONDARY_BG_COLOR",
    "TEXT_COLOR", "SECONDARY_TEXT_COLOR", "TERTIARY_TEXT_COLOR",
    "DISABLED_TEXT_COLOR", "CTR_TEXT_COLOR",
    "DIVIDER_COLOR", "DIVIDER_ITEM_COLOR", "DIVIDER_ITEM_RGB",
    "DIVIDER_ITEM_ALPHA",
    "SCROLLBAR_HANDLE_COLOR", "SCROLLBAR_HANDLE_HOVER_COLOR",
    "BUTTON_BG_COLOR", "BUTTON_HOVER_BG_COLOR",
    "BUTTON_PRESSED_BG_COLOR", "BUTTON_BORDER_COLOR",
    "INPUT_BG_COLOR", "INPUT_BORDER_COLOR", "INPUT_TEXT_COLOR",
    "BADGE_BG_RGB", "BADGE_BG_ALPHA", "BADGE_TEXT_COLOR",
    "TEMPO_MIN", "TEMPO_MAX", "ENERGY_MIN", "ENERGY_MAX",
    "MOOD_MIN", "MOOD_MAX", "FLUX_MIN", "FLUX_MAX",
    "HPSS_NORM_MIN", "HPSS_NORM_MAX",
    "TOL_BASELINE", "GENRE_WEIGHT", "PENALTY_LANGUAGE",
    "AUDIO_WEIGHT_TEMPO", "AUDIO_WEIGHT_ENERGY", "AUDIO_WEIGHT_MOOD",
    "AUDIO_WEIGHT_ZCR", "AUDIO_WEIGHT_FLUX", "AUDIO_WEIGHT_HPSS",
    "ANALYSIS_DURATION", "ACCENT_COLOR",
})


class LockedSettings:
    """Read-only proxy over AppSettings for plugins.

    Prevents plugins from accidentally modifying player-wide settings.
    """

    def __init__(self, settings):
        self._settings = settings

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(f"Access denied: {name}")
        return getattr(self._settings, name)

    def __setattr__(self, name, value):
        if name == "_settings":
            super().__setattr__(name, value)
            return
        raise TypeError("Plugins cannot modify player settings")


class PluginHub:
    """
    Bridge between the player and plugins.

    Plugins receive this object in their register() function.
    It exposes only the methods a plugin needs — no access to player internals.
    """

    def __init__(self, main_window, settings, plugin_info: PluginInfo):
        self._main_window = main_window
        self._settings = LockedSettings(settings)
        self._plugin_info = plugin_info

    # -- UI Integration --

    def add_sidebar_button(self, svg_getter: Callable, tooltip: str,
                           callback: Callable) -> object:
        """Add a button to the sidebar. Returns the button widget."""
        btn = self._main_window.sidebar.add_plugin_button(
            svg_getter, tooltip, callback)
        self._plugin_info.sidebar_buttons.append(btn)
        return btn

    def add_context_action(self, text: str, callback: Callable):
        """Add an action to the playlist's right-click context menu."""
        self._main_window.playlist_widget.add_context_action(text, callback)
        self._plugin_info.context_actions.append((text, callback))

    def add_context_submenu(self, label: str, items: list):
        """Add a submenu to the playlist's right-click context menu.

        Args:
            label: submenu label text
            items: list of (item_text, callback) tuples.
                   callback receives view_index of the clicked track.
        """
        self._main_window.playlist_widget.add_context_submenu(label, items)
        self._plugin_info.context_submenus.append((label, items))

    def add_settings_page(self, page_widget, tab_name: str):
        """Add a new tab page to the Settings dialog."""
        self._main_window.add_plugin_page(page_widget, tab_name)

    def set_settings_widget(self, widget_factory):
        """Register a settings widget factory for this plugin.

        The widget will be embedded inside the 'Плагины' tab
        rather than creating a separate tab.
        """
        self._plugin_info.settings_widget_factory = widget_factory

    # -- Player Control --

    def get_player(self):
        """Return the AudioPlayer instance (read-only player control)."""
        return self._main_window.player

    def get_playlist_widget(self):
        """Return the PlaylistWidget."""
        return self._main_window.playlist_widget

    def get_main_window(self):
        """Return the main window (as parent for dialogs)."""
        return self._main_window

    # -- Settings --

    def get_settings(self):
        """Return read-only AppSettings proxy.

        Plugins can read player settings but CANNOT modify them.
        Use save_plugin_settings() for plugin-specific storage.
        """
        return self._settings

    def get_config_value(self, key: str):
        """Get a value from config by attribute name.

        Only allows access to pre-approved constants (UI colors, paths).
        """
        if key not in _ALLOWED_CONFIG_KEYS:
            raise KeyError(
                f"Access to config key '{key}' is not allowed for plugins")
        return getattr(cfg, key, None)

    # -- Plugin-specific settings storage --

    PLUGIN_SETTINGS_FILE: Path = cfg.CACHE_DIR / "plugins.json"

    def get_data_dir(self) -> Path:
        """Return the plugin's private data directory.

        This is the recommended location for plugin DATA (playlists,
        caches, user files). The directory is created on first call
        if it doesn't exist.

        For plugin SETTINGS (small key-value config), use
        get_plugin_settings() / save_plugin_settings() instead.
        """
        path = cfg.PLUGINS_DIR / self._plugin_info.name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _load_all_plugin_settings(cls) -> dict:
        with _LOCK:
            try:
                with open(cls.PLUGIN_SETTINGS_FILE, "r",
                          encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    @classmethod
    def _save_all_plugin_settings(cls, data: dict):
        with _LOCK:
            cls.PLUGIN_SETTINGS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_plugin_settings(self, plugin_name: str) -> dict:
        """Return settings dict for a specific plugin."""
        all_data = self._load_all_plugin_settings()
        return all_data.get(plugin_name, {})

    def save_plugin_settings(self, plugin_name: str, data: dict):
        """Persist settings dict for a specific plugin (replaces existing)."""
        all_data = self._load_all_plugin_settings()
        all_data[plugin_name] = data
        self._save_all_plugin_settings(all_data)

    # -- Database --

    def add_tracks_to_library(self, filepaths: list):
        """Add downloaded tracks to the database and refresh UI if needed."""
        from musicplayer.core.db import upsert_track, extract_metadata
        added = []
        for fp in filepaths:
            path = Path(fp)
            if path.exists():
                track = extract_metadata(str(path))
                if track:
                    upsert_track(track, track.mtime)
                    added.append(track)
        # Refresh playlist if we're in the target folder
        mw = self._main_window
        if added:
            folder = mw.get_current_folder()
            if folder and any(str(t.filepath).startswith(folder)
                              for t in added):
                mw.rescan_folder()

    def get_db(self):
        """Return the db module for direct queries."""
        from musicplayer.core import db
        return db
