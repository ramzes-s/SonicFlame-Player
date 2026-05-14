"""
Playback Controls Module

Bottom block containing all playback controls:
- Play/Pause, Next, Previous buttons
- Shuffle and Repeat toggles
- Seek bar (progress slider)
- Volume control
"""

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                                QSlider, QLabel, QFrame, QStyleOptionSlider, QStyle)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QByteArray, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvgWidgets import QSvgWidget
from musicplayer.ui.svg_icons import (
    get_play_svg, get_pause_svg, get_next_svg, get_previous_svg,
    get_shuffle_svg, get_repeat_svg,
    get_volume_high_svg, get_volume_mute_svg, get_heart_svg,
    get_similar_tracks_svg # NEW import
)


from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR, DIVIDER_COLOR


class IconButton(QPushButton):
    """Button with SVG icon."""

    def __init__(self, svg_getter, size=32, tooltip="", parent=None, circular_hover=False):
        super().__init__(parent)
        self.svg_getter = svg_getter
        self.icon_size = size
        self.tooltip = tooltip
        self._overlay_callback = None  # Optional callback to draw on top of icon
        self._circular_hover = circular_hover  # Use opacity hover effect

        # Animated opacity for smooth hover transition
        self._hover_opacity = 0.8  # Default 80% opacity
        self._opacity_anim = None
        if self._circular_hover:
            self._opacity_anim = QPropertyAnimation(self, b"hover_opacity")
            self._opacity_anim.setDuration(200)
            self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.setFixedSize(size + 6, size + 6)
        self.setCursor(Qt.PointingHandCursor)

        if self._circular_hover:
            # No stylesheet — hover handled via opacity in _update_icon
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    padding: 4px;
                }
            """)
        else:
            self.setStyleSheet(self._get_style())

        self._update_icon()

        if tooltip:
            self.setToolTip(tooltip)

    # --- animated property ---

    def _get_hover_opacity(self) -> float:
        return self._hover_opacity

    def _set_hover_opacity(self, value: float):
        self._hover_opacity = value
        self._update_icon()

    hover_opacity = Property(float, _get_hover_opacity, _set_hover_opacity)

    def enterEvent(self, event):
        if self._circular_hover and self._opacity_anim:
            self._opacity_anim.setStartValue(self._hover_opacity)
            self._opacity_anim.setEndValue(1.0)
            self._opacity_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._circular_hover and self._opacity_anim:
            self._opacity_anim.setStartValue(self._hover_opacity)
            self._opacity_anim.setEndValue(0.8)
            self._opacity_anim.start()
        super().leaveEvent(event)

    def set_overlay_callback(self, callback):
        """Set a callback (QPainter, QSize) -> None to draw on top of the icon."""
        self._overlay_callback = callback
        self._update_icon()
    
    def _get_style(self) -> str:
        """Button stylesheet."""
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 0.6);
            }
        """
    
    def _update_icon(self, color=None):
        """Update button icon from SVG string."""
        from PySide6.QtSvg import QSvgRenderer

        use_color = color if color else TEXT_COLOR
        svg_data = self.svg_getter(color=use_color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))

        size = self.icon_size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Opacity for circular hover buttons: animated via QPropertyAnimation
        if self._circular_hover:
            painter.setOpacity(self._hover_opacity)

        renderer.render(painter, QRect(0, 0, size, size))

        # Draw overlay if set
        if self._overlay_callback is not None:
            self._overlay_callback(painter, QSize(size, size))

        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(self.icon_size, self.icon_size))
    
    def set_active(self, active: bool):
        """Toggle active state with accent color."""
        if active:
            self._update_icon(cfg.get_accent_color())
        else:
            self._update_icon(TEXT_COLOR)


class ColorHoverButton(IconButton):
    """Button with smooth color transition on hover (no background)."""

    def __init__(self, svg_getter, size=32, tooltip="", parent=None):
        self._hover_anim = None
        self._color_phase = 0.0
        self._current_icon_color = TEXT_COLOR
        super().__init__(svg_getter, size, tooltip, parent, circular_hover=False)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: transparent;
            }
            QPushButton:pressed {
                background-color: transparent;
            }
        """)

    def _get_color_phase(self):
        return self._color_phase

    def _set_color_phase(self, value):
        self._color_phase = value
        self._update_icon_color()

    color_phase = Property(float, _get_color_phase, _set_color_phase)

    def _update_icon_color(self):
        accent = cfg.get_accent_color()
        r1, g1, b1 = int(TEXT_COLOR[1:3], 16), int(TEXT_COLOR[3:5], 16), int(TEXT_COLOR[5:7], 16)
        r2, g2, b2 = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        t = self._color_phase
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self._current_icon_color = color
        self._update_icon(color)

    def _update_icon(self, color=None):
        use_color = color if color else self._current_icon_color
        self._current_icon_color = use_color
        super()._update_icon(use_color)

    def enterEvent(self, event):
        if self._hover_anim:
            self._hover_anim.stop()
        self._hover_anim = QPropertyAnimation(self, b"color_phase")
        self._hover_anim.setDuration(200)
        self._hover_anim.setStartValue(self._color_phase)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hover_anim:
            self._hover_anim.stop()
        self._hover_anim = QPropertyAnimation(self, b"color_phase")
        self._hover_anim.setDuration(200)
        self._hover_anim.setStartValue(self._color_phase)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.start()
        super().leaveEvent(event)


class SeekSlider(QSlider):
    """Custom styled seek slider."""
    
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet(self._get_style())
        self.setRange(0, 0)
        self.setCursor(Qt.PointingHandCursor)
        self._is_user_interacting = False
    
    def mousePressEvent(self, event):
        """Handle click to seek."""
        if event.button() == Qt.LeftButton and self.maximum() > 0:
            # Calculate value from click position first
            self._set_value_from_click(event)
            self._is_user_interacting = True
            # Call parent to set pressed state and emit sliderPressed signal
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle drag to seek."""
        if event.buttons() == Qt.LeftButton and self._is_user_interacting:
            self._set_value_from_click(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle release."""
        was_interacting = self._is_user_interacting
        self._is_user_interacting = False
        
        # Always call parent to emit sliderReleased signal
        super().mouseReleaseEvent(event)
        
        # Our custom handling after parent
        if was_interacting:
            event.accept()
    
    def _set_value_from_click(self, event):
        """Calculate slider value from click position."""
        if self.maximum() <= 0:
            return
        
        # Get the groove geometry
        style = self.style()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        
        groove_rect = style.subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self
        )
        
        # Calculate position within groove
        if self.orientation() == Qt.Horizontal:
            click_x = event.position().x()
            groove_start = groove_rect.left()
            groove_end = groove_rect.right()
            groove_width = groove_end - groove_start
            
            if groove_width > 0:
                # Calculate ratio (0.0 to 1.0)
                ratio = max(0.0, min(1.0, (click_x - groove_start) / groove_width))
                value = int(ratio * (self.maximum() - self.minimum()) + self.minimum())
                self.setValue(value)
    
    def set_value_safe(self, value: int):
        """Set value only if user is not interacting (avoid feedback loop)."""
        if not self._is_user_interacting:
            self.setValue(value)
    
    def _get_style(self) -> str:
        """Slider stylesheet."""
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(80, 80, 80, 0.5);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0;
                background: {cfg.get_accent_color()};
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #FFFFFF;
            }}
            QSlider::sub-page:horizontal {{
                background: {cfg.get_accent_color()};
                border-radius: 2px;
            }}
        """


class VolumeSlider(QSlider):
    """Custom styled volume slider with click-to-seek support."""

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet(self._get_style())
        self.setRange(0, 100)
        self.setValue(50)
        self.setFixedWidth(120)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle click anywhere on groove to set value."""
        if event.button() == Qt.LeftButton and self.maximum() > 0:
            self._set_value_from_click(event)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def _set_value_from_click(self, event):
        """Calculate slider value from click position."""
        if self.maximum() <= 0:
            return
        style = self.style()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = style.subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self
        )
        if self.orientation() == Qt.Horizontal:
            click_x = event.position().x()
            groove_start = groove_rect.left()
            groove_end = groove_rect.right()
            groove_width = groove_end - groove_start
            if groove_width > 0:
                ratio = max(0.0, min(1.0, (click_x - groove_start) / groove_width))
                value = int(ratio * (self.maximum() - self.minimum()) + self.minimum())
                self.setValue(value)
    
    def _get_style(self) -> str:
        """Slider stylesheet."""
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(80, 80, 80, 0.5);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: {TEXT_COLOR};
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {cfg.get_accent_color()};
            }}
            QSlider::sub-page:horizontal {{
                background: {TEXT_COLOR};
                border-radius: 2px;
            }}
        """


class ControlsWidget(QWidget):
    """
    Playback controls widget.
    
    Contains:
    - Transport controls (Prev, Play/Pause, Next)
    - Shuffle and Repeat toggles
    - Seek bar with time labels
    - Volume control
    """
    
    play_pause_clicked = Signal()
    next_clicked = Signal()
    previous_clicked = Signal()
    shuffle_toggled = Signal(bool)
    repeat_toggled = Signal(str)  # "none", "all", "one"
    seek_requested = Signal(int)  # milliseconds
    volume_changed = Signal(float)  # 0.0 to 1.0
    seek_clicked = Signal(int)  # milliseconds - emitted on click/release
    favorite_toggled = Signal()  # toggle favorite for current track
    similar_tracks_requested = Signal() # NEW: Request to find similar tracks
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        
        # State tracking
        self.is_playing = False
        self.shuffle_enabled = False
        self.repeat_mode = "none"  # none, all, one
        self._is_muted = False
        self._previous_volume = 50
        self._current_filepath = None  # For favorite toggling
        self._current_is_favorite = False  # Current track favorite status
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 10)
        main_layout.setSpacing(8)
        
        # Top row: Seek bar and time labels
        seek_layout = QHBoxLayout()
        
        self.time_label_left = QLabel("0:00")
        self.time_label_left.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px; font-weight: bold;")
        self.time_label_left.setFixedWidth(60)
        
        self.seek_slider = SeekSlider()
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        
        self.time_label_right = QLabel("0:00")
        self.time_label_right.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px; font-weight: bold;")
        self.time_label_right.setFixedWidth(60)
        self.time_label_right.setAlignment(Qt.AlignRight)
        
        seek_layout.addWidget(self.time_label_left)
        seek_layout.addWidget(self.seek_slider)
        seek_layout.addWidget(self.time_label_right)
        
        main_layout.addLayout(seek_layout)
        
        # Bottom row: Controls — wrapped in a container to prevent stretching
        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        # Left margin
        controls_layout.addSpacing(80)

        # NEW: Similar Tracks Button (color hover effect on hover)
        self.similar_tracks_btn = ColorHoverButton(get_similar_tracks_svg, size=22, tooltip="Найти похожие треки")
        self.similar_tracks_btn.setEnabled(True) # Make it clickable now
        self.similar_tracks_btn.clicked.connect(self.similar_tracks_requested.emit) # Connect signal
        controls_layout.addWidget(self.similar_tracks_btn)

        controls_layout.addSpacing(48)

        # Previous
        self.prev_btn = IconButton(get_previous_svg, size=22, tooltip="Previous", circular_hover=True)
        self.prev_btn.clicked.connect(self.previous_clicked.emit)
        controls_layout.addWidget(self.prev_btn)

        controls_layout.addSpacing(10)

        # Play/Pause
        self.play_pause_btn = IconButton(get_play_svg, size=50, tooltip="Play")
        self.play_pause_btn.setFixedSize(58, 58)
        self.play_pause_btn.setStyleSheet(self._get_play_button_style())
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        controls_layout.addWidget(self.play_pause_btn)

        controls_layout.addSpacing(10)

        # Next
        self.next_btn = IconButton(get_next_svg, size=22, tooltip="Next", circular_hover=True)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        controls_layout.addWidget(self.next_btn)

        controls_layout.addSpacing(48)

        # Repeat
        self.repeat_btn = IconButton(get_repeat_svg, size=22, tooltip="Repeat")
        self.repeat_btn.clicked.connect(self._on_repeat_clicked)
        controls_layout.addWidget(self.repeat_btn)

        # Stretch fills remaining space between transport and volume
        #controls_layout.addStretch()
        controls_layout.addSpacing(380)

        # Right: Volume
        self.volume_icon_btn = ColorHoverButton(get_volume_high_svg, size=24, tooltip="Громкость")
        self.volume_icon_btn.clicked.connect(self._on_volume_icon_clicked)

        self.volume_slider = VolumeSlider()
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        controls_layout.addSpacing(15)
        controls_layout.addWidget(self.volume_icon_btn)

        controls_layout.addSpacing(20)
        controls_layout.addWidget(self.volume_slider)

        controls_layout.addSpacing(80)

        controls_layout.addStretch()
        # Heart icon for current track favorite
        self.heart_btn = IconButton(get_heart_svg, size=40, tooltip="В избранное")
        self.heart_btn.clicked.connect(self._on_favorite_clicked)
        self.heart_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        controls_layout.addWidget(self.heart_btn)
        controls_layout.addSpacing(10)

        main_layout.addWidget(controls_row, alignment=Qt.AlignLeft)
    
    def _on_play_pause_clicked(self):
        """Toggle play/pause state."""
        self.is_playing = not self.is_playing

        if self.is_playing:
            self.play_pause_btn.svg_getter = get_pause_svg
            self.play_pause_btn._update_icon()
        else:
            self.play_pause_btn.svg_getter = get_play_svg
            self.play_pause_btn._update_icon()

        self.play_pause_clicked.emit()
    
    def _on_repeat_clicked(self):
        """Cycle through repeat modes: none -> all -> one -> none."""
        if self.repeat_mode == "none":
            self.repeat_mode = "all"
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(None)
            self.repeat_btn._update_icon(cfg.get_accent_color())
        elif self.repeat_mode == "all":
            self.repeat_mode = "one"
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(self._draw_repeat_one_overlay)
            self.repeat_btn._update_icon(cfg.get_accent_color())
        else:
            self.repeat_mode = "none"
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(None)
            self.repeat_btn._update_icon(TEXT_COLOR)

        self.repeat_toggled.emit(self.repeat_mode)

    def _draw_repeat_one_overlay(self, painter, size):
        """Draw circle with '1' on top of repeat icon for repeat-one mode."""
        from PySide6.QtGui import QFont, QColor, QBrush

        # Circle background
        cx, cy = size.width() // 2, size.height() // 2
        radius = size.width() // 3

        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.setPen(QColor(cfg.get_accent_color()))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Number "1"
        font = QFont("Segoe UI", radius, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(cfg.get_accent_color()))
        painter.drawText(
            cx - radius, cy - radius, radius * 2, radius * 2,
            Qt.AlignCenter, "1"
        )
    
    def _on_seek_moved(self, value: int):
        """Seek slider moved (update labels only)."""
        self._update_time_labels(value, self.seek_slider.maximum())
    
    def _on_seek_pressed(self):
        """Seek slider pressed - update position visually."""
        self._update_time_labels(self.seek_slider.value(), self.seek_slider.maximum())

    def _on_seek_released(self):
        """Seek slider released - perform the seek."""
        value = self.seek_slider.value()
        self.seek_requested.emit(value)
        self.seek_clicked.emit(value)
    
    def _get_play_button_style(self) -> str:
        """Get circular stylesheet for play/pause button."""
        return """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 29px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 0.3);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 0.5);
        """
    
    def _on_volume_changed(self, value: int):
        """Volume slider changed."""
        volume = value / 100.0
        self.volume_changed.emit(volume)
        
        # Update volume icon
        if value == 0:
            self.volume_icon_btn._update_icon()
        else:
            self.volume_icon_btn._update_icon()
    
    def _on_volume_icon_clicked(self):
        """Toggle mute."""
        if self._is_muted:
            # Restore volume
            self.volume_slider.setValue(self._previous_volume)
            self._is_muted = False
        else:
            # Mute
            self._previous_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self._is_muted = True

    def _on_favorite_clicked(self):
        """Emit favorite toggle signal."""
        self.favorite_toggled.emit()

    def set_current_track_favorite(self, filepath: str, is_favorite: bool):
        """Update heart button state for current track."""
        self._current_filepath = filepath
        self._current_is_favorite = is_favorite
        if is_favorite:
            self.heart_btn._update_icon(cfg.get_accent_color())
            self.heart_btn.setToolTip("В избранном")
        else:
            self.heart_btn._update_icon(TEXT_COLOR)
            self.heart_btn.setToolTip("В избранное")
    
    def _update_time_labels(self, position: int, duration: int):
        """Update time display labels."""
        from musicplayer.utils.helpers import format_duration
        
        pos_sec = position / 1000.0
        dur_sec = duration / 1000.0
        
        self.time_label_left.setText(format_duration(pos_sec))
        self.time_label_right.setText(format_duration(dur_sec))
    
    def set_duration(self, duration_ms: int):
        """Set total track duration."""
        self.seek_slider.setRange(0, duration_ms)
        self._update_time_labels(self.seek_slider.value(), duration_ms)
    
    def set_position(self, position_ms: int):
        """Set current playback position."""
        # Use safe set to avoid overwriting user interaction
        self.seek_slider.set_value_safe(position_ms)
        self._update_time_labels(position_ms, self.seek_slider.maximum())
    
    def set_play_state(self, playing: bool):
        """Update play/pause button icon."""
        self.is_playing = playing

        if playing:
            self.play_pause_btn.svg_getter = get_pause_svg
            self.play_pause_btn._update_icon()
        else:
            self.play_pause_btn.svg_getter = get_play_svg
            self.play_pause_btn._update_icon()
    
    def set_shuffle_state(self, enabled: bool):
        """Update shuffle button state. This method is now a no-op as shuffle button is replaced."""
        pass
    
    def set_repeat_mode(self, mode: str):
        """Update repeat button state."""
        self.repeat_mode = mode

        if mode == "none":
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(None)
            self.repeat_btn._update_icon(TEXT_COLOR)
        elif mode == "all":
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(None)
            self.repeat_btn._update_icon(cfg.get_accent_color())
        elif mode == "one":
            self.repeat_btn.svg_getter = get_repeat_svg
            self.repeat_btn.set_overlay_callback(self._draw_repeat_one_overlay)
            self.repeat_btn._update_icon(cfg.get_accent_color())
    
    def set_volume(self, volume: float):
        """Set volume from external source (0.0 to 1.0)."""
        value = int(volume * 100)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)

        self._is_muted = (value == 0)

    def apply_accent_color(self, color: str):
        """Update accent color across all controls."""
        # Update seek slider style
        self.seek_slider.setStyleSheet(self.seek_slider._get_style())

        # Update volume slider style
        self.volume_slider.setStyleSheet(self.volume_slider._get_style())

        # Update similar tracks button (it's disabled, so just update icon if needed)
        self.similar_tracks_btn._update_icon(TEXT_COLOR) # Always default color as it's not active

        # Update repeat button
        if self.repeat_mode != "none":
            self.repeat_btn._update_icon(color)

        # Update heart button for current track
        if self._current_is_favorite:
            self.heart_btn._update_icon(color)

        # Force viewport update
        self.update()


