"""
PluginManager — discovers, loads and manages plugin lifecycle.

Handles:
- Discovery of plugins (plugin.json scanning)
- Registration (import + register() call)
- Hot enable/disable of individual plugins
- Cleanup of stale settings
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from musicplayer import config as cfg

from .info import PluginInfo
from .hub import PluginHub

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Discovers and loads plugins from PLUGINS_DIR.

    Usage:
        pm = PluginManager(main_window, settings)
        pm.discover()
        pm.register_all()
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

                # Validate and sanitize fields
                display_name = meta.get("display_name", meta["name"])[:50]
                desc = meta.get("description", "")[:90]
                version = meta.get("version", "0.0.0")
                version = re.sub(r"[^0-9.a-zA-Z]", "", version) or "0.0.0"
                author = meta.get("author", "")[:50]

                info = PluginInfo(
                    name=meta["name"],
                    display_name=display_name,
                    version=version,
                    entry=meta.get("entry", meta["name"]),
                    description=desc,
                    settings_page=meta.get("settings_page", False),
                    requires=meta.get("requires", []),
                    author=author,
                )
                self._plugins.append(info)
                logger.info(
                    f"Discovered plugin: {info.display_name} v{info.version}")
            except Exception as e:
                logger.warning(
                    f"Failed to load plugin metadata from {plugin_json}: {e}")

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
            logger.info(
                f"Cleaned up {len(stale_keys)} stale plugin "
                f"settings from plugins.json")

        return self._plugins

    def register_all(self) -> int:
        """
        Load and register all discovered plugins.

        Returns: number of successfully loaded plugins.
        """
        if not cfg.ENABLE_PLUGINS:
            return 0

        self._hub = PluginHub(
            self._main_window, self._settings,
            # Dummy info — replaced per-plugin during registration
            PluginInfo("_hub", "_hub", "", "_hub"),
        )
        loaded = 0

        self._add_plugins_to_syspath()

        for info in self._plugins:
            if not self._settings.get_plugin_enabled(info.name):
                logger.info(
                    f"Plugin disabled, skipping: {info.display_name}")
                continue
            if self._import_and_register(info):
                loaded += 1

        return loaded

    def register_single(self, info: PluginInfo) -> bool:
        """Load and register a single plugin (hot enable).

        Returns True if registration succeeded, False otherwise.
        """
        if self._hub is None:
            logger.warning(
                "PluginHub not initialized, cannot register %s", info.name)
            return False
        self._add_plugins_to_syspath()
        return self._import_and_register(info)

    def _import_and_register(self, info: PluginInfo) -> bool:
        """Import plugin module and call register(hub).

        Returns True on success.
        """
        try:
            plugin_mod = __import__(info.entry, fromlist=['register'])
            if hasattr(plugin_mod, 'register'):
                # Create per-plugin hub with proper info reference
                hub = PluginHub(
                    self._main_window, self._settings, info)
                plugin_mod.register(hub)
                logger.info(
                    "Registered plugin: %s", info.display_name)
                return True
            else:
                logger.warning(
                    "Plugin %s has no register() function", info.name)
                return False
        except Exception as e:
            logger.error(
                "Failed to load plugin %s: %s", info.name, e)
            return False

    def _add_plugins_to_syspath(self):
        plugins_dir = str(cfg.PLUGINS_DIR)
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)

    def get_hub(self) -> Optional[PluginHub]:
        return self._hub

    def unregister_plugin(self, info: PluginInfo):
        """Remove a plugin's UI integration (called when plugin is disabled).

        Only removes the specific plugin's sidebar buttons and
        context menu items — other plugins are unaffected.
        """
        if self._hub is None:
            return

        mw = self._hub._main_window

        # Remove sidebar buttons
        sidebar = mw.sidebar
        for btn in list(info.sidebar_buttons):
            sidebar.remove_plugin_button(btn)
        info.sidebar_buttons.clear()

        # Remove only this plugin's context actions
        pw = mw.playlist_widget
        pw.remove_context_actions(info.context_actions)
        info.context_actions.clear()

        # Remove only this plugin's context submenus
        pw.remove_context_submenus(info.context_submenus)
        info.context_submenus.clear()

        # Refresh callback — if it belongs to this plugin, clear it
        # (each plugin should set its own via set_context_refresh;
        #  we can't track which plugin set it, so this is best-effort)
        # Plugin authors should manage refresh_cb lifecycle.

        # Call plugin's unregister() if it exists
        try:
            plugins_dir = str(cfg.PLUGINS_DIR)
            if plugins_dir not in sys.path:
                sys.path.insert(0, plugins_dir)
            plugin_mod = __import__(info.entry, fromlist=['unregister'])
            if hasattr(plugin_mod, 'unregister'):
                plugin_mod.unregister(self._hub)
        except Exception as e:
            logger.warning(
                "Failed to call unregister for %s: %s", info.name, e)

    def get_discovered_plugins(self) -> list[PluginInfo]:
        """Return all discovered plugins (regardless of enabled state)."""
        return self._plugins
