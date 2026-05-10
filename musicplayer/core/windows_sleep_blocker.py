import ctypes
from enum import IntFlag

class ExecutionState(IntFlag):
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_AUDIO_PLAYBACK = 0x00000040  # Windows 10 1703+

class WindowsSleepBlocker:
    """Block Windows sleep while audio is actively outputting.

    Usage example:
        blocker = WindowsSleepBlocker()
        blocker.enable()   # prevents system sleep
        ...
        blocker.disable()  # restore normal behavior
    """

    def __init__(self):
        self._active = False
        # Detect if OS supports the audio flag (Windows 10+). Simple heuristic – assume True.
        self._supports_audio_flag = True

    def enable(self, allow_display_off: bool = True):
        """Enable sleep blocking.

        If ``allow_display_off`` is True the display may turn off, otherwise it stays on.
        """
        if self._active:
            return
        flags = ExecutionState.ES_CONTINUOUS | ExecutionState.ES_SYSTEM_REQUIRED
        if self._supports_audio_flag:
            flags |= ExecutionState.ES_AUDIO_PLAYBACK
        if not allow_display_off:
            flags |= ExecutionState.ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(int(flags))
        self._active = True

    def disable(self):
        """Disable previously set sleep blocking."""
        if not self._active:
            return
        # Reset to continuous without other flags.
        ctypes.windll.kernel32.SetThreadExecutionState(ExecutionState.ES_CONTINUOUS)
        self._active = False

    def __enter__(self):
        self.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable()
