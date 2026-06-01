"""
Database Package

SQLite-based persistent storage for all track metadata.
Exposes public API for track operations, favorites, caching, and queries.

Submodules:
- connection: Database connection and configuration
- tracks: Track CRUD operations and metadata extraction
- favorites: Favorites management
- cache: Cover art and artists cache
- queries: Filtering and complex queries
"""

from musicplayer.core.db.connection import (
    get_connection,
    init_db,
    get_db_mtime,
    DB_PATH,
    DB_DIR,
    COVERS_DIR,
    normalize_path,
)

from musicplayer.core.db.tracks import (
    TrackInfo,
    extract_metadata,
    get_track,
    get_track_mtime,
    upsert_track,
    update_track_analysis,
    increment_play_count,
    delete_track,
    delete_folder_tracks,
    get_all_library_tracks_light,
    get_tracks_by_folder,
    get_tracks_by_artist,
    get_folder_filepaths,
    ensure_cover_for_track,
    _row_to_track,
    _row_to_track_with_cover,
)

from musicplayer.core.db.favorites import (
    is_favorite,
    toggle_favorite,
    get_favorite_filepaths,
    get_favorite_tracks,
)

from musicplayer.core.db.cache import (
    get_covers_cache_size,
    get_artists_cache_status,
    get_cached_artists,
    update_artists_cache,
    delete_cover,
    get_cover_path,
    _get_cover_path,
)

from musicplayer.core.db.queries import (
    get_filtered_library_track_count,
    get_analyzed_track_count,
    get_library_tracks_page,
    get_all_genres,
    get_all_folders,
    get_top_tracks,
    find_similar_tracks,
)

from musicplayer.core.db.folders import (
    upsert_folder,
    get_folder_track_count,
    delete_folder,
)

from musicplayer.core.db.system import (
    set_system_value,
    get_system_value,
)

__all__ = [
    # Connection
    "get_connection",
    "init_db",
    "get_db_mtime",
    "DB_PATH",
    "DB_DIR",
    "COVERS_DIR",
    "normalize_path",
    # Tracks
    "TrackInfo",
    "extract_metadata",
    "get_track",
    "get_track_mtime",
    "upsert_track",
    "update_track_analysis",
    "increment_play_count",
    "delete_track",
    "delete_folder_tracks",
    "get_all_library_tracks_light",
    "get_tracks_by_folder",
    "get_tracks_by_artist",
    "get_folder_filepaths",
    "ensure_cover_for_track",
    # Favorites
    "is_favorite",
    "toggle_favorite",
    "get_favorite_filepaths",
    "get_favorite_tracks",
    # Cache
    "get_covers_cache_size",
    "get_artists_cache_status",
    "get_cached_artists",
    "update_artists_cache",
    "delete_cover",
    "get_cover_path",
    "_get_cover_path",
    # Queries
    "get_filtered_library_track_count",
    "get_analyzed_track_count",
    "get_library_tracks_page",
    "get_all_genres",
    "get_all_folders",
    "get_top_tracks",
    "find_similar_tracks",
    # Folders
    "upsert_folder",
    "get_folder_track_count",
    "delete_folder",
    # System
    "set_system_value",
    "get_system_value",
]