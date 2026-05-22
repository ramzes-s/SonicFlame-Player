"""
SMTC Manager — Windows System Media Transport Controls integration.

Registers the player with Windows SMTC so that:
- Volume flyout shows now-playing info (title, artist, album, cover)
- Media keys work through the system
- Windows auto-prevents sleep during playback
"""

import sys
import os
import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SMTCManager(QObject):
    """Manages Windows System Media Transport Controls integration."""

    play_requested = Signal()
    pause_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._smtc = None
        self._updater = None
        self._music_props = None
        self._token = None
        self._media_player = None
        self._thumbnail_stream = None
        self._temp_thumb_dir = None  # lazily created
        self._prev_thumb_path = None  # for cleanup

        if sys.platform != "win32":
            logger.info("[SMTC] Not available on non-Windows platforms")
            return

        try:
            # Create a MediaPlayer just to hold an SMTC instance alive.
            # Desktop Win32 apps cannot use get_for_current_view() because
            # there is no CoreWindow.  MediaPlayer creates a valid SMTC even
            # without a CoreWindow.
            import winrt.windows.media.playback as wmp
            import winrt.windows.media as wm

            self._media_player = wmp.MediaPlayer()
            self._smtc = self._media_player.system_media_transport_controls

            if self._smtc is None:
                logger.warning("[SMTC] system_media_transport_controls is None")
                self._media_player = None
                return

            self._smtc.is_play_enabled = True
            self._smtc.is_pause_enabled = True
            self._smtc.is_next_enabled = True
            self._smtc.is_previous_enabled = True

            self._updater = self._smtc.display_updater
            self._updater.type = wm.MediaPlaybackType.MUSIC
            self._music_props = self._updater.music_properties

            self._media_player.audio_category = wmp.MediaPlayerAudioCategory.MEDIA
            self._media_player.volume = 0.0

            self._token = self._smtc.add_button_pressed(self._on_button_pressed)

            logger.info("[SMTC] Initialized successfully")
        except Exception as e:
            logger.warning("[SMTC] Failed to initialize: %s", e)
            self._smtc = None
            self._media_player = None

    @property
    def available(self) -> bool:
        return self._smtc is not None

    def update_track_info(self, track) -> None:
        if not self.available or not track:
            return
        try:
            self._music_props.title = track.title or ""
            self._music_props.artist = track.artist or ""
            self._music_props.album_title = track.album or ""
            self._set_thumbnail(track)
            self._updater.update()
            logger.debug("[SMTC] Updated track: %s - %s", track.artist, track.title)
        except Exception as e:
            logger.warning("[SMTC] Failed to update track info: %s", e)

    def set_playback_status(self, status: str) -> None:
        if not self.available:
            return
        try:
            import winrt.windows.media as wm
            status_map = {
                "playing": wm.MediaPlaybackStatus.PLAYING,
                "paused": wm.MediaPlaybackStatus.PAUSED,
                "stopped": wm.MediaPlaybackStatus.STOPPED,
            }
            mapped = status_map.get(status.lower())
            if mapped is not None:
                self._smtc.playback_status = mapped
                logger.debug("[SMTC] Status: %s", status)
        except Exception as e:
            logger.warning("[SMTC] Failed to set playback status: %s", e)

    def clear_playback(self) -> None:
        if not self.available:
            return
        try:
            import winrt.windows.media as wm
            self._music_props.title = ""
            self._music_props.artist = ""
            self._music_props.album_title = ""
            self._updater.thumbnail = None
            self._updater.update()
            self._smtc.playback_status = wm.MediaPlaybackStatus.STOPPED
        except Exception as e:
            logger.warning("[SMTC] Failed to clear playback: %s", e)

    def close(self) -> None:
        if self._smtc and self._token is not None:
            try:
                self._smtc.remove_button_pressed(self._token)
            except Exception:
                pass
        self.clear_playback()
        self._smtc = None
        self._updater = None
        self._music_props = None
        self._token = None
        self._media_player = None
        self._thumbnail_stream = None
        # Clean up temp thumbnails
        if self._prev_thumb_path and os.path.exists(self._prev_thumb_path):
            try:
                os.unlink(self._prev_thumb_path)
            except Exception:
                pass
        self._prev_thumb_path = None
        if self._temp_thumb_dir and os.path.isdir(self._temp_thumb_dir):
            try:
                os.rmdir(self._temp_thumb_dir)
            except Exception:
                pass
        logger.info("[SMTC] Closed")

    def _set_thumbnail(self, track) -> None:
        self._updater.thumbnail = None
        self._thumbnail_stream = None

        try:
            jpg_data = self._prepare_cover_jpeg(track)
            if jpg_data is None:
                return

            import concurrent.futures
            import tempfile

            if self._temp_thumb_dir is None:
                self._temp_thumb_dir = os.path.join(
                    tempfile.gettempdir(), "SonicFlame-SMTC"
                )
                os.makedirs(self._temp_thumb_dir, exist_ok=True)

            tmp_path = os.path.join(self._temp_thumb_dir, f"thumb_{os.urandom(4).hex()}.jpg")

            def _do_on_mta(updater, data, path):
                import winrt.windows.storage.streams as wss
                import winrt.windows.storage as ws
                with open(path, "wb") as f:
                    f.write(data)
                file = ws.StorageFile.get_file_from_path_async(path).get()
                updater.thumbnail = wss.RandomAccessStreamReference.create_from_file(file)
                updater.update()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                ex.submit(_do_on_mta, self._updater, jpg_data, tmp_path).result()

            # Delete previous temp file
            if self._prev_thumb_path and os.path.exists(self._prev_thumb_path):
                try:
                    os.unlink(self._prev_thumb_path)
                except Exception:
                    pass
            self._prev_thumb_path = tmp_path

            logger.debug("[SMTC] Thumbnail: set via MTA StorageFile")
        except Exception as e:
            logger.debug("[SMTC] Thumbnail failed: %s", e)

    def _prepare_cover_jpeg(self, track):
        """Extract cover and convert to JPEG bytes. Returns None on failure."""
        cover_data = getattr(track, "cover_data", None)
        if not cover_data:
            from musicplayer.core.db.cache import _load_cover
            cover_data = _load_cover(track.filepath)
        if not cover_data:
            logger.debug("[SMTC] Thumbnail: no cover data")
            return None

        from PIL import Image
        import io
        img = Image.open(io.BytesIO(cover_data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > 300 or img.height > 300:
            ratio = 300 / max(img.width, img.height)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def _on_button_pressed(self, sender, args) -> None:
        try:
            import winrt.windows.media as wm
            button = args.button
            if button == wm.SystemMediaTransportControlsButton.PLAY:
                self.play_requested.emit()
            elif button == wm.SystemMediaTransportControlsButton.PAUSE:
                self.pause_requested.emit()
            elif button == wm.SystemMediaTransportControlsButton.NEXT:
                self.next_requested.emit()
            elif button == wm.SystemMediaTransportControlsButton.PREVIOUS:
                self.previous_requested.emit()
        except Exception as e:
            logger.warning("[SMTC] Button handler error: %s", e)
