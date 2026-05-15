# Re-export all public classes for backward compatibility
from .constants import ID3_GENRES, COVER_SIZE, BRIGHT_COLORS
from .cover import _generate_abstract_cover
from .cover_thread import _CoverSearchThread
from .threads import _TrackSearchThread, _SaveTagsThread, _CoverDownloadThread
from .widgets import LoadingBar, CoverDisplayLabel
from .dialogs import TrackSearchResultsDialog, CoverSearchResultsDialog, CoverTile
from .editor import TagEditorDialog
from .base_dialog import BaseFramelessDialog
from .track_mover import move_track_to_folder
from .api import (
    _search_itunes_covers_static,
    _search_deezer_covers_static,
    _search_itunes_tracks_static,
    _search_deezer_tracks_static,
)

__all__ = [
    "TagEditorDialog",
    "TrackSearchResultsDialog",
    "CoverSearchResultsDialog",
    "LoadingBar",
    "CoverDisplayLabel",
    "CoverTile",
    "BaseFramelessDialog",
    "move_track_to_folder",
    "_CoverSearchThread",
    "_TrackSearchThread",
    "_SaveTagsThread",
    "_CoverDownloadThread",
    "_generate_abstract_cover",
    "ID3_GENRES",
]