"""
Media Keys Handler (Windows)

Handles global media key events (Play/Pause, Next, Previous) using
Windows RegisterHotKey API + QAbstractNativeEventFilter.

Works globally even when the window is minimized to tray.
"""

import sys
import ctypes
import threading
import time


def _install_media_keys_filter(hwnd, callback):
    """
    Register media keys as global hotkeys on the given HWND.

    The callback is called with one of:
        "play_pause", "next_track", "prev_track"

    Returns a handler object with .uninstall() method, or None on non-Windows.
    """
    if sys.platform != "win32":
        return None

    return _MediaKeyHandler(hwnd, callback)


def create_media_keys_handler(hwnd, player, on_next, on_previous):
    """
    Create a media keys handler with player control callbacks.

    Args:
        hwnd: Window handle
        player: AudioPlayer instance with toggle_play_pause() method
        on_next: Callback for next track
        on_previous: Callback for previous track

    Returns:
        Handler object with .uninstall() method
    """
    def on_media_key(action: str):
        if action == "play_pause":
            player.toggle_play_pause()
        elif action == "next_track":
            on_next()
        elif action == "prev_track":
            on_previous()

    return _install_media_keys_filter(hwnd, on_media_key)


# VK codes for media keys
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000

HK_PLAY_PAUSE = 0x7001
HK_NEXT = 0x7002
HK_PREV = 0x7003

_DEDUP_MS = 150

_VK_TO_ACTION = {
    HK_PLAY_PAUSE: "play_pause",
    HK_NEXT: "next_track",
    HK_PREV: "prev_track",
}


class _MediaKeyHandler:
    def __init__(self, hwnd, callback):
        self._hwnd = hwnd
        self._callback = callback
        self._app_filter = None
        self._last_t = 0.0
        self._last_action = None
        self._lock = threading.Lock()
        self._sources = []

        self._install_hotkeys()
        self._install_event_filter()

        print(f"[MediaKeys] Sources: {', '.join(self._sources) if self._sources else 'NONE'}")

    def _dedup(self, action: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if (now - self._last_t) * 1000 < _DEDUP_MS and self._last_action == action:
                return False
            self._last_t = now
            self._last_action = action
            return True

    def _dispatch(self, action: str):
        if self._dedup(action):
            print(f"[MediaKeys] {action}")
            self._callback(action)

    def _install_hotkeys(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        for vk, hk_id in [
            (VK_MEDIA_PLAY_PAUSE, HK_PLAY_PAUSE),
            (VK_MEDIA_NEXT_TRACK, HK_NEXT),
            (VK_MEDIA_PREV_TRACK, HK_PREV),
        ]:
            if user32.RegisterHotKey(self._hwnd, hk_id, MOD_NOREPEAT, vk):
                self._sources.append(f"HotKey(0x{vk:02X})")
            else:
                err = kernel32.GetLastError()
                if err == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                    self._sources.append(f"HotKey(0x{vk:02X}, taken)")
                else:
                    print(f"[MediaKeys] RegisterHotKey 0x{vk:02X} failed: {err}")

    def _install_event_filter(self):
        """Install Qt native event filter to catch WM_HOTKEY messages."""
        from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

        handler = self

        class HotkeyFilter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):
                if event_type != "windows_generic_MSG":
                    return False, 0
                try:
                    msg_ptr = int(message)
                    import struct
                    is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
                    if is_64:
                        data = ctypes.cast(msg_ptr, ctypes.POINTER(ctypes.c_ubyte * 32)).contents
                        msg_id = struct.unpack_from('<I', data, 8)[0]
                        wParam = struct.unpack_from('<Q', data, 16)[0]
                    else:
                        data = ctypes.cast(msg_ptr, ctypes.POINTER(ctypes.c_ubyte * 16)).contents
                        msg_id = struct.unpack_from('<I', data, 4)[0]
                        wParam = struct.unpack_from('<I', data, 8)[0]

                    if msg_id == WM_HOTKEY:
                        action = _VK_TO_ACTION.get(wParam)
                        if action:
                            handler._dispatch(action)
                            return True, 0
                except Exception:
                    pass
                return False, 0

        self._app_filter = HotkeyFilter()
        app = QCoreApplication.instance()
        if app:
            app.installNativeEventFilter(self._app_filter)
            self._sources.append("WM_HOTKEY filter")

    def uninstall(self):
        # Remove event filter
        if self._app_filter:
            from PySide6.QtCore import QCoreApplication
            app = QCoreApplication.instance()
            if app:
                app.removeNativeEventFilter(self._app_filter)
            self._app_filter = None

        # Unregister hotkeys
        if self._hwnd:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(self._hwnd, HK_PLAY_PAUSE)
            user32.UnregisterHotKey(self._hwnd, HK_NEXT)
            user32.UnregisterHotKey(self._hwnd, HK_PREV)
