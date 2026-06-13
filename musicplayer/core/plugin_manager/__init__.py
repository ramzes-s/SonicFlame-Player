"""Plugin system — discovery, lifecycle, and PluginHub."""

from .info import PluginInfo
from .hub import PluginHub, LockedSettings
from .manager import PluginManager

__all__ = ["PluginInfo", "PluginHub", "PluginManager", "LockedSettings"]
