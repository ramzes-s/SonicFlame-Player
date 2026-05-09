"""
Web Server Module

HTTP server for remote control of the player.
Provides REST API and web interface.
"""

import asyncio
import base64
import socket
import threading
from pathlib import Path
from typing import Optional, Callable, List
from aiohttp import web
from PySide6.QtCore import QObject, Signal
from musicplayer import config as cfg
from musicplayer.core.db import TrackInfo, get_all_folders


class WebServer(QObject):
    # Signals emitted from web server to be handled by the player/UI
    play_requested = Signal()
    pause_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    volume_requested = Signal(float)
    seek_requested = Signal(int)
    play_track_requested = Signal(int)
    play_folder_requested = Signal(str)
    toggle_favorite_requested = Signal()
    toggle_repeat_requested = Signal()
    play_favorites_requested = Signal()
    play_top_requested = Signal()
    play_similar_requested = Signal()

    def __init__(self):
        super().__init__()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._port = 8080
        self._is_running = False

        self._playing = False
        self._position = 0
        self._duration = 0
        self._volume = 0.5
        self._repeat = "none"
        self._sort_mode = "artist"
        self._current_track: Optional[TrackInfo] = None
        self._current_index = -1
        self._playlist: List[TrackInfo] = []
        self._favorite_filepaths = set()
        self._playlist_title = ""

        self._on_play: Optional[Callable] = None
        self._on_pause: Optional[Callable] = None
        self._on_next: Optional[Callable] = None
        self._on_previous: Optional[Callable] = None
        self._on_set_volume: Optional[Callable[[float], None]] = None
        self._on_seek: Optional[Callable[[int], None]] = None
        self._on_play_track: Optional[Callable[[int], None]] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, port: int) -> bool:
        """Start the web server on the specified port."""
        self._port = port
        self._app = web.Application()

        # Register routes (now consolidated via _setup_routes)
        self._setup_routes()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._runner = web.AppRunner(self._app)
        loop.run_until_complete(self._runner.setup())
        self._site = web.TCPSite(self._runner, '0.0.0.0', port)
        loop.run_until_complete(self._site.start())
        self._is_running = True
        loop.run_forever()

        # Note: loop_forever is blocking; _is_running is already set above for status checks.
        return True

    def start_async(self, port: int) -> bool:
        """Backward compatibility shim.

        For compatibility with existing callers, keep original behavior
        by starting the server in a separate thread as before.
        """
        import threading
        self._port = port

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self._app = web.Application()
            self._setup_routes()

            self._runner = web.AppRunner(self._app)
            loop.run_until_complete(self._runner.setup())
            self._site = web.TCPSite(self._runner, '0.0.0.0', port)
            loop.run_until_complete(self._site.start())

            self._is_running = True
            loop.run_forever()

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        return True

    def set_signal_emitter(self, emitter):
        """Set the signal emitter for Qt thread-safe callbacks."""
        self._signal_emitter = emitter

    def _emit_signal(self, signal_name: str, *args):
        """Emit a signal to the Qt main thread."""
        print(f"[WebServer] _emit_signal: {signal_name} args={args}")
        if hasattr(self, '_signal_emitter') and self._signal_emitter:
            self._signal_emitter(signal_name, *args)
        else:
            print(f"[WebServer] No signal emitter set!")

    def _setup_routes(self):
        """Setup all routes."""
        self._app.router.add_get('/', self._handle_index)
        self._app.router.add_get('/Sonic-Flame.ico', self._handle_favicon)
        self._app.router.add_get('/api/status', self._handle_status)
        self._app.router.add_get('/api/track', self._handle_track)
        self._app.router.add_get('/api/playlist', self._handle_playlist)
        self._app.router.add_get('/api/accent_color', self._handle_accent_color)
        self._app.router.add_get('/api/playing_data', self._handle_playing_data)
        self._app.router.add_post('/api/play', self._handle_play)
        self._app.router.add_post('/api/pause', self._handle_pause)
        self._app.router.add_get('/api/next', self._handle_next)
        self._app.router.add_get('/api/previous', self._handle_previous)
        self._app.router.add_post('/api/volume', self._handle_volume)
        self._app.router.add_post('/api/seek', self._handle_seek)
        self._app.router.add_post('/api/play_track', self._handle_play_track)
        self._app.router.add_get('/api/folders', self._handle_folders)
        self._app.router.add_post('/api/play_folder', self._handle_play_folder)
        self._app.router.add_post('/api/toggle_favorite', self._handle_toggle_favorite)
        self._app.router.add_get('/api/toggle_repeat', self._handle_toggle_repeat)
        self._app.router.add_get('/api/play_favorites', self._handle_play_favorites)
        self._app.router.add_get('/api/play_top', self._handle_play_top)
        self._app.router.add_get('/api/play_similar', self._handle_play_similar)
        self._app.router.add_get('/api/check', self._handle_check)

    def stop(self):
        """Stop the web server."""
        if hasattr(self, '_runner') and self._runner:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._runner.cleanup())
            except Exception:
                pass
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def get_port(self) -> int:
        return self._port

    def update_state(self, playing: bool, position: int, duration: int,
                     volume: float, repeat: str):
        self._playing = playing
        self._position = position
        self._duration = duration
        self._volume = volume
        self._repeat = repeat

    def update_sort_mode(self, sort_mode: str):
        """Update the playlist sort mode."""
        self._sort_mode = sort_mode

    def update_track(self, track: Optional[TrackInfo]):
        self._current_track = track

    def update_playlist_title(self, title: str):
        """Update the current playlist title."""
        self._playlist_title = title

    def update_favorites(self, favorite_filepaths: set):
        """Update the set of favorite filepaths."""
        self._favorite_filepaths = favorite_filepaths

    def update_current_index(self, index: int):
        self._current_index = index

    def update_playlist(self, tracks: List[TrackInfo]):
        print(f"[WebServer] update_playlist storing {len(tracks)} tracks, first: {tracks[0].filepath if tracks else 'none'}")
        self._playlist = tracks

    async def _handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=self._get_html(), content_type='text/html')

    async def _handle_favicon(self, request: web.Request) -> web.Response:
        import sys
        checked = []
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                icon_path = Path(meipass) / "Sonic-Flame.ico"
                checked.append(str(icon_path))
                if icon_path.exists():
                    return web.Response(body=icon_path.read_bytes(), content_type='image/x-icon')
            icon_path = Path(sys.executable).parent / "Sonic-Flame.ico"
            checked.append(str(icon_path))
            if icon_path.exists():
                return web.Response(body=icon_path.read_bytes(), content_type='image/x-icon')
        else:
            icon_path = Path(__file__).parent.parent.parent / "Sonic-Flame.ico"
            checked.append(str(icon_path))
            if icon_path.exists():
                return web.Response(body=icon_path.read_bytes(), content_type='image/x-icon')
            icon_path = Path(__file__).parent / "Sonic-Flame.ico"
            checked.append(str(icon_path))
            if icon_path.exists():
                return web.Response(body=icon_path.read_bytes(), content_type='image/x-icon')
        print(f"[WebServer] Favicon not found, checked: {checked}")
        return web.Response(text="Not Found", status=404)

    async def _handle_status(self, request: web.Request) -> web.Response:
        return web.json_response({
            "playing": self._playing,
            "position": self._position,
            "duration": self._duration,
            "volume": self._volume,
            "repeat": self._repeat,
            "sort_mode": self._sort_mode
        })

    async def _handle_track(self, request: web.Request) -> web.Response:
        if not self._current_track:
            return web.json_response(None)

        cover_b64 = None
        if self._current_track.cover_data:
            cover_b64 = base64.b64encode(self._current_track.cover_data).decode()

        return web.json_response({
            "title": self._current_track.title,
            "artist": self._current_track.artist,
            "album": self._current_track.album,
            "duration": self._current_track.duration,
            "genre": self._current_track.genre,
            "bitrate": self._current_track.bitrate,
            "is_favorite": self._current_track.filepath in self._favorite_filepaths,
            "cover": cover_b64,
            "playlist_title": self._playlist_title
        })

    async def _handle_playlist(self, request: web.Request) -> web.Response:
        tracks = []
        for t in self._playlist:
            tracks.append({
                "title": t.title,
                "artist": t.artist,
                "album": t.album,
                "duration": t.duration,
                "filepath": t.filepath
            })
        return web.json_response(tracks)

    async def _handle_accent_color(self, request: web.Request) -> web.Response:
        return web.json_response({"color": cfg.get_accent_color()})

    async def _handle_playing_data(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": {
                "playing": self._playing,
                "position": self._position,
                "duration": self._duration,
                "volume": self._volume,
                "repeat": self._repeat
            },
            "current_index": self._current_index,
            "current_track_filepath": self._current_track.filepath if self._current_track else None,
            "is_favorite": self._current_track.filepath in self._favorite_filepaths if self._current_track else False,
            "accent_color": cfg.get_accent_color(),
            "sort_mode": self._sort_mode
        })

    async def _handle_play(self, request: web.Request) -> web.Response:
        print(f"[WebServer] _handle_play called")
        self.play_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_pause(self, request: web.Request) -> web.Response:
        print(f"[WebServer] _handle_pause called")
        self.pause_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_next(self, request: web.Request) -> web.Response:
        print(f"[WebServer] _handle_next called")
        self.next_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_previous(self, request: web.Request) -> web.Response:
        self.previous_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_volume(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            volume = float(data.get("value", 0.5))
            self.volume_requested.emit(volume)
        except Exception:
            pass
        return web.json_response({"ok": True})

    async def _handle_seek(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            position = int(data.get("position", 0))
            self.seek_requested.emit(position)
        except Exception:
            pass
        return web.json_response({"ok": True})

    async def _handle_play_track(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            index = int(data.get("index", 0))
            self.play_track_requested.emit(index)
        except Exception:
            pass
        return web.json_response({"ok": True})

    async def _handle_folders(self, request: web.Request) -> web.Response:
        """Return list of indexed folders from DB."""
        folders = get_all_folders()
        result = []
        for f in folders:
            path = f[0]
            # Extract folder name (last part of path)
            name = path.replace('\\', '/').split('/')[-1]
            result.append({"path": path, "name": name, "track_count": f[1]})
        return web.json_response(result)

    async def _handle_play_folder(self, request: web.Request) -> web.Response:
        """Emit signal to play selected folder."""
        try:
            data = await request.json()
            path = data.get("path", "")
            if path:
                self.play_folder_requested.emit(path)
        except Exception:
            pass
        return web.json_response({"ok": True})

    async def _handle_toggle_favorite(self, request: web.Request) -> web.Response:
        """Emit signal to toggle favorite status of the current track."""
        self.toggle_favorite_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_toggle_repeat(self, request: web.Request) -> web.Response:
        """Cycle through repeat modes: none -> all -> one -> none."""
        self.toggle_repeat_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_play_favorites(self, request: web.Request) -> web.Response:
        """Load favorites playlist."""
        self.play_favorites_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_play_top(self, request: web.Request) -> web.Response:
        """Load top tracks playlist."""
        self.play_top_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_play_similar(self, request: web.Request) -> web.Response:
        """Load similar tracks playlist."""
        self.play_similar_requested.emit()
        return web.json_response({"ok": True})

    async def _handle_check(self, request: web.Request) -> web.Response:
        """Return computer name."""
        return web.json_response({"computer_name": socket.gethostname()})

    def _get_html(self) -> str:
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>SonicFlame Player</title>
    <link rel="icon" type="image/x-icon" href="/Sonic-Flame.ico">
    <style>
        :root { --accent-color: #ed6a02; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: #000; color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            height: 100%; width: 100%; overflow-x: hidden;
        }
        body {
            display: flex; justify-content: center; align-items: flex-start;
            padding: 26px 16px; min-height: 100vh;
        }
        .container {
            width: 100%; max-width: 900px;
            display: flex; gap: 4px;
        }
        .player-section {
            display: flex; flex-direction: row; align-items: flex-start;
            gap: 16px; flex-shrink: 0;
            position: sticky;
            top: 26px;
            max-height: calc(100vh - 52px);
            overflow: hidden;
        }
        .player-main {
            display: flex; flex-direction: column; align-items: center;
            width: 44%;
            min-width: 360px; max-width: 420px;
        }
        .cover {
            width: 100%; aspect-ratio: 1;
            max-width: 420px; border-radius: 12px;
            background: #1a1a1a; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5); margin-bottom: 16px;
        }
        .cover img { width: 100%; height: 100%; object-fit: cover; border-radius: 12px; }
        
        .track-info {
            text-align: center; margin-bottom: 16px; width: 100%;
            min-height: 56px;
        }
        .track-title {
            font-size: 15px; font-weight: bold;
            color: #fff; margin-bottom: 4px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .track-artist {
            font-size: 13px; color: var(--accent-color);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .track-album {
            font-size: 11px; color: #666; margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        
        .seek-container { display: flex; align-items: center; gap: 10px; width: 100%; margin-bottom: 12px; }
        .seek-bar {
            flex: 1 1 auto; height: 4px; min-width: 0;
            -webkit-appearance: none; appearance: none;
            background: transparent;
            border-radius: 2px; outline: none; cursor: pointer;
        }
        .seek-bar::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px; height: 14px; margin-top: -5px; /* (track_height - thumb_height) / 2 */
            background: var(--accent-color); border-radius: 50%; cursor: pointer;
        }
        .seek-bar::-moz-range-thumb {
            width: 14px; height: 14px;
            background: var(--accent-color); border-radius: 50%; cursor: pointer; border: none;
        }
        .seek-bar::-webkit-slider-runnable-track {
            height: 4px; border-radius: 2px;
            background: linear-gradient(to right, var(--accent-color) var(--seek-before-width, 0%), #333 var(--seek-before-width, 0%));
        }
        .seek-bar::-moz-range-track {
            height: 4px; border-radius: 2px;
            background: linear-gradient(to right, var(--accent-color) var(--seek-before-width, 0%), #333 var(--seek-before-width, 0%));
        }

        .time-display {
            font-size: 11px; color: #fff; white-space: nowrap;
        }
        .time-current { flex: 0 0 auto; }
        .time-total { flex: 0 0 auto; }
        
        .controls {
            display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 12px;
            position: relative;
        }
        .btn {
            background: none; border: none; color: #fff; cursor: pointer;
            transition: color 0.2s; display: flex; align-items: center; justify-content: center;
            padding: 0;
        }
        .btn:hover { color: #ccc; }
        .btn:active { color: #888; }
        .btn svg { fill: currentColor; }
        
        .btn-play {
            width: 78px; height: 78px;
        }
        
        .playlist-section {
            flex: 1; min-width: 0; display: flex; flex-direction: column;
            overflow: hidden;
            border-radius: 8px;
        }
        .playlist {
            background: #0a0a0a; border-radius: 8px;
            flex: 1; overflow-y: auto;
            min-height: 200px;
            max-height: calc(100vh - 80px);
        }
        .playlist::-webkit-scrollbar { width: 6px; }
        .playlist::-webkit-scrollbar-track { background: #0a0a0a; }
        .playlist::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        .playlist::-webkit-scrollbar-thumb:hover { background: #444; }

        .folder-dropdown::-webkit-scrollbar { width: 4px; }
        .folder-dropdown::-webkit-scrollbar-track { background: #0a0a0a; }
        .folder-dropdown::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
        .folder-dropdown::-webkit-scrollbar-thumb:hover { background: #444; }
        
        .offline-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.95);
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 20px;
            z-index: 1000;
        }
        .offline-overlay.visible { display: flex; }
        .offline-text { color: #888; font-size: 16px; text-align: center; }
        .btn-refresh {
            padding: 12px 24px; background: var(--accent-color); color: #fff;
            border: none; border-radius: 8px; font-size: 14px; cursor: pointer;
        }
        .btn-refresh:hover { opacity: 0.9; }

        .folder-dropdown {
            display: none;
            position: absolute;
            bottom: 5px;
            left: -10px;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            min-width: 240px;
            max-height: 480px;
            overflow-y: auto;
            z-index: 100;
        }
        .folder-dropdown.visible { display: block; }
        .folder-item {
            padding: 10px 12px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #222;
        }
        .folder-item:hover { background: #151515; }
        .folder-item .path {
            color: #fff;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 220px;
        }
        .folder-item .count {
            color: #999;
            font-size: 11px;
            margin-left: 8px;
            flex-shrink: 0;
        }
        
        .playlist-item {
            padding: 10px 12px; border-bottom: 1px solid #1a1a1a; cursor: pointer;
            display: flex; justify-content: space-between; align-items: center;
            height: 52px;
            box-sizing: border-box;
        }
        .playlist-item:hover { background: #151515; }
        .playlist-item.active {
            background: #1a1a1a;
            border-left: 3px solid var(--accent-color);
            padding-left: 9px;
        }
        .playlist-item .info {
            display: flex; flex-direction: column; justify-content: center;
            min-width: 0; flex: 1;
        }
        .playlist-item .title {
            font-size: 13px; color: #fff;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .playlist-item .artist {
            font-size: 11px; color: #666;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .playlist-item .duration {
            font-size: 11px; color: #666; white-space: nowrap; margin-left: 8px;
            flex-shrink: 0;
        }
        
        @media (max-width: 790px) {
            body { padding: 0 12px 12px; }
            .container {
                flex-direction: column;
                align-items: center;
                gap: 6px;
            }
            .player-section {
                width: 100%;
                justify-content: center;
                position: sticky;
                top: 0;
                max-height: none;
                background: #000;
                z-index: 10;
                padding: 12px 0 6px 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            }
            .player-main {
                width: 90%;
                max-width: none;
                min-width: 0;
            }
            .cover {
                width: 90%;
                margin-left: auto; margin-right: auto;
            }
            .playlist-section {
                width: 100%;
                min-height: 200px;
            }
            .playlist {
                max-height: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="player-section">
            <div class="player-main">
                <div class="cover" id="cover"></div>
                <div class="track-info">
                    <div class="track-title" id="title">-</div>
                    <div class="track-artist" id="artist">-</div>
                    <div class="track-album" id="album">-</div>
                </div>
                <div class="seek-container">
                    <span class="time-display time-current" id="currentTime">0:00</span>
                    <input type="range" class="seek-bar" id="seek" min="0" max="100" value="0">
                    <span class="time-display time-total" id="totalTime">0:00</span>
                </div>
                <div class="controls">
                    <button class="btn" id="folderBtn" title="Выбрать папку">
                        <svg width="26" height="26" viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                    </button>
                    <button class="btn" id="prevBtn">
                        <svg width="32" height="32" viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                    </button>
                    <button class="btn btn-play" id="playBtn">
                        <svg id="playIcon" width="44" height="44" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                    <button class="btn" id="nextBtn">
                        <svg width="32" height="32" viewBox="0 0 24 24"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                    </button>
                    <button class="btn" id="heartBtn" title="Избранное">
                        <svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                    </button>
                    <div class="folder-dropdown" id="folderDropdown">
                        <div class="folder-list" id="folderList"></div>
                    </div>
                </div>
            </div>
        </div>
        <div class="playlist-section">
            <div class="playlist" id="playlist"></div>
        </div>
    </div>
    <div class="offline-overlay" id="offlineOverlay">
        <div class="offline-text">Плеер выключен</div>
        <button class="btn-refresh" onclick="location.reload()">Обновить страницу</button>
    </div>
    <script>
        let currentIndex = -1;
        let currentFilepath = null;
        let isPlaying = false;
        let isOffline = false;
        let pollInterval = null;
        let abortController = null;
        let lastPlaylistHash = '';
        let clientSeekTimer = null;

        function getPlaylistHash(tracks) {
            return tracks.map(t => t.filepath).join('|');
        }

        async function fetchWithTimeout(url, timeout = 3000) {
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), timeout);
            try {
                const res = await fetch(url, { signal: controller.signal });
                clearTimeout(id);
                return res;
            } catch (e) {
                clearTimeout(id);
                if (e.name !== 'AbortError') {
                    console.log('fetch error:', e.message, e.name);
                    showOffline();
                }
                return null;
            }
        }

        function formatTime(ms) {
            const s = Math.floor(ms / 1000);
            const m = Math.floor(s / 60);
            return m + ':' + (s % 60).toString().padStart(2, '0');
        }

        function showOffline() {
            isOffline = true;
            clearInterval(pollInterval);
            document.getElementById('offlineOverlay').classList.add('visible');
        }

        function hideOffline() {
            isOffline = false;
            document.getElementById('offlineOverlay').classList.remove('visible');
        }

        function animateSeekBar() {
            const seekBar = document.getElementById('seek');
            const currentTimeDisplay = document.getElementById('currentTime');
            
            let currentValue = parseFloat(seekBar.value);
            let maxValue = parseFloat(seekBar.max);
            
            if (currentValue < maxValue) {
                currentValue += 100; // Increment by the interval duration (100ms)
                seekBar.value = currentValue;
                
                currentTimeDisplay.textContent = formatTime(currentValue);

                const percent = maxValue > 0 ? (currentValue / maxValue) * 100 : 0;
                seekBar.style.setProperty('--seek-before-width', percent + '%');
            }
        }

        let initialLoad = true;

        async function updateStatus() {
            if (isOffline) return;
            const res = await fetchWithTimeout('/api/playing_data');
            if (!res || !res.ok) {
                if (!isOffline) showOffline();
                return;
            }

            hideOffline();

            try {
                const data = await res.json();

                document.documentElement.style.setProperty('--accent-color', data.accent_color);

                const heartIcon = document.getElementById('heartBtn');
                if (heartIcon) {
                    heartIcon.style.color = data.is_favorite ? 'var(--accent-color)' : '#fff';
                }

                const status = data.status;
                const newIndex = data.current_index;
                const newFilepath = data.current_track_filepath;

                const trackChanged = (newIndex !== currentIndex || newFilepath !== currentFilepath) && newIndex !== -1;

                if (trackChanged) {
                    currentIndex = newIndex;
                    currentFilepath = newFilepath;
                    highlightCurrentTrack();
                }

                // If track changes, or it's the first load, update the info.
                // The playlist will be updated automatically inside updateTrackInfo.
                if (initialLoad) {
                    initialLoad = false;
                    await updateTrackInfo();
                } else if (trackChanged) {
                    await updateTrackInfo();
                }

                const prevPlaying = isPlaying;
                isPlaying = status.playing;
                // If playback just started, update info (which will also update playlist)
                if (isPlaying && !prevPlaying) {
                    await updateTrackInfo();
                }

                const playIcon = document.getElementById('playIcon');
                playIcon.setAttribute('width', status.playing ? '44' : '44');
                playIcon.innerHTML = status.playing
                    ? '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>'
                    : '<path d="M8 5v14l11-7z"/>';

                const seekBar = document.getElementById('seek');
                seekBar.value = status.position;
                seekBar.max = status.duration || 100;
                
                const percent = status.duration > 0 ? (status.position / status.duration) * 100 : 0;
                seekBar.style.setProperty('--seek-before-width', percent + '%');

                document.getElementById('currentTime').textContent = formatTime(status.position);
                document.getElementById('totalTime').textContent = formatTime(status.duration);

                if (status.playing && !clientSeekTimer) {
                    clientSeekTimer = setInterval(animateSeekBar, 100);
                } else if (!status.playing && clientSeekTimer) {
                    clearInterval(clientSeekTimer);
                    clientSeekTimer = null;
                }
            } catch (e) {
                if (!isOffline) showOffline();
            }
        }

        async function updatePlaylist() {
            try {
                const res = await fetch('/api/playlist');
                if (!res.ok) return;
                const tracks = await res.json();
                const container = document.getElementById('playlist');
                if (!container) return;
                if (tracks.length === 0) return;
                lastPlaylistHash = getPlaylistHash(tracks);
                container.innerHTML = tracks.map((t, i) =>
                    '<div class="playlist-item' + (i === currentIndex ? ' active' : '') + '" data-index="' + i + '">' +
                    '<div class="info"><div class="title">' + (t.title || '-') + '</div><div class="artist">' + (t.artist || '-') + '</div></div>' +
                    '<div class="duration">' + formatTime((t.duration || 0) * 1000) + '</div></div>'
                ).join('');
            } catch (e) { console.error(e); }
        }

        async function updateTrackInfo() {
            try {
                const res = await fetch('/api/track');
                if (!res.ok) return;
                const track = await res.json();

                if (!track) return;

                // Ironclad rule: update playlist after updating track.
                await updatePlaylist();

                document.getElementById('title').textContent = track.title || '-';
                document.getElementById('artist').textContent = track.artist || '-';
                document.getElementById('album').textContent = track.album || '-';
                if (track.cover) {
                    document.getElementById('cover').innerHTML = '<img src="data:image/webp;base64,' + track.cover + '">';
                } else {
                    document.getElementById('cover').innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" style="fill:#333"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>';
                }
            } catch (e) { console.error(e); }
        }

        function highlightCurrentTrack() {
            const container = document.getElementById('playlist');
            if (!container) return;
            const items = container.querySelectorAll('.playlist-item');
            items.forEach((item, i) => {
                if (i === currentIndex) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
            const activeItem = container.querySelector('.playlist-item.active');
            if (activeItem) {
                activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        document.getElementById('playBtn').onclick = () => {
            fetch(isPlaying ? '/api/pause' : '/api/play', {method: 'POST'}).then(() => updateTrackInfo());
        };
        document.getElementById('prevBtn').onclick = () => {
            fetch('/api/previous').then(() => updateTrackInfo());
        };
        document.getElementById('nextBtn').onclick = () => {
            fetch('/api/next').then(() => updateTrackInfo());
        };
        document.getElementById('heartBtn').onclick = () => {
            fetch('/api/toggle_favorite', {method: 'POST'}).then(updateStatus);
        };
        document.getElementById('seek').onchange = (e) => fetch('/api/seek', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position: parseInt(e.target.value)})
        });
        document.getElementById('playlist').onclick = (e) => {
            const item = e.target.closest('.playlist-item');
            if (item) {
                currentIndex = parseInt(item.dataset.index);
                highlightCurrentTrack();
                fetch('/api/play_track', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: currentIndex})
                }).then(() => updateTrackInfo());
                document.querySelector('.player-section').scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        };

        let folderDropdownVisible = false;

        async function loadFolders() {
            const res = await fetch('/api/folders');
            if (!res.ok) return;
            const folders = await res.json();
            const container = document.getElementById('folderList');
            if (!container) return;
            container.innerHTML = folders.map(f =>
                '<div class="folder-item" data-path="' + f.path + '">' +
                '<span class="path" title="' + f.path + '">' + f.name + '</span>' +
                '<span class="count">' + f.track_count + '</span>' +
                '</div>'
            ).join('');

            container.querySelectorAll('.folder-item').forEach(item => {
                item.onclick = () => {
                    fetch('/api/play_folder', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({path: item.dataset.path})
                    }).then(() => {
                        hideFolderDropdown();
                        updateStatus();
                    });
                };
            });
        }

        function showFolderDropdown() {
            loadFolders();
            document.getElementById('folderDropdown').classList.add('visible');
            folderDropdownVisible = true;
        }

        function hideFolderDropdown() {
            document.getElementById('folderDropdown').classList.remove('visible');
            folderDropdownVisible = false;
        }

        document.getElementById('folderBtn').onclick = (e) => {
            e.stopPropagation();
            if (folderDropdownVisible) {
                hideFolderDropdown();
            } else {
                showFolderDropdown();
            }
        };

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#folderBtn') && !e.target.closest('#folderDropdown')) {
                hideFolderDropdown();
            }
        });

        updateStatus();
        pollInterval = setInterval(updateStatus, 1000);
    </script>
</body>
</html>"""
