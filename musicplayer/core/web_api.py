"""
Web Server API Handlers

API endpoints for player control.
"""

import base64
import socket
from aiohttp import web
from typing import List, Optional
from musicplayer.core.db import get_all_folders, get_filtered_library_track_count
from musicplayer.core.db.connection import is_safe_filepath, get_music_folder
from musicplayer import config as cfg


def _validate_volume(value) -> Optional[float]:
    """Validate volume value is between 0 and 1."""
    try:
        vol = float(value)
        return max(0.0, min(1.0, vol))
    except (TypeError, ValueError):
        return None


def _validate_position(value) -> Optional[int]:
    """Validate position is non-negative integer."""
    try:
        pos = int(value)
        return max(0, pos)
    except (TypeError, ValueError):
        return None


def _validate_index(value, max_len: int) -> Optional[int]:
    """Validate track index is within valid range."""
    try:
        idx = int(value)
        if 0 <= idx < max_len:
            return idx
    except (TypeError, ValueError):
        pass
    return None


class APIHandlers:
    """Handles all API requests for the web server."""

    def __init__(self, server):
        self._server = server

    async def handle_status(self, request: web.Request) -> web.Response:
        srv = self._server
        with srv._lock:
            playing = srv._playing
            position = srv._position
            duration = srv._duration
            volume = srv._volume
            repeat = srv._repeat
            sort_mode = srv._sort_mode
        return web.json_response({
            "playing": playing,
            "position": position,
            "duration": duration,
            "volume": volume,
            "repeat": repeat,
            "sort_mode": sort_mode
        })

    async def handle_track(self, request: web.Request) -> web.Response:
        with self._server._lock:
            track = self._server._current_track
            is_fav = track.filepath in self._server._favorite_filepaths if track else False
            playlist_title = self._server._playlist_title

        if not track:
            return web.json_response(None)

        cover_b64 = None
        if track.filepath:
            from musicplayer.core.db.cache import _load_cover
            cover_data = _load_cover(track.filepath)
            if cover_data:
                try:
                    cover_b64 = base64.b64encode(cover_data).decode()
                except Exception as e:
                    print("web_api.handle_track: encode cover b64 failed")
                    cover_b64 = None

        return web.json_response({
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "duration": track.duration,
            "genre": track.genre,
            "bitrate": track.bitrate,
            "is_favorite": is_fav,
            "cover": cover_b64,
            "playlist_title": playlist_title
        })

    async def handle_playlist(self, request: web.Request) -> web.Response:
        with self._server._lock:
            playlist = list(self._server._playlist)
        tracks = []
        for t in playlist:
            tracks.append({
                "title": t.title,
                "artist": t.artist,
                "album": t.album,
                "duration": t.duration
            })
        return web.json_response(tracks)

    async def handle_accent_color(self, request: web.Request) -> web.Response:
        return web.json_response({"color": cfg.get_accent_color()})

    async def handle_playing_data(self, request: web.Request) -> web.Response:
        srv = self._server
        with srv._lock:
            playing = srv._playing
            position = srv._position
            duration = srv._duration
            volume = srv._volume
            repeat = srv._repeat
            current_index = srv._current_index
            track = srv._current_track
            is_fav = track.filepath in srv._favorite_filepaths if track else False
            sort_mode = srv._sort_mode

        return web.json_response({
            "status": {
                "playing": playing,
                "position": position,
                "duration": duration,
                "volume": volume,
                "repeat": repeat
            },
            "current_index": current_index,
            "current_track_filepath": track.filepath if track else None,
            "is_favorite": is_fav,
            "accent_color": cfg.get_accent_color(),
            "sort_mode": sort_mode
        })

    async def handle_play(self, request: web.Request) -> web.Response:
        print(f"[WebServer] handle_play called")
        self._server._relay.play_requested.emit()
        return web.json_response({"ok": True})

    async def handle_pause(self, request: web.Request) -> web.Response:
        print(f"[WebServer] handle_pause called")
        self._server._relay.pause_requested.emit()
        return web.json_response({"ok": True})

    async def handle_next(self, request: web.Request) -> web.Response:
        print(f"[WebServer] handle_next called")
        self._server._relay.next_requested.emit()
        return web.json_response({"ok": True})

    async def handle_previous(self, request: web.Request) -> web.Response:
        self._server._relay.previous_requested.emit()
        return web.json_response({"ok": True})

    async def handle_volume(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            volume = _validate_volume(data.get("value", 0.5))
            if volume is not None:
                self._server._relay.volume_requested.emit(volume)
        except Exception as e:
            print("web_api.handle_volume: parse volume request failed")
        return web.json_response({"ok": True})

    async def handle_seek(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            position = _validate_position(data.get("position", 0))
            if position is not None:
                self._server._relay.seek_requested.emit(position)
        except Exception as e:
            print("web_api.handle_seek: parse seek request failed")
        return web.json_response({"ok": True})

    async def handle_play_track(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            with self._server._lock:
                playlist_len = len(self._server._playlist)
            index = _validate_index(data.get("index", 0), playlist_len)
            if index is not None:
                self._server._relay.play_track_requested.emit(index)
        except Exception as e:
            print("web_api.handle_play_track: parse play_track request failed")
        return web.json_response({"ok": True})

    async def handle_folders(self, request: web.Request) -> web.Response:
        from musicplayer.core.settings import AppSettings
        settings = AppSettings()
        root_folder = settings.music_folder
        total_tracks = get_filtered_library_track_count()
        folders = get_all_folders()
        result = []
        if root_folder:
            result.append({"path": root_folder, "name": "Вся музыка", "track_count": total_tracks})
        for f in folders:
            path = f[0]
            name = path.replace('\\', '/').split('/')[-1]
            result.append({"path": path, "name": name, "track_count": f[1]})
        return web.json_response(result)

    async def handle_play_folder(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            path = data.get("path", "")
            if path:
                # Validate path to prevent path traversal
                music_folder = get_music_folder()
                if is_safe_filepath(path, music_folder):
                    self._server._relay.play_folder_requested.emit(path)
        except Exception as e:
            print("web_api.handle_play_folder: parse play_folder request failed")
        return web.json_response({"ok": True})

    async def handle_toggle_favorite(self, request: web.Request) -> web.Response:
        self._server._relay.toggle_favorite_requested.emit()
        return web.json_response({"ok": True})

    async def handle_toggle_repeat(self, request: web.Request) -> web.Response:
        self._server._relay.toggle_repeat_requested.emit()
        return web.json_response({"ok": True})

    async def handle_play_favorites(self, request: web.Request) -> web.Response:
        self._server._relay.play_favorites_requested.emit()
        return web.json_response({"ok": True})

    async def handle_play_top(self, request: web.Request) -> web.Response:
        self._server._relay.play_top_requested.emit()
        return web.json_response({"ok": True})

    async def handle_play_similar(self, request: web.Request) -> web.Response:
        self._server._relay.play_similar_requested.emit()
        return web.json_response({"ok": True})

    async def handle_play_artist(self, request: web.Request) -> web.Response:
        self._server._relay.play_artist_requested.emit()
        return web.json_response({"ok": True})

    async def handle_shutdown(self, request: web.Request) -> web.Response:
        from musicplayer.core.settings import AppSettings
        settings = AppSettings()
        if not settings.allow_remote_shutdown:
            return web.json_response({"ok": False, "error": "Remote shutdown is disabled"})
        self._server._relay.shutdown_requested.emit()
        return web.json_response({"ok": True})

    async def handle_check(self, request: web.Request) -> web.Response:
        return web.json_response({"computer_name": socket.gethostname()})