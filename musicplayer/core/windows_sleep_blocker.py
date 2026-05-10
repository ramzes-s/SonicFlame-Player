import ctypes
from enum import IntFlag

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class ExecutionState(IntFlag):
    ES_CONTINUOUS = ES_CONTINUOUS
    ES_SYSTEM_REQUIRED = ES_SYSTEM_REQUIRED
    ES_DISPLAY_REQUIRED = ES_DISPLAY_REQUIRED


class WindowsSleepBlocker:
    """Block Windows sleep while audio is actively outputting."""

    def __init__(self):
        self._active = False

    def enable(self, allow_display_off: bool = True):
        """Enable sleep blocking."""
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        
        self._active = True
        return result

    def disable(self):
        """Disable previously set sleep blocking."""
        if not self._active:
            return
        # MUST call with the SAME flags as enable to clear them
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        self._active = False

    def __enter__(self):
        self.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable()
