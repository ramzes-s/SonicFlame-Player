"""
Mini Widget for System Tray

Compact always-on-top widget displayed in the bottom-right corner
when the main window is minimized to tray.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QByteArray, Signal, QRect, Property, QPropertyAnimation
from PySide6.QtGui import QFont, QPainter, QIcon, QColor, QPixmap
from PySide6.QtSvg import QSvgRenderer

from musicplayer import config as cfg
from musicplayer.ui.svg_icons import (
    get_play_svg, get_pause_svg, get_next_svg, get_previous_svg
)


def _get_icon_path() -> str:
    """Get path to icon file (works for both dev and PyInstaller)."""
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).parent / "Sonic-Flame.ico")
    return str(Path(__file__).parent.parent.parent / "Sonic-Flame.ico")


class MiniIconButton(QPushButton):
    """Button with SVG icon for mini widget."""

    def __init__(self, svg_getter, size=24, accent_color="#ed6a02", parent=None):
        super().__init__(parent)
        self.svg_getter = svg_getter
        self.icon_size = size
        self.accent_color = accent_color
        self.setFixedSize(size + 8, size + 8)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self._pressed = False
        self.setStyleSheet("QPushButton { background: transparent; border: none; padding: 4px; }")
        self._update_icon()

    def set_accent_color(self, color):
        """Update cached accent color and redraw if hovered."""
        self.accent_color = color
        if self._hovered:
            self._update_icon()

    def enterEvent(self, event):
        self._hovered = True
        self._pressed = False
        self._update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self._update_icon()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self._update_icon(color=self.accent_color)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self._update_icon()
        super().mouseReleaseEvent(event)

    def _update_icon(self, color=None):
        if color is None:
            if self._hovered:
                use_color = self.accent_color
            else:
                use_color = "#FFFFFF"
        else:
            use_color = color
        svg_data = self.svg_getter(color=use_color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        pixmap = QPixmap(self.icon_size, self.icon_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter, QRect(0, 0, self.icon_size, self.icon_size))
        painter.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QPixmap(pixmap.size()).size())


class MiniPlayerWidget(QWidget):
    """
    Compact mini-player widget for system tray mode.

    Displays: [Expand] [Artist - Title] [Prev] [Play/Pause] [Next]
    Always on top, positioned at bottom-right above system tray.
    """

    play_pause_clicked = Signal()
    next_clicked = Signal()
    previous_clicked = Signal()
    expand_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(480, 56)

        self._artist_text = "Unknown Artist"
        self._title_text = "No Track"
        self._is_playing = False
        self._accent_color = cfg.get_accent_color()
        self._idle_alpha = 153
        self._bg_alpha = self._idle_alpha

        self._build_ui()
        self._position_on_screen()
        self._setup_animations()

    def _setup_animations(self):
        """Setup fade in/out animations for background."""
        self.fade_in_anim = QPropertyAnimation(self, b"backgroundAlpha", self)
        self.fade_in_anim.setDuration(200)
        self.fade_in_anim.setEndValue(255)

        self.fade_out_anim = QPropertyAnimation(self, b"backgroundAlpha", self)
        self.fade_out_anim.setDuration(300)
        self.fade_out_anim.setEndValue(self._idle_alpha)

    @Property(int)
    def backgroundAlpha(self):
        return self._bg_alpha

    @backgroundAlpha.setter
    def backgroundAlpha(self, value):
        self._bg_alpha = value
        self.update()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # Expand button (left)
        self.expand_btn = MiniIconButton(self._get_expand_svg, size=24, accent_color=self._accent_color)
        self.expand_btn.setToolTip("Развернуть плеер")
        self.expand_btn.clicked.connect(self.expand_requested.emit)
        layout.addWidget(self.expand_btn, 0)

        # Track info (center, stretches) — two labels for artist and title
        info_container = QWidget()
        info_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 4, 0, 0)
        info_layout.setSpacing(0)

        self.artist_label = QLabel()
        self.artist_label.setStyleSheet(
            "color: #FFFFFF; font-size: 14px; font-weight: bold; background: transparent;"
        )
        self.artist_label.setCursor(Qt.OpenHandCursor)
        self.artist_label.installEventFilter(self)

        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            f"color: {cfg.get_accent_color()}; font-size: 13px; background: transparent;"
        )
        self.title_label.setCursor(Qt.OpenHandCursor)
        self.title_label.installEventFilter(self)

        info_layout.addWidget(self.artist_label)
        info_layout.addWidget(self.title_label)
        info_layout.addStretch()

        layout.addWidget(info_container, 1)

        # Playback controls (right)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)
        controls_layout.setContentsMargins(0, 2, 0, 0)

        self.prev_btn = MiniIconButton(get_previous_svg, size=22, accent_color=self._accent_color)
        self.prev_btn.setToolTip("Предыдущий")
        self.prev_btn.clicked.connect(self.previous_clicked.emit)
        controls_layout.addWidget(self.prev_btn)

        self.play_pause_btn = MiniIconButton(get_play_svg, size=28, accent_color=self._accent_color)
        self.play_pause_btn.setToolTip("Воспроизвести")
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        controls_layout.addWidget(self.play_pause_btn)

        self.next_btn = MiniIconButton(get_next_svg, size=22, accent_color=self._accent_color)
        self.next_btn.setToolTip("Следующий")
        self.next_btn.clicked.connect(self.next_clicked.emit)
        controls_layout.addWidget(self.next_btn)

        controls_container = QWidget()
        controls_container.setLayout(controls_layout)
        layout.addWidget(controls_container, 0)

    def _get_expand_svg(self, color="#FFFFFF"):
        """SVG for expand/restore icon."""
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <path fill="{color}" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
        </svg>"""

    def _position_on_screen(self):
        """Position widget at bottom-right above system tray."""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 1
        y = screen.bottom() - self.height() - 1
        self.move(x, y)

    def set_track_info(self, artist: str, title: str):
        """Update displayed track information and refresh accent color."""
        self._artist_text = (artist or "Unknown Artist").strip()
        self._title_text = (title or "No Track").strip()

        # Refresh accent color from config (in case settings changed)
        self._accent_color = cfg.get_accent_color()

        # Update labels: artist white, title accent
        self.artist_label.setStyleSheet(
            "color: #FFFFFF; font-size: 14px; font-weight: bold; background: transparent;"
        )
        self.title_label.setStyleSheet(
            f"color: {self._accent_color}; font-size: 13px; background: transparent;"
        )

        # Update all button accent colors
        for btn in (self.expand_btn, self.prev_btn, self.play_pause_btn, self.next_btn):
            btn.set_accent_color(self._accent_color)

        max_chars = 45
        artist_display = self._artist_text[:max_chars]
        title_display = self._title_text[:max_chars]

        self.artist_label.setText(artist_display)
        self.title_label.setText(title_display)

    def set_opacity(self, value: int):
        """Set background idle transparency (0 = opaque, 80 = max transparency)."""
        alpha = int(255 * (1 - max(0, min(80, int(value))) / 100.0))
        self._idle_alpha = alpha
        self._bg_alpha = alpha
        self.fade_out_anim.setEndValue(alpha)
        self.update()

    def set_play_state(self, playing: bool):
        """Update play/pause button icon."""
        self._is_playing = playing
        if playing:
            self.play_pause_btn.svg_getter = get_pause_svg
            self.play_pause_btn.setToolTip("Пауза")
        else:
            self.play_pause_btn.svg_getter = get_play_svg
            self.play_pause_btn.setToolTip("Воспроизвести")
        self.play_pause_btn._update_icon()

    def enterEvent(self, event):
        """Fade in background."""
        self.fade_out_anim.stop()
        self.fade_in_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Fade out background."""
        self.fade_in_anim.stop()
        self.fade_out_anim.start()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """Forward mouse drag events from info labels to self."""
        from PySide6.QtCore import QEvent
        if obj in (self.artist_label, self.title_label):
            if event.type() == QEvent.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            elif event.type() == QEvent.MouseMove:
                self.mouseMoveEvent(event)
                return True
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        """Draw black background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background with animated alpha
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._bg_alpha))

    def mousePressEvent(self, event):
        """Allow dragging the widget."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle dragging."""
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
