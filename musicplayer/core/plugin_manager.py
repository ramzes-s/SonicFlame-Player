"""
Plugin System — core loader and PluginHub.

PluginHub provides a controlled interface for plugins to interact with the player.
PluginManager discovers and loads plugins from PLUGINS_DIR.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Callable, Optional

from musicplayer import config as cfg

logger = logging.getLogger(__name__)


class PluginInfo:
    """Metadata for a discovered plugin."""

    def __init__(self, name: str, display_name: str, version: str,
                 entry: str, description: str = "",
                 settings_page: bool = False, requires: list = None,
                 author: str = ""):
        self.name = name
        self.display_name = display_name
        self.version = version
        self.entry = entry
        self.description = description
        self.settings_page = settings_page
        self.requires = requires or []
        self.author = author
        self.settings_widget_factory = None  # Set by hub.set_settings_widget()


class PluginHub:
    """
    Bridge between the player and plugins.

    Plugins receive this object in their register() function.
    It exposes only the methods a plugin needs — no access to player internals.
    """

    def __init__(self, main_window, settings):
        self._main_window = main_window
        self._settings = settings

    # -- UI Integration --

    def add_sidebar_button(self, svg_getter: Callable, tooltip: str,
                           callback: Callable) -> object:
        """Add a button to the sidebar. Returns the button widget."""
        return self._main_window.sidebar.add_plugin_button(
            svg_getter, tooltip, callback)

    def add_context_action(self, text: str, callback: Callable):
        """Add an action to the playlist's right-click context menu."""
        self._main_window.playlist_widget.add_context_action(text, callback)

    def add_settings_page(self, page_widget, tab_name: str):
        """Add a new tab page to the Settings dialog."""
        self._main_window._plugin_pages.append((page_widget, tab_name))

    def set_settings_widget(self, widget_factory):
        """Register a settings widget factory for this plugin.

        The widget will be embedded inside the 'Плагины' tab
        rather than creating a separate tab.
        """
        global _current_plugin_info
        if _current_plugin_info is not None:
            _current_plugin_info.settings_widget_factory = widget_factory

    # -- Player Control --

    def get_player(self):
        """Return the AudioPlayer instance (play/pause/stop only)."""
        return self._main_window.player

    def get_playlist_widget(self):
        """Return the PlaylistWidget."""
        return self._main_window.playlist_widget

    def get_main_window(self):
        """Return the main window (as parent for dialogs)."""
        return self._main_window

    # -- Settings --

    def get_settings(self):
        """Return the AppSettings instance."""
        return self._settings

    def get_config_value(self, key: str):
        """Get a value from config by attribute name."""
        return getattr(cfg, key, None)

    # -- Plugin-specific settings storage --

    PLUGIN_SETTINGS_FILE = cfg.CACHE_DIR / "plugins.json"

    @classmethod
    def _load_all_plugin_settings(cls) -> dict:
        try:
            with open(cls.PLUGIN_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @classmethod
    def _save_all_plugin_settings(cls, data: dict):
        cls.PLUGIN_SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_plugin_settings(self, plugin_name: str) -> dict:
        """Return settings dict for a specific plugin."""
        all_data = self._load_all_plugin_settings()
        return all_data.get(plugin_name, {})

    def save_plugin_settings(self, plugin_name: str, data: dict):
        """Persist settings dict for a specific plugin (merges with existing)."""
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
        if added and mw._current_folder_path:
            folder = mw._current_folder_path
            if any(str(t.filepath).startswith(folder) for t in added):
                mw._scanning.scan(folder)

    def get_db(self):
        """Return the db module for direct queries."""
        from musicplayer.core import db
        return db


# Track which plugin is currently being registered (for hub.set_settings_widget)
_current_plugin_info: Optional[PluginInfo] = None


class PluginManager:
    """
    Discovers and loads plugins from PLUGINS_DIR.

    Usage:
        pm = PluginManager(main_window, settings)
        pm.discover()
        pm.register_all(hub)
    """

    def __init__(self, main_window, settings):
        self._main_window = main_window
        self._settings = settings
        self._plugins: list[PluginInfo] = []
        self._hub: Optional[PluginHub] = None

    def discover(self) -> list[PluginInfo]:
        """Scan PLUGINS_DIR and return list of discovered plugins."""
        self._plugins = []
        if not cfg.ENABLE_PLUGINS:
            logger.info("Plugins disabled by ENABLE_PLUGINS=False")
            return self._plugins

        plugins_dir = cfg.PLUGINS_DIR
        if not plugins_dir.exists():
            logger.info(f"Plugins directory not found: {plugins_dir}")
            return self._plugins

        for entry_dir in sorted(plugins_dir.iterdir()):
            if not entry_dir.is_dir() or entry_dir.name.startswith('_'):
                continue
            plugin_json = entry_dir / "plugin.json"
            if not plugin_json.exists():
                continue
            try:
                with open(plugin_json, encoding='utf-8') as f:
                    meta = json.load(f)
                info = PluginInfo(
                    name=meta["name"],
                    display_name=meta.get("display_name", meta["name"]),
                    version=meta.get("version", "0.0.0"),
                    entry=meta.get("entry", meta["name"]),
                    description=meta.get("description", ""),
                    settings_page=meta.get("settings_page", False),
                    requires=meta.get("requires", []),
                    author=meta.get("author", ""),
                )
                self._plugins.append(info)
                logger.info(f"Discovered plugin: {info.display_name} v{info.version}")
            except Exception as e:
                logger.warning(f"Failed to load plugin metadata from {plugin_json}: {e}")

        # Remove stale plugin_enabled_* entries from settings
        active = {p.name for p in self._plugins}
        self._settings.cleanup_plugin_settings(active)

        # Remove stale entries from plugins.json
        all_plugin_data = PluginHub._load_all_plugin_settings()
        stale_keys = set(all_plugin_data) - active
        if stale_keys:
            for key in stale_keys:
                del all_plugin_data[key]
            PluginHub._save_all_plugin_settings(all_plugin_data)
            logger.info(f"Cleaned up {len(stale_keys)} stale plugin settings from plugins.json")

        return self._plugins

    def register_all(self) -> int:
        """
        Load and register all discovered plugins.

        Returns: number of successfully loaded plugins.
        """
        if not cfg.ENABLE_PLUGINS:
            return 0

        global _current_plugin_info

        self._hub = PluginHub(self._main_window, self._settings)
        loaded = 0

        # Add plugins dir to sys.path for import
        plugins_dir = str(cfg.PLUGINS_DIR)
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)

        for info in self._plugins:
            if not self._settings.get_plugin_enabled(info.name):
                logger.info(f"Plugin disabled, skipping: {info.display_name}")
                continue
            try:
                _current_plugin_info = info
                plugin_mod = __import__(info.entry, fromlist=['register'])
                if hasattr(plugin_mod, 'register'):
                    plugin_mod.register(self._hub)
                    loaded += 1
                    logger.info(f"Registered plugin: {info.display_name}")
                else:
                    logger.warning(f"Plugin {info.name} has no register() function")
            except Exception as e:
                logger.error(f"Failed to load plugin {info.name}: {e}")
            finally:
                _current_plugin_info = None

        return loaded

    def get_hub(self) -> Optional[PluginHub]:
        return self._hub

    def get_discovered_plugins(self) -> list[PluginInfo]:
        """Return all discovered plugins (regardless of enabled state)."""
        return self._plugins
