"""PluginInfo — metadata for a discovered plugin."""

from __future__ import annotations

from typing import Callable, Optional


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
        self.settings_widget_factory: Optional[Callable] = None
        self.sidebar_buttons: list = []
        self.context_actions: list[tuple[str, Callable]] = []
        self.context_submenus: list[tuple[str, list]] = []
