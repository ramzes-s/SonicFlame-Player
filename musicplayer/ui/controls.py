"""
Playback Controls Module

Bottom block containing all playback controls:
- Play/Pause, Next, Previous buttons
- Shuffle and Repeat toggles
- Seek bar (progress slider)
- Volume control
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from musicplayer.ui.svg_icons import (
    get_play_svg, get_pause_svg, get_next_svg, get_previous_svg,
    get_shuffle_svg, get_repeat_svg,
    get_volume_high_svg, get_volume_mute_svg, get_heart_svg,
    get_similar_tracks_svg, get_settings_svg
)
from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR
from musicplayer.ui.widgets.icon_button import IconButton, ColorHoverButton
from musicplayer.ui.widgets.sliders import SeekSlider, VolumeSlider


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
    similar_tracks_requested = Signal() # Request to find similar tracks
    settings_requested = Signal()  # Open settings dialog
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        
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

        main_layout.addLayout(self._build_seek_bar())
        main_layout.addWidget(self._build_controls_row(), alignment=Qt.AlignLeft)

    def _build_seek_bar(self):
        """Build seek bar with time labels."""
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

        return seek_layout

    def _build_controls_row(self):
        """Build controls row with transport, volume and action buttons."""
        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        # Settings button - open settings dialog
        self.settings_btn = ColorHoverButton(get_settings_svg, size=28, tooltip="Настройки")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        controls_layout.addWidget(self.settings_btn)

        controls_layout.addSpacing(60)

        # Similar Tracks Button (color hover effect on hover)
        self.similar_tracks_btn = ColorHoverButton(get_similar_tracks_svg, size=22, tooltip="Найти похожие треки")
        self.similar_tracks_btn.setEnabled(True)
        self.similar_tracks_btn.clicked.connect(self.similar_tracks_requested.emit)
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

        return controls_row
    
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
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 29px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {cfg.DIVIDER_ITEM_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {cfg.DIVIDER_COLOR};
            }}
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
    
    def set_action_buttons_enabled(self, enabled: bool):
        """Enable/disable similar-tracks button during loading."""
        self.similar_tracks_btn.setEnabled(enabled)

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


