"""
Web Server Module

HTTP server for remote control of the player.
Provides REST API and web interface.
"""

import asyncio
import ipaddress
import sys
import threading
from pathlib import Path
from typing import Optional, Callable, List

from aiohttp import web
from PySide6.QtCore import QObject, Signal

from musicplayer.core.db import TrackInfo
from musicplayer.core.web_api import APIHandlers
from musicplayer.core.web_template import get_web_html


class WebServer(QObject):
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
    play_artist_requested = Signal()
    shutdown_requested = Signal()

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
        self._music_folder: Optional[str] = None

        self._on_play: Optional[Callable] = None
        self._on_pause: Optional[Callable] = None
        self._on_next: Optional[Callable] = None
        self._on_previous: Optional[Callable] = None
        self._on_set_volume: Optional[Callable[[float], None]] = None
        self._on_seek: Optional[Callable[[int], None]] = None
        self._on_play_track: Optional[Callable[[int], None]] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._api_handlers: Optional[APIHandlers] = None

    def start(self, port: int) -> bool:
        """Start the web server on the specified port."""
        self._port = port
        self._app = web.Application()
        self._api_handlers = APIHandlers(self)
        self._setup_routes()

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._runner = web.AppRunner(self._app)
        self._loop.run_until_complete(self._runner.setup())
        self._site = web.TCPSite(self._runner, '0.0.0.0', port)
        self._loop.run_until_complete(self._site.start())
        self._is_running = True
        self._loop.run_forever()

        return True

    def start_async(self, port: int) -> bool:
        """Start the web server in a separate thread."""
        self._port = port

        def run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            self._app = web.Application()
            self._api_handlers = APIHandlers(self)
            self._setup_routes()

            self._runner = web.AppRunner(self._app)
            self._loop.run_until_complete(self._runner.setup())
            self._site = web.TCPSite(self._runner, '0.0.0.0', port)
            self._loop.run_until_complete(self._site.start())

            self._is_running = True
            self._loop.run_forever()

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
        # Add CORS and security headers middleware
        self._app.middlewares.append(_security_middleware)

        self._app.router.add_get('/', self._handle_index)
        self._app.router.add_get('/Sonic-Flame.ico', self._handle_favicon)

        api = self._api_handlers
        self._app.router.add_get('/api/status', api.handle_status)
        self._app.router.add_get('/api/track', api.handle_track)
        self._app.router.add_get('/api/playlist', api.handle_playlist)
        self._app.router.add_get('/api/accent_color', api.handle_accent_color)
        self._app.router.add_get('/api/playing_data', api.handle_playing_data)
        self._app.router.add_post('/api/play', api.handle_play)
        self._app.router.add_post('/api/pause', api.handle_pause)
        self._app.router.add_get('/api/next', api.handle_next)
        self._app.router.add_get('/api/previous', api.handle_previous)
        self._app.router.add_post('/api/volume', api.handle_volume)
        self._app.router.add_post('/api/seek', api.handle_seek)
        self._app.router.add_post('/api/play_track', api.handle_play_track)
        self._app.router.add_get('/api/folders', api.handle_folders)
        self._app.router.add_post('/api/play_folder', api.handle_play_folder)
        self._app.router.add_post('/api/toggle_favorite', api.handle_toggle_favorite)
        self._app.router.add_get('/api/toggle_repeat', api.handle_toggle_repeat)
        self._app.router.add_get('/api/play_favorites', api.handle_play_favorites)
        self._app.router.add_get('/api/play_top', api.handle_play_top)
        self._app.router.add_get('/api/play_similar', api.handle_play_similar)
        self._app.router.add_get('/api/play_artist', api.handle_play_artist)
        self._app.router.add_get('/api/check', api.handle_check)
        self._app.router.add_post('/api/shutdown', api.handle_shutdown)

    def stop(self):
        """Stop the web server asynchronously (non-blocking)."""
        self._is_running = False
        loop = getattr(self, '_loop', None)
        if loop is None:
            return
        self._loop = None  # prevent double-stop
        try:
            async def _cleanup():
                if hasattr(self, '_runner'):
                    await self._runner.cleanup()
                for task in asyncio.all_tasks(loop):
                    task.cancel()
                loop.stop()
            asyncio.run_coroutine_threadsafe(_cleanup(), loop)
        except Exception:
            pass

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
        return web.Response(text=get_web_html(), content_type='text/html')

    async def _handle_favicon(self, request: web.Request) -> web.Response:
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


def _is_private_ip(ip_str: str) -> bool:
    """Check if IP is from local/private network."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except ValueError:
        return False


async def _security_middleware(app, handler):
    """Restrict to local network and add security headers."""
    async def middleware_handler(request):
        peer_name = request.transport.get_extra_info('peername')
        if peer_name:
            ip = peer_name[0]
            if not _is_private_ip(ip):
                return web.Response(status=403, text='Forbidden: Access restricted to local network')
        response = await handler(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if request.method not in ('GET', 'POST'):
            return web.Response(status=405, text='Method Not Allowed')
        return response
    return middleware_handler