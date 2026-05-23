from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices


class AudioDeviceManager(QObject):
    """Manages audio output device selection with automatic fallback to default."""

    device_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._requested_device_id: str | None = None
        self._current_device_id: str = self._resolve_id()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(1000)

    def set_user_device(self, device_id: str | None):
        """Set user-preferred device. None = follow system default."""
        self._requested_device_id = device_id
        self._apply()

    def get_user_device(self) -> str | None:
        return self._requested_device_id

    def get_current_device_id(self) -> str:
        return self._current_device_id

    def create_audio_output(self, parent=None) -> QAudioOutput:
        return QAudioOutput(self._resolve_device(), parent)

    @staticmethod
    def enumerate_devices():
        return [
            (dev.description(), str(dev.id().toStdString()))
            for dev in QMediaDevices.audioOutputs()
        ]

    def _resolve_device(self):
        if self._requested_device_id is not None:
            for dev in QMediaDevices.audioOutputs():
                if str(dev.id().toStdString()) == self._requested_device_id:
                    return dev
        return QMediaDevices.defaultAudioOutput()

    def _resolve_id(self) -> str:
        return str(self._resolve_device().id().toStdString())

    def _apply(self):
        new_id = self._resolve_id()
        if new_id != self._current_device_id:
            self._current_device_id = new_id
            self.device_changed.emit(new_id)

    def _poll(self):
        self._apply()
