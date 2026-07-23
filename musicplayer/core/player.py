"""
Audio Player Module

Wrapper around QMediaPlayer providing playback functionality
with signals for UI updates.
"""

import json
import time

from PySide6.QtCore import QObject, Signal, QUrl, QPropertyAnimation
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from musicplayer import config as cfg
from musicplayer.core.db import TrackInfo
from musicplayer.core.settings import AppSettings
from musicplayer.core import settings
from musicplayer.core.smtc_manager import SMTCManager
from musicplayer.core.audio_device_manager import AudioDeviceManager


class AudioPlayer(QObject):
    """
    High-level audio player wrapper.

    Provides convenient signals and simplified API for playback control.
    """

    # Signals
    state_changed = Signal(QMediaPlayer.PlaybackState)
    position_changed = Signal(int)  # milliseconds
    duration_changed = Signal(int)  # milliseconds
    volume_changed = Signal(float)  # 0.0 to 1.0
    media_status_changed = Signal(QMediaPlayer.MediaStatus)
    error_occurred = Signal(str)
    smtc_next_requested = Signal()
    smtc_previous_requested = Signal()
    empty_play_requested = Signal()  # Play pressed but no source loaded

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_track: TrackInfo | None = None
        self._now_playing_written = None  # filepath of last track written to now_playing.json

        # Audio device manager (handles selection + fallback)
        self._device_manager = AudioDeviceManager(self)
        self._device_manager.device_changed.connect(self._on_device_changed)

        # Create audio output
        self._audio_output = self._device_manager.create_audio_output(self)
        self._audio_output.setVolume(0.5)

        # Windows sleep blocker – enabled based on settings
        from .windows_sleep_blocker import WindowsSleepBlocker
        self._sleep_blocker = WindowsSleepBlocker()
        self._prevent_sleep_enabled = settings.get_prevent_sleep()
        if self._prevent_sleep_enabled:
            self._sleep_blocker.enable()

        # Create media player
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)

        # Connect signals
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

        # Fade on play/pause
        self._fade_anim: QPropertyAnimation | None = None
        self._fade_target_volume: float = self._audio_output.volume()

        # SMTC integration
        self._smtc = SMTCManager(self)
        self._smtc.play_requested.connect(self.toggle_play_pause)
        self._smtc.pause_requested.connect(self.toggle_play_pause)
        self._smtc.next_requested.connect(self.smtc_next_requested.emit)
        self._smtc.previous_requested.connect(self.smtc_previous_requested.emit)

    def close_smtc(self):
        """Shut down the SMTC manager."""
        if hasattr(self, '_smtc'):
            self._smtc.close()

    def set_prevent_sleep(self, enabled: bool):
        """Enable or disable the sleep blocker."""
        self._prevent_sleep_enabled = enabled
        if enabled:
            self._sleep_blocker.enable()
        else:
            self._sleep_blocker.disable()

    def set_audio_device(self, device_id: str | None):
        """Switch to a specific audio output device (None = system default)."""
        self._device_manager.set_user_device(device_id)

    def get_audio_device_id(self) -> str | None:
        """Return the currently active device ID."""
        return self._device_manager.get_current_device_id()

    def _on_device_changed(self, new_device_id: str):
        """Recreate QAudioOutput when the active device changes."""
        current_volume = self._audio_output.volume()
        self._audio_output = self._device_manager.create_audio_output(self)
        self._audio_output.setVolume(current_volume)
        self._player.setAudioOutput(self._audio_output)

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.state_changed.emit(state)
        if state == QMediaPlayer.PlayingState:
            self._smtc.set_playback_status("playing")
        elif state == QMediaPlayer.PausedState:
            self._smtc.set_playback_status("paused")
        elif state == QMediaPlayer.StoppedState:
            self._smtc.set_playback_status("stopped")

    def _on_position_changed(self, position: int):
        self.position_changed.emit(position)
        self._check_write_now_playing(position)

    def _on_duration_changed(self, duration: int):
        self.duration_changed.emit(duration)

    def _check_write_now_playing(self, position: int):
        """Write now_playing.json after 5s of stable playback (once per track)."""
        if position < 5000:
            return
        track = self._current_track
        if track is None:
            return
        if track.filepath == self._now_playing_written:
            return
        try:
            genres = (
                [g.strip() for g in track.genre.split(";") if g.strip()]
                if track.genre else []
            )
            data = {}
            if track.artist and track.artist != "Unknown Artist":
                data["artist"] = track.artist
            data["title"] = track.title
            if track.album and track.album != "Unknown Album":
                data["album"] = track.album
            data["duration"] = track.duration
            if genres:
                data["genres"] = genres
            data["timestamp"] = time.time()

            np_path = cfg.CACHE_DIR / "now_playing.json"
            with open(np_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._now_playing_written = track.filepath
        except Exception as e:
            print("player._check_write_now_playing: write now_playing.json failed")



    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        """Forward media status changes to UI."""
        self.media_status_changed.emit(status)

    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        """Emit a unified error string for UI handling."""
        self.error_occurred.emit(f"{error_string} (Code: {error})")

    def load_source(self, track: TrackInfo):
        """Load an audio file for playback."""
        self._current_track = track
        self._now_playing_written = None
        url = QUrl.fromLocalFile(track.filepath)
        self._player.setSource(url)
        self._smtc.update_track_info(track)

    def _stop_fade(self):
        if self._fade_anim:
            self._fade_anim.stop()
            self._fade_anim.deleteLater()
            self._fade_anim = None

    def _fade_animate(self, from_vol: float, to_vol: float,
                      duration_ms: int, on_finished=None):
        self._stop_fade()
        self._audio_output.setVolume(from_vol)
        self._fade_anim = QPropertyAnimation(self._audio_output, b"volume")
        self._fade_anim.setStartValue(from_vol)
        self._fade_anim.setEndValue(to_vol)
        self._fade_anim.setDuration(duration_ms)
        if on_finished:
            def _on_done():
                try:
                    on_finished()
                except RuntimeError:
                    pass
            self._fade_anim.finished.connect(_on_done)
        self._fade_anim.start()

    def play(self):
        """Start or resume playback."""
        if self._player.source().isEmpty():
            self.empty_play_requested.emit()
            return
        dur = AppSettings().fade_duration
        if dur > 0:
            self._audio_output.setVolume(0.0)
            self._player.play()
            self._smtc.set_playback_status("playing")
            self._fade_animate(0.0, self._fade_target_volume, dur * 1000)
        else:
            self._stop_fade()
            self._player.play()
            self._smtc.set_playback_status("playing")

    def pause(self):
        """Pause playback."""
        dur = AppSettings().fade_duration
        if dur > 0 and self._player.playbackState() == QMediaPlayer.PlayingState:
            self._fade_target_volume = self._audio_output.volume()
            self._smtc.set_playback_status("paused")
            self._fade_animate(self._fade_target_volume, 0.0, dur * 1000,
                               on_finished=self._player.pause)
        else:
            self._stop_fade()
            self._player.pause()
            self._smtc.set_playback_status("paused")

    def stop(self):
        """Stop playback."""
        self._stop_fade()
        self._player.stop()
        self._smtc.set_playback_status("stopped")

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def set_position(self, position: int):
        """Set playback position in milliseconds."""
        if self._player.source().isEmpty():
            return
        self._player.setPosition(position)

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)."""
        self._stop_fade()
        volume = max(0.0, min(1.0, volume))
        self._audio_output.setVolume(volume)
        self._fade_target_volume = volume
        self.volume_changed.emit(volume)

    def get_position(self) -> int:
        """Get current playback position in milliseconds."""
        return self._player.position()

    def get_duration(self) -> int:
        """Get total duration in milliseconds."""
        return self._player.duration()

    def get_volume(self) -> float:
        """Get current volume (0.0 to 1.0)."""
        return self._audio_output.volume()

    def get_state(self) -> QMediaPlayer.PlaybackState:
        """Get current playback state."""
        return self._player.playbackState()

    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._player.playbackState() == QMediaPlayer.PlayingState

    @property
    def player(self) -> QMediaPlayer:
        """Access the underlying QMediaPlayer instance."""
        return self._player

    @property
    def audio_output(self) -> QAudioOutput:
        """Access the underlying QAudioOutput instance."""
        return self._audio_output