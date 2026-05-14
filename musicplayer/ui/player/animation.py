"""
Blink animation for scanning status label.
"""

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property

def update_status_blink_color(phase: float, title_bar) -> str:
    """Calculate blink color and apply to title bar."""
    t = abs(0.5 - phase) * 2
    r = int(136 + (255 - 136) * t)
    g = int(136 + (255 - 136) * t)
    b = int(136 + (255 - 136) * t)
    color = f"#{r:02x}{g:02x}{b:02x}"
    title_bar.set_scanning_status_style(f"color: {color}; font-size: 11px;")
    return color


class BlinkAnimation:
    """Standalone blink animation — targets MainWindow's blink_phase property."""

    def __init__(self, main_window):
        self._main_window = main_window
        self._animation = None
        main_window._blink_phase = 0.0

    def start(self):
        if self._animation:
            self._animation.stop()
        self._animation = QPropertyAnimation(self._main_window, b"_blink_phase")
        self._animation.setDuration(4000)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.SineCurve)
        self._animation.valueChanged.connect(self._on_value_changed)
        self._animation.finished.connect(self._on_loop)
        self._animation.start()

    def stop(self):
        if self._animation:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None

    def _on_loop(self):
        if self._animation:
            self._animation.setCurrentTime(0)
            self._animation.start()

    def _on_value_changed(self, value):
        update_status_blink_color(value, self._main_window.title_bar)