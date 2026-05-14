"""
Base classes for player managers.
"""

import ctypes

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication


class PlayerManagerBase:
    """Base class providing shared methods for player managers."""

    def _bring_to_front(self):
        """Bring window to front and give it focus."""
        hwnd = int(self._mw.windowHandle().winId())
        if not hwnd:
            return

        self._mw.showNormal()
        self._mw.setWindowState(self._mw.windowState() & ~Qt.WindowMinimized)
        self._mw.raise_()
        QApplication.processEvents()

        def do_bring():
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.AllowSetForegroundWindow(kernel32.GetCurrentProcessId())
                fgwnd = user32.GetForegroundWindow()
                if fgwnd:
                    fg_tid = user32.GetWindowThreadProcessId(fgwnd, None)
                    our_tid = user32.GetWindowThreadProcessId(hwnd, None)
                    user32.AttachThreadInput(our_tid, fg_tid, True)
                    user32.ShowWindow(hwnd, 9)
                    user32.BringWindowToTop(hwnd)
                    user32.AttachThreadInput(our_tid, fg_tid, False)
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        QTimer.singleShot(100, do_bring)
        QTimer.singleShot(300, do_bring)
        QTimer.singleShot(600, do_bring)

    def _reset_sidebar_state(self):
        """Reset sidebar favorites/top buttons to inactive state."""
        if self._mw.sidebar._favorites_active:
            self._mw.sidebar._favorites_active = False
            self._mw.sidebar.favorites_btn.set_active(False)
            self._mw.settings.favorites_mode = False
        if self._mw.sidebar._top_active:
            self._mw.sidebar._top_active = False
            self._mw.sidebar.top_btn.set_active(False)
            self._mw.settings.top_mode = False