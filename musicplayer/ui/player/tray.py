"""
System tray management (mini-widget stays in MainWindow).
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtGui import QIcon


def get_icon_path() -> Path:
    """Get path to app icon."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "Sonic-Flame.ico"
    return Path(__file__).parent.parent.parent.parent / "Sonic-Flame.ico"


class TrayManager:
    """Manages system tray icon and menu."""

    def __init__(self, main_window):
        self._mw = main_window
        self._tray_icon = None
        self._setup()

    def _setup(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray_icon = QSystemTrayIcon(self._mw)
        icon_path = get_icon_path()
        if icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))
        menu = QMenu()
        menu.addAction("Показать").triggered.connect(self._mw._restore_from_tray)
        menu.addAction("Выход").triggered.connect(self._mw.close)
        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(
            lambda r: r == QSystemTrayIcon.DoubleClick and self._mw._restore_from_tray()
        )
        self._tray_icon.setVisible(False)

    def show(self):
        if self._tray_icon:
            self._tray_icon.setVisible(True)

    def hide(self):
        if self._tray_icon:
            self._tray_icon.setVisible(False)

    @property
    def tray_icon(self):
        return self._tray_icon