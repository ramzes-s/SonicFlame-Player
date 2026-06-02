"""
Side Bar Module

Left vertical sidebar with action buttons:
- Open Folder
- Favorites (Heart)
- Settings (Gear)

Icons are semi-transparent by default and smoothly become
fully opaque on hover via QPropertyAnimation.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, Property, QByteArray, QRect
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from musicplayer.ui.svg_icons import (
    get_folder_svg,
    get_heart_svg,
    get_settings_svg,
    get_library_svg,
    get_top_svg,
)


from musicplayer import config as cfg
from musicplayer.config import TEXT_COLOR, DIVIDER_COLOR

SIDEBAR_WIDTH = 42

# Opacity levels
OPACITY_DEFAULT = 140   # ~55 % opaque
OPACITY_HOVER = 255     # fully opaque
ANIM_DURATION = 200     # ms


class SidebarButton(QPushButton):
    """
    Icon button for sidebar with smooth opacity animation on hover.

    The icon is rendered with a semi-transparent colour by default.
    On hover the alpha smoothly animates to full opacity.
    """

    def __init__(self, svg_getter, tooltip="", parent=None):
        super().__init__(parent)
        self.svg_getter = svg_getter
        self.icon_size = 22
        self.setFixedSize(SIDEBAR_WIDTH, SIDEBAR_WIDTH)
        self.setCursor(Qt.PointingHandCursor)

        # No background stylesheet — icon opacity is the only visual cue
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 6px;
            }
        """)

        # Current alpha value (animated property)
        self._icon_alpha = OPACITY_DEFAULT
        self._force_color = None  # If set, override default on leave

        # Build initial pixmap
        self._update_icon()

        if tooltip:
            self.setToolTip(tooltip)

        # Animation
        self._anim = QPropertyAnimation(self, b"icon_alpha")
        self._anim.setDuration(ANIM_DURATION)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    # ---- animated property ----

    def _get_icon_alpha(self) -> int:
        return self._icon_alpha

    def _set_icon_alpha(self, value: int):
        self._icon_alpha = int(value)
        self._update_icon()

    icon_alpha = Property(int, _get_icon_alpha, _set_icon_alpha)

    # ---- public API ----

    def enterEvent(self, event):
        self._anim.setStartValue(self._icon_alpha)
        self._anim.setEndValue(OPACITY_HOVER)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.setStartValue(self._icon_alpha)
        if self._force_color is not None:
            # Keep forced color (e.g. accent for active favorites)
            self._anim.setEndValue(OPACITY_HOVER)
        else:
            self._anim.setEndValue(OPACITY_DEFAULT)
        self._anim.start()
        super().leaveEvent(event)

    # ---- internal ----

    def _update_icon(self, base_color=None):
        """Re-render the SVG with the current alpha using QPainter opacity."""
        if base_color is not None:
            color = base_color
        elif self._force_color is not None:
            color = self._force_color
        else:
            color = TEXT_COLOR

        svg_data = self.svg_getter(color=color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

        size = self.icon_size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(self._icon_alpha / 255.0)
        renderer.render(painter, QRect(0, 0, size, size))
        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(self.icon_size, self.icon_size))

    def set_active(self, active: bool):
        """Toggle active state with accent color."""
        if active:
            self._force_color = cfg.get_accent_color()
            self._icon_alpha = OPACITY_HOVER
        else:
            self._force_color = None
            self._icon_alpha = OPACITY_DEFAULT
        self._update_icon()


class SideBarWidget(QWidget):
    """
    Left vertical sidebar with action buttons.

    Buttons:
    - Open Folder (folder icon)
    - Favorites (heart icon) — toggle state
    - Top (star icon) — toggle state
    - Library (books icon)
    - Settings (gear icon)
    """

    folder_open_requested = Signal()
    favorites_toggled = Signal(bool)  # emitted with active state
    top_requested = Signal(bool)  # emitted with active state
    playlist_type_changed = Signal(str)  # emits: "Folder", "Favorites", "Top", "Playlist"
    settings_requested = Signal()
    library_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")

        self._favorites_active = False
        self._top_active = False
        self._music_folder_configured = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        # --- top ---
        self.folder_btn = SidebarButton(get_folder_svg, tooltip="Открыть папку")
        self.folder_btn.clicked.connect(self.folder_open_requested.emit)
        layout.addWidget(self.folder_btn, alignment=Qt.AlignTop)

        layout.addSpacing(8)

        # Divider
        divider1 = QFrame()
        divider1.setFixedHeight(1)
        divider1.setStyleSheet(f"background-color: {DIVIDER_COLOR};")
        layout.addWidget(divider1)

        # Spacer — pushes bottom group down
        layout.addStretch()

        # Divider
        divider2 = QFrame()
        divider2.setFixedHeight(1)
        divider2.setStyleSheet(f"background-color: {DIVIDER_COLOR};")
        layout.addWidget(divider2)

        # --- bottom ---
        self.favorites_btn = SidebarButton(get_heart_svg, tooltip="Избранное")
        self.favorites_btn.clicked.connect(self._on_favorites_clicked)
        layout.addWidget(self.favorites_btn, alignment=Qt.AlignBottom)

        layout.addSpacing(4)

        self.top_btn = SidebarButton(get_top_svg, tooltip="Топ")
        self.top_btn.clicked.connect(self._on_top_clicked)
        layout.addWidget(self.top_btn, alignment=Qt.AlignBottom)

        layout.addSpacing(4)

        self.library_btn = SidebarButton(get_library_svg, tooltip="Библиотека")
        self.library_btn.clicked.connect(self.library_requested.emit)
        layout.addWidget(self.library_btn, alignment=Qt.AlignBottom)

        layout.addSpacing(4)

        self.settings_btn = SidebarButton(get_settings_svg, tooltip="Настройки")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn, alignment=Qt.AlignBottom)

    def _on_favorites_clicked(self):
        """Toggle favorites mode."""
        self._favorites_active = not self._favorites_active
        self.favorites_btn.set_active(self._favorites_active)
        self.favorites_toggled.emit(self._favorites_active)
        if self._favorites_active:
            self.playlist_type_changed.emit("Favorites")

    def _on_top_clicked(self):
        """Toggle top mode."""
        self._top_active = not self._top_active
        self.top_btn.set_active(self._top_active)
        self.top_requested.emit(self._top_active)
        if self._top_active:
            self.playlist_type_changed.emit("Top")

    def set_music_folder_configured(self, configured: bool):
        """Enable folder button only when music_folder is set in config."""
        self._music_folder_configured = configured
        self.folder_btn.setEnabled(configured)
        if not configured:
            self.folder_btn._icon_alpha = 40
            self.folder_btn._update_icon()
        else:
            self.folder_btn._icon_alpha = OPACITY_DEFAULT
            self.folder_btn._update_icon()

    def set_folder_enabled(self, enabled: bool):
        """Enable or disable the folder button (used during scanning)."""
        self.folder_btn.setEnabled(enabled and self._music_folder_configured)
        if not enabled:
            self.folder_btn._icon_alpha = 40
            self.folder_btn._update_icon()
        else:
            self.folder_btn._icon_alpha = OPACITY_DEFAULT
            self.folder_btn._update_icon()

    def set_all_buttons_enabled(self, enabled: bool, include_folder: bool = True):
        """Enable or disable all sidebar buttons with visual feedback."""
        if include_folder:
            self.folder_btn.setEnabled(enabled and self._music_folder_configured)
        self.favorites_btn.setEnabled(enabled)
        self.top_btn.setEnabled(enabled)

        # Visual feedback: adjust opacity on disabled buttons
        alpha = 40 if not enabled else OPACITY_DEFAULT
        self.favorites_btn._icon_alpha = alpha
        self.favorites_btn._update_icon()
        self.top_btn._icon_alpha = alpha
        self.top_btn._update_icon()
        if include_folder:
            self.folder_btn._icon_alpha = alpha
            self.folder_btn._update_icon()

    def apply_accent_color(self, color: str):
        """Update accent color for active buttons."""
        # Re-render active buttons with new accent color
        if self._favorites_active:
            self.favorites_btn._force_color = color
            self.favorites_btn._update_icon()
        if self._top_active:
            self.top_btn._force_color = color
            self.top_btn._update_icon()


