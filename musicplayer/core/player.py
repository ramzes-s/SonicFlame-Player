"""
Audio Player Module

Wrapper around QMediaPlayer providing playback functionality
with signals for UI updates.
"""

from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from musicplayer.core.db import TrackInfo
from musicplayer.core import settings


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

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_track: TrackInfo | None = None
        self._current_device_id = None

        # Create audio output
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.5)
        
        # Windows sleep blocker – enabled based on settings
        from .windows_sleep_blocker import WindowsSleepBlocker
        self._sleep_blocker = WindowsSleepBlocker()
        self._prevent_sleep_enabled = settings.get_prevent_sleep()
        if self._prevent_sleep_enabled:
            self._sleep_blocker.enable()

        # Create media player
        self._player = QMediaPlayer()  
        self._player.setAudioOutput(self._audio_output)

        # Connect signals
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

        # Poll for audio device changes
        self._current_device_id = self._get_default_device_id()
        self._device_poll_timer = QTimer(self)
        self._device_poll_timer.timeout.connect(self._check_audio_device)
        self._device_poll_timer.start(1000)

    def set_prevent_sleep(self, enabled: bool):
        """Enable or disable the sleep blocker."""
        self._prevent_sleep_enabled = enabled
        if enabled:
            self._sleep_blocker.enable()
        else:
            self._sleep_blocker.disable()

    def _get_default_device_id(self) -> str:
        """Get unique identifier for current default audio output."""
        device = QMediaDevices.defaultAudioOutput()
        return str(device.id().toStdString())

    def _check_audio_device(self):
        """Poll for audio device changes."""
        new_id = self._get_default_device_id()
        if new_id != self._current_device_id:
            self._current_device_id = new_id
            device = QMediaDevices.defaultAudioOutput()
            current_volume = self._audio_output.volume()
            self._audio_output = QAudioOutput(device, self)
            self._audio_output.setVolume(current_volume)
            self._player.setAudioOutput(self._audio_output)
            # Re‑connect the stateChanged signal after recreating the output
    

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.state_changed.emit(state)

    def _on_position_changed(self, position: int):
        self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int):
        self.duration_changed.emit(duration)



    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        """Forward media status changes to UI."""
        self.media_status_changed.emit(status)

    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        """Emit a unified error string for UI handling."""
        self.error_occurred.emit(f"{error_string} (Code: {error})")

    def load_source(self, track: TrackInfo):
        """Load an audio file for playback."""
        self._current_track = track
        url = QUrl.fromLocalFile(track.filepath)
        self._player.setSource(url)

    def play(self):
        """Start or resume playback."""
        self._player.play()

    def pause(self):
        """Pause playback."""
        self._player.pause()

    def stop(self):
        """Stop playback."""
        self._player.stop()

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
        volume = max(0.0, min(1.0, volume))
        self._audio_output.setVolume(volume)
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