"""
Library UI Package

Contains the library dialog and related components for managing
the music library view with tracks and artists tabs.
"""

from musicplayer.ui.library.dialog import LibraryDialog
from musicplayer.ui.library.model import LibraryModel
from musicplayer.ui.library.worker import DataWorker
from musicplayer.ui.library.artist_view import ArtistViewWidget

__all__ = [
    "LibraryDialog",
    "LibraryModel",
    "DataWorker",
    "ArtistViewWidget",
]