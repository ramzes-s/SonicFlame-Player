"""
Playlist Module

Manages track lists, shuffle/repeat logic, and current track navigation.
"""

import random
import os
from typing import List, Optional
from musicplayer.core.db import TrackInfo
from musicplayer.core.settings import get_playlist_sort_mode


class RepeatMode:
    """Enumeration of repeat modes."""
    NONE = "none"          # No repeat
    ALL = "all"            # Repeat entire playlist
    ONE = "one"            # Repeat current track


class Playlist:
    """
    Manages a list of tracks with navigation and shuffle/repeat logic.
    """
    
    def __init__(self):
        self._tracks: List[TrackInfo] = []
        self._original_order: List[TrackInfo] = []
        self._current_index = -1
        self._shuffle_enabled = False
        self._repeat_mode = RepeatMode.NONE
        # When loading initial tracks, avoid applying sorting until explicitly requested
        self._ignore_sort_on_load = False
        # New: initialize sort mode storage; default comes from settings
        self._sort_mode = get_playlist_sort_mode()
        self._bulk_add_depth = 0
    
    def set_sort_mode(self, mode: str):
        """Set sorting mode for the playlist: 'artist' | 'title' | 'newest' | 'shuffle'"""
        if mode not in ("artist", "title", "newest", "shuffle"):
            mode = "artist"
        if getattr(self, "_sort_mode", None) == mode:
            return
        self._sort_mode = mode
        if getattr(self, "_ignore_sort_on_load", False):
            # Do not reorder currently-loaded tracks during initial load
            return
        self._apply_sort()

    def load_tracks_no_sort(self, tracks: List[TrackInfo]):
        """Load tracks into playlist without applying any sort. Used for initial load."""
        self._tracks = tracks[:]
        self._original_order = tracks[:]
        self._current_index = -1

    def _apply_sort(self):
        """Sorts or shuffles the playlist based on the current `_sort_mode`."""
        if not self._original_order:
            self._tracks = []
            self._current_index = -1
            return

        current_track = self.get_current_track()
        
        if self._sort_mode == "shuffle":
            # Shuffle a copy of the original order
            self._tracks = self._original_order[:]
            random.shuffle(self._tracks)
        else:
            # Apply a specific sort order to the original list
            if self._sort_mode == "artist":
                key = lambda t: ((t.artist or "") if t.artist is not None else "", (t.album or "") if t.album is not None else "", (t.title or "") if t.title is not None else "")
            elif self._sort_mode == "title":
                key = lambda t: ((t.title or "") if t.title is not None else "", (t.artist or "") if t.artist is not None else "", (t.album or "") if t.album is not None else "")
            elif self._sort_mode == "newest":
                def _mtime(track: TrackInfo) -> float:
                    m = getattr(track, "mtime", 0.0)
                    if m is None:
                        m = 0.0
                    return m
                key = lambda t: (-_mtime(t), (t.title or ""))
            else: # Default to artist
                key = lambda t: ((t.artist or ""), (t.album or ""), (t.title or ""))
            
            self._tracks = sorted(self._original_order, key=key)

        # Restore current track position
        if current_track and current_track in self._tracks:
            self._current_index = self._tracks.index(current_track)
        
        if hasattr(self, "_on_playlist_changed") and callable(self._on_playlist_changed):
            self._on_playlist_changed()

    def set_tracks(self, tracks: List[TrackInfo]):
        """Load tracks into playlist, maintaining original order."""
        self._tracks = tracks[:]
        self._original_order = tracks[:]
        self._current_index = -1
        # If we are currently in a bulk-load mode, skip sorting to avoid UI freeze
        if getattr(self, "_ignore_sort_on_load", False) or getattr(self, "_bulk_add_depth", 0) > 0:
            return
        # Otherwise apply current sorting
        self._apply_sort()
    
    def add_tracks(self, tracks: List[TrackInfo]):
        """Append tracks to the playlist."""
        self._tracks.extend(tracks)
        self._original_order.extend(tracks)
        # If in bulk add mode, defer sorting for performance
        if self._bulk_add_depth > 0:
            return
        # Re-apply current sort mode to the extended list
        self._apply_sort()

    def begin_bulk_add(self):
        """Begin a batch of additions where sorting should be deferred."""
        self._bulk_add_depth += 1

    def end_bulk_add(self):
        """End a batch of additions and apply sorting once."""
        if self._bulk_add_depth > 0:
            self._bulk_add_depth -= 1
        if self._bulk_add_depth == 0:
            if not getattr(self, "_ignore_sort_on_load", False):
                self._apply_sort()
    
    def force_sort(self, mode: str):
        """Force sort regardless of _ignore_sort_on_load flag."""
        self._sort_mode = mode
        self._apply_sort()
    
    def clear(self):
        """Clear all tracks from the playlist."""
        self._tracks.clear()
        self._original_order.clear()
        self._current_index = -1
    
    def get_tracks(self) -> List[TrackInfo]:
        """Get current track list (may be shuffled or sorted)."""
        return self._tracks[:]
    
    def get_current_track(self) -> Optional[TrackInfo]:
        """Get the currently playing track."""
        if 0 <= self._current_index < len(self._tracks):
            return self._tracks[self._current_index]
        return None
    
    def get_current_index(self) -> int:
        """Get the index of the currently playing track."""
        return self._current_index
    
    def get_track_count(self) -> int:
        """Get total number of tracks."""
        return len(self._tracks)
    
    def play_track_at(self, index: int):
        """Set current track by index."""
        if 0 <= index < len(self._tracks):
            self._current_index = index
    
    def play_next(self) -> Optional[TrackInfo]:
        """
        Move to next track.
        Handles repeat logic.
        """
        if not self._tracks:
            return None
        
        if self._repeat_mode == RepeatMode.ONE:
            # Repeat current track
            return self.get_current_track()
        
        next_index = self._current_index + 1
        
        if next_index >= len(self._tracks):
            # End of playlist
            if self._repeat_mode == RepeatMode.ALL:
                next_index = 0  # Loop back to start
            else:
                return None  # Stop playback
        
        self._current_index = next_index
        return self._tracks[self._current_index]
    
    def play_previous(self) -> Optional[TrackInfo]:
        """
        Move to previous track.
        Handles repeat logic.
        """
        if not self._tracks:
            return None
        
        prev_index = self._current_index - 1
        
        if prev_index < 0:
            if self._repeat_mode == RepeatMode.ALL:
                prev_index = len(self._tracks) - 1  # Loop to end
            else:
                prev_index = 0  # Stay at start
        
        self._current_index = prev_index
        return self._tracks[self._current_index]
    
    def set_repeat_mode(self, mode: str):
        """Set repeat mode (NONE, ALL, ONE)."""
        if mode in [RepeatMode.NONE, RepeatMode.ALL, RepeatMode.ONE]:
            self._repeat_mode = mode
    
    def get_repeat_mode(self) -> str:
        """Get current repeat mode."""
        return self._repeat_mode

    def force_sort(self, mode: str):
        """Force sorting of current tracks according to mode, regardless of load state."""
        if mode not in ("artist", "title", "newest", "shuffle"):
            mode = "artist"
        self._sort_mode = mode
        # Apply sort immediately
        self._apply_sort()
