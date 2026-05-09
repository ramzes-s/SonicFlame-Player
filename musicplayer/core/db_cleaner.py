"""
Database Cleaner Module

Removes tracks from the database that no longer exist on disk.
Also removes orphaned cover cache files.
"""

import os
from musicplayer.core.db import get_all_library_tracks_light, delete_track, get_all_folders


def cleanup_missing_tracks() -> int:
    """
    Check all tracks in the database and remove those that no longer exist on disk.

    Returns:
        Number of removed tracks.
    """
    tracks = get_all_library_tracks_light()
    removed_count = 0

    for track in tracks:
        if not os.path.exists(track.filepath):
            delete_track(track.filepath)
            removed_count += 1

    print(f"[DB Cleaner] Removed {removed_count} missing tracks from database")
    return removed_count