"""
Main Window Module — backward compatibility shim.

All logic has been moved to musicplayer.ui.player package.
"""

from musicplayer.ui.player import MainWindow

__all__ = ["MainWindow"]