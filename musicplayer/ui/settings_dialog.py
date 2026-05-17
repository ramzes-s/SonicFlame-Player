"""
Settings Dialog

Dialog for application settings:
- Accent color selection
- Root music folder path
- Cache statistics (cover weight, library track count)
"""

import os
import socket
import qrcode
from pathlib import Path
from io import BytesIO

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QFileDialog, QWidget, QCheckBox,
                                QLineEdit, QSlider, QStyleOptionSlider, QComboBox)
from PySide6.QtWidgets import QStyle
from PySide6.QtCore import Qt, Signal, QByteArray, QTimer, QThread
from PySide6.QtGui import QFont, QPainter, QPen, QIcon, QPixmap, QColor, QPaintEvent, QIntValidator, QValidator
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtSvg import QSvgRenderer

from musicplayer import config as cfg
from musicplayer.core.db import get_filtered_library_track_count, get_covers_cache_size, get_analyzed_track_count
from musicplayer.core.db_cleaner import cleanup_missing_tracks
from musicplayer.ui.svg_icons import get_music_note_svg


class CleanupWorker(QThread):
    """Background worker for database cleanup."""
    finished = Signal(int)

    def run(self):
        removed = cleanup_missing_tracks()
        self.finished.emit(removed)

# --- Stat helpers ---

def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"


def _get_library_track_count() -> int:
    """Total number of tracks in the library DB."""
    try:
        return get_filtered_library_track_count()
    except Exception:
        return 0


# --- Preset accent colors ---
ACCENT_PRESETS = [
    ("#ed6a02", "Orange"),      # default
    ("#ff4444", "Red"),
    ("#e91e63", "Pink"),
    ("#9c27b0", "Purple"),
    ("#673ab7", "Deep Purple"),
    ("#3f51b5", "Indigo"),
    ("#2196f3", "Blue"),
    ("#00bcd4", "Cyan"),
    ("#009688", "Teal"),
    ("#4caf50", "Green"),
    ("#8bc34a", "Light Green"),
    ("#ffc150", "Yellow"),
    ("#977c64", "Brown"),
    ("#84a2be", "Gray"),
    ("#607884", "Slate"),
]


class ColorCircleButton(QPushButton):
    """Small circle button representing an accent color."""

    def __init__(self, color_hex: str, size: int = 22, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(size + 6, size + 6)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0;
            }
        """)
        self._pixmap = self._make_pixmap(color_hex, size)
        self.setIcon(QIcon(self._pixmap))
        self.setIconSize(QPixmap(self._pixmap.size()).size())

    def _make_pixmap(self, color_hex: str, size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_hex))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return pixmap

    def set_selected(self, selected: bool):
        if selected:
            # Draw ring
            ring = QPixmap(self.width(), self.height())
            ring.fill(Qt.transparent)
            p = QPainter(ring)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor("#FFFFFF"))
            p.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
            p.end()
            combined = QPixmap(self._pixmap)
            cp = QPainter(combined)
            cp.drawPixmap(0, 0, ring)
            cp.end()
            self.setIcon(QIcon(combined))
        else:
            self.setIcon(QIcon(self._pixmap))


FORBIDDEN_PORTS = {21, 22, 80, 443}


class PortValidator(QValidator):
    """Validates port numbers: 1024-65535, excluding 21, 22, 80, 443."""

    def validate(self, input_str: str, pos: int):
        if not input_str:
            return QValidator.Intermediate, input_str, pos
        if not input_str.isdigit():
            return QValidator.Invalid, input_str, pos
        port = int(input_str)
        if port > 65535:
            return QValidator.Invalid, input_str, pos
        if port < 1024:
            return QValidator.Intermediate, input_str, pos
        if port in FORBIDDEN_PORTS:
            return QValidator.Intermediate, input_str, pos
        return QValidator.Acceptable, input_str, pos

    def fixup(self, input_str: str) -> str:
        return "8080"


class ClickableSlider(QSlider):
    """QSlider with click-to-seek support."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            style = self.style()
            handle_rect = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            click_pos = event.position().toPoint()
            if not handle_rect.contains(click_pos):
                groove_rect = style.subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
                slider_range = self.maximum() - self.minimum()
                groove_width = groove_rect.width()
                if groove_width > 0:
                    x_in_groove = click_pos.x() - groove_rect.x()
                    ratio = x_in_groove / groove_width
                    new_val = self.minimum() + round(ratio * slider_range)
                    self.setValue(new_val)
                event.accept()
                return
        super().mousePressEvent(event)


class SpinnerWidget(QWidget):
    """Animated spinning circle loader."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(16, 16)
        self.hide()

    def start(self):
        self._angle = 0
        self.show()
        if not self._timer.isActive():
            self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self.hide()

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(cfg.get_accent_color()), 2.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        r = self.rect().adjusted(2, 2, -2, -2)
        painter.drawArc(r, self._angle * 16, 270 * 16)


class SettingsDialog(QDialog):
    """Frameless dialog for application settings."""

    accent_color_changed = Signal(str)
    dynamic_color_toggled = Signal(bool)
    web_server_toggled = Signal(bool)
    web_server_port_changed = Signal(int)
    music_folder_changed = Signal(bool)
    prevent_sleep_toggled = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._pending_port = None
        self._port_debounce_timer = QTimer(self)
        self._port_debounce_timer.setSingleShot(True)
        self._port_debounce_timer.timeout.connect(self._on_port_debounce_complete)
        self._spinner = SpinnerWidget(self)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(620, 420)
        self.setModal(True)

        self._build_ui()
        self._update_stats()

    def paintEvent(self, event: QPaintEvent):
        """Draw semi-transparent accent border around the dialog."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)
        color.setAlpha(26)  # ~10% opacity

        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(rect)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # --- Container for content ---
        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background-color: #000000;
            }
        """)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        svg_data = get_music_note_svg(60).encode('utf-8')
        title_icon.renderer().load(QByteArray(svg_data))
        title_layout.addWidget(title_icon)

        title_label = QLabel("Настройки")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        from musicplayer import config as app_cfg
        version_label = QLabel(f"code by ramzes    v{app_cfg.APP_VERSION}")
        version_label.setStyleSheet(f"color: {cfg.get_accent_color()}; font-size: 14px;")

        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        title_layout.addWidget(close_btn)

        version_label.setContentsMargins(0, 0, 8, 0)
        title_layout.addWidget(version_label)

        self._close_btn = close_btn
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        title_layout.addWidget(close_btn)
        self._close_btn = close_btn

        inner.addWidget(title_bar)

        # --- Scrollable content ---
        from PySide6.QtWidgets import QScrollArea, QFrame
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 20)
        content_layout.setSpacing(0)

        # Accent color
        accent_label = QLabel("Акцентный цвет")
        accent_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        content_layout.addWidget(accent_label)
        content_layout.addSpacing(8)

        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_buttons = {}
        for color_hex, _name in ACCENT_PRESETS:
            btn = ColorCircleButton(color_hex, size=22)
            btn.clicked.connect(lambda checked=False, c=color_hex: self._set_accent_color(c))
            btn.setToolTip(color_hex)
            self._color_buttons[color_hex] = btn
            color_row.addWidget(btn)
        color_row.addStretch()
        content_layout.addLayout(color_row)
        content_layout.addSpacing(16)

        # Music folder button
        self.folder_btn = QPushButton()
        self.folder_btn.setFixedHeight(36)
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(self._browse_folder)
        self._update_folder_button_text()
        content_layout.addWidget(self.folder_btn)
        content_layout.addSpacing(16)

        # Split into two columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)

        # Left column - settings (400px)
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Mini widget checkbox
        self.mini_widget_cb = QCheckBox("Включать виджет при сворачивании")
        self.mini_widget_cb.setChecked(self.settings.mini_widget_on_minimize)
        self.mini_widget_cb.toggled.connect(self._on_mini_widget_toggled)
        left_col.addWidget(self.mini_widget_cb)

        # Mini widget opacity combo
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(10)
        self._opacity_combo = QComboBox()
        opacity_label = QLabel("Прозрачность мини-виджета")
        opacity_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        self._opacity_combo.addItems([str(i) for i in range(0, 81, 10)])
        self._opacity_combo.setCurrentText(str(self.settings.mini_widget_opacity))
        self._opacity_combo.currentTextChanged.connect(self._on_opacity_changed)
        self._opacity_combo.setEnabled(self.settings.mini_widget_on_minimize)
        self._opacity_combo.setFixedWidth(70)
        self._opacity_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #000000;
                border: none;
                border-bottom: 1px solid {cfg.get_accent_color()};
                color: #FFFFFF;
                font-size: 12px;
                padding: 3px 6px 2px 6px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #000000;
                border: 1px solid {cfg.get_accent_color()};
                color: #FFFFFF;
                selection-background-color: {cfg.get_accent_color()};
            }}
        """)
        opacity_row.addWidget(self._opacity_combo)
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch()
        left_col.addLayout(opacity_row)

        # Prevent sleep checkbox
        self.prevent_sleep_cb = QCheckBox("Блокировать сон при работающем плеере")
        self.prevent_sleep_cb.setChecked(self.settings.prevent_sleep)
        self.prevent_sleep_cb.toggled.connect(self._on_prevent_sleep_toggled)
        left_col.addWidget(self.prevent_sleep_cb)

        # Dynamic color checkbox
        self.dynamic_color_cb = QCheckBox("Динамический цвет (из обложки)")
        self.dynamic_color_cb.setChecked(self.settings.dynamic_color)
        self.dynamic_color_cb.toggled.connect(self._on_dynamic_color_toggled)
        left_col.addWidget(self.dynamic_color_cb)

        # Web server checkbox
        self.web_server_cb = QCheckBox("Веб-сервер (удалённое управление)")
        self.web_server_cb.setChecked(self.settings.web_server_enabled)
        self.web_server_cb.toggled.connect(self._on_web_server_toggled)
        left_col.addWidget(self.web_server_cb)

        # Web server port
        port_layout = QHBoxLayout()
        port_layout.setSpacing(10)
        port_label = QLabel("Порт:")
        port_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        self.port_input = QLineEdit()
        initial_port = self.settings.web_server_port
        if initial_port in FORBIDDEN_PORTS or not (1024 <= initial_port <= 65535):
            initial_port = 8080
            self.settings.web_server_port = 8080
        self.port_input.setText(str(initial_port))
        self.port_input.setFixedWidth(80)
        self.port_input.setAlignment(Qt.AlignCenter)
        self.port_input.setEnabled(self.settings.web_server_enabled)
        self.port_input.setValidator(PortValidator())
        self.port_input.textChanged.connect(self._on_port_changed)
        self.port_input.setStyleSheet(self._port_style("#FFFFFF"))
        port_layout.addWidget(self.port_input)
        port_layout.addWidget(port_label)
        port_layout.addWidget(self._spinner)
        self._web_server_status = QLabel()
        self._web_server_status.setStyleSheet("color: #888888; font-size: 11px;")
        port_layout.addWidget(self._web_server_status)
        port_layout.addStretch()
        left_col.addLayout(port_layout)
        left_col.addSpacing(8)

        # Right column - QR + similarity slider
        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignTop)
        right_col.setSpacing(12)

        def _right_row():
            """Create a horizontal layout that pushes its content to the right edge."""
            row = QHBoxLayout()
            row.addStretch()
            return row

        qr_row = _right_row()
        self._qr_label = QLabel()
        self._qr_label.setFixedSize(100, 100)
        self._qr_label.setVisible(False)
        qr_row.addWidget(self._qr_label)
        right_col.addLayout(qr_row)
        right_col.addSpacing(20)

        # Similarity precision slider
        sim_label_row = _right_row()
        sim_label = QLabel("Точность подбора похожих треков")
        sim_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        sim_label_row.addWidget(sim_label)
        right_col.addLayout(sim_label_row)

        sim_slider_row = _right_row()
        sim_slider_row.setSpacing(10)
        self._sim_slider = ClickableSlider(Qt.Horizontal)
        self._sim_slider.setRange(0, 20)
        self._sim_slider.setValue(self.settings.similarity_precision)
        self._sim_slider.setFixedWidth(210)
        self._sim_slider.setCursor(Qt.PointingHandCursor)
        self._sim_slider.valueChanged.connect(self._on_similarity_precision_changed)
        self._sim_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(80, 80, 80, 0.5);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px;
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
        """)
        sim_slider_row.addWidget(self._sim_slider)
        right_col.addLayout(sim_slider_row)

        left_col.addStretch()

        columns_layout.addLayout(left_col)
        columns_layout.addLayout(right_col)
        content_layout.addLayout(columns_layout)

        content_layout.addStretch()

        # Apply styles after both checkboxes are created
        self._update_checkbox_style()
        self._update_combo_style()

        scroll.setWidget(content)
        inner.addWidget(scroll)

        # --- Status bar ---
        status_bar = QWidget()
        status_bar.setFixedHeight(32)
        status_bar.setStyleSheet("background-color: #0a0a0a;")

        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 0, 16, 0)

        accent = cfg.get_accent_color()
        self.library_count_label = QLabel()
        self.library_count_label.setStyleSheet(f"color: {accent}; font-size: 13px;")
        status_layout.addWidget(self.library_count_label)

        status_layout.addStretch()

        self.covers_size_label = QLabel()
        self.covers_size_label.setStyleSheet(f"color: {accent}; font-size: 13px;")
        status_layout.addWidget(self.covers_size_label)

        status_layout.addStretch()

        self._cleanup_btn = QPushButton("Чистка мусора")
        self._cleanup_btn.setFixedHeight(24)
        self._cleanup_btn.setCursor(Qt.PointingHandCursor)
        self._cleanup_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 11px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {accent};
            }}
            QPushButton:disabled {{
                color: #666666;
            }}
        """)
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        status_layout.addWidget(self._cleanup_btn)

        self._cleanup_result_label = QLabel()
        self._cleanup_result_label.setStyleSheet(f"color: {accent}; font-size: 12px;")
        self._cleanup_result_label.setVisible(False)
        status_layout.addWidget(self._cleanup_result_label)

        status_layout.addSpacing(10)

        inner.addWidget(status_bar)

        layout.addWidget(container)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_web_server_status()

    def _divider(self):
        d = QWidget()
        d.setFixedHeight(1)
        d.setStyleSheet("background-color: rgba(80, 80, 80, 0.5);")
        return d

    def _set_accent_color(self, color_hex: str):
        """Update global accent color and highlight selected button."""
        # Save to settings
        self.settings._data["accent_color"] = color_hex
        self.settings._save()

        # Update config module
        import musicplayer.config
        musicplayer.config.ACCENT_COLOR = color_hex

        # Update button highlights
        for hex_key, btn in self._color_buttons.items():
            btn.set_selected(hex_key == color_hex)

        # Emit signal for real-time UI update
        self.accent_color_changed.emit(color_hex)

    def _update_stats(self):
        """Update cache and library statistics."""
        covers_size = get_covers_cache_size()
        self.covers_size_label.setText(f"Кеш обложек:  {_format_size(covers_size)}")

        track_count = _get_library_track_count()
        analyzed_count = get_analyzed_track_count()
        self.library_count_label.setText(f"Треков:  {track_count} ({analyzed_count})")

        # Highlight current accent color
        current = self.settings._data.get("accent_color", ACCENT_PRESETS[0][0])
        for hex_key, btn in self._color_buttons.items():
            btn.set_selected(hex_key == current)

    def _update_folder_button_style(self, has_folder: bool):
        """Update folder button border - red if not set, accent if set."""
        accent = cfg.get_accent_color()
        if has_folder:
            border_color = "rgba(80, 80, 80, 0.5)"
        else:
            border_color = "#FF4444"
        self.folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {border_color};
                color: {accent};
                font-size: 13px;
                text-align: left;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(80, 80, 80, 0.3);
            }}
            QPushButton:pressed {{
                background-color: rgba(60, 60, 60, 0.4);
            }}
        """)

    def _update_folder_button_text(self):
        """Update folder button text based on current selection."""
        folder = self.settings.music_folder
        if folder and os.path.isdir(folder):
            self.folder_btn.setText(folder)
            self._update_folder_button_style(True)
        else:
            self.folder_btn.setText("Укажите корневую папку с музыкой")
            self._update_folder_button_style(False)

    def _browse_folder(self):
        """Open folder dialog and save selection."""
        current = self.settings.music_folder or ""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите корневую папку с музыкой",
            current,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.settings.music_folder = folder
            self._update_folder_button_text()
            self.music_folder_changed.emit(True)

    def _on_mini_widget_toggled(self, checked: bool):
        """Save mini widget on minimize setting."""
        self.settings.mini_widget_on_minimize = checked
        self._opacity_combo.setEnabled(checked)

    def _on_opacity_changed(self, text: str):
        """Save mini widget opacity setting."""
        try:
            self.settings.mini_widget_opacity = int(text)
        except ValueError:
            pass

    def _on_prevent_sleep_toggled(self, checked: bool):
        """Save prevent sleep setting."""
        self.settings.prevent_sleep = checked
        self.prevent_sleep_toggled.emit(checked)

    def _on_dynamic_color_toggled(self, checked: bool):
        """Save dynamic color setting and emit signal."""
        self.settings.dynamic_color = checked
        self.dynamic_color_toggled.emit(checked)

    def _on_web_server_toggled(self, checked: bool):
        """Save web server setting and emit signal."""
        self.settings.web_server_enabled = checked
        self.port_input.setEnabled(checked)
        self._update_web_server_status()
        self.web_server_toggled.emit(checked)

    def _port_style(self, text_color: str) -> str:
        return f"""
            QLineEdit {{
                background-color: #000000;
                border: none;
                border-bottom: 1px solid {cfg.get_accent_color()};
                color: {text_color};
                font-size: 12px;
                padding: 3px 4px 2px 4px;
            }}
            QLineEdit:disabled {{
                background-color: #000000;
                color: #555555;
                border-bottom: 1px solid #333333;
            }}
        """

    def _on_port_changed(self, text: str):
        """Debounce port changes — restart server only after 2s of inactivity."""
        if not text:
            self._spinner.stop()
            self._port_debounce_timer.stop()
            self._pending_port = None
            return

        try:
            port = int(text)
        except ValueError:
            self._spinner.stop()
            self._port_debounce_timer.stop()
            self._pending_port = None
            return

        self._pending_port = port

        if port in FORBIDDEN_PORTS or not (1024 <= port <= 65535):
            self.port_input.setStyleSheet(self._port_style("#ff4444"))
        else:
            self.port_input.setStyleSheet(self._port_style("#FFFFFF"))

        self._spinner.start()
        self._port_debounce_timer.start(2000)

    def _on_port_debounce_complete(self):
        """Fire when 2s of inactivity + valid port — save & restart server."""
        port = self._pending_port
        if port is None:
            self._spinner.stop()
            return

        if port in FORBIDDEN_PORTS or not (1024 <= port <= 65535):
            return

        self.settings.web_server_port = port
        self._spinner.stop()
        self.web_server_port_changed.emit(port)
        self._update_web_server_status()

    def _on_similarity_precision_changed(self, value: int):
        """Save similarity precision setting."""
        self.settings.similarity_precision = value

    def _get_local_ip(self):
        """Get local IP address."""
        try:
            host = socket.gethostname()
            ip_list = socket.getaddrinfo(host, None, socket.AF_INET)
            for info in ip_list:
                ip = info[4][0]
                if not ip.startswith("127."):
                    return ip
        except Exception:
            pass
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            s.close()
            return ip if not ip.startswith("127.") else "127.0.0.1"
        except Exception:
            return "127.0.0.1"

    def _update_web_server_status(self):
        """Update the web server status label."""
        if self.settings.web_server_enabled:
            ip = self._get_local_ip()
            url = f"http://{ip}:{self.settings.web_server_port}"
            self._web_server_status.setText(url)

            qr = qrcode.QRCode(box_size=2, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="white", back_color="black")

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            from PySide6.QtGui import QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.read())
            self._qr_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._qr_label.setVisible(True)
        else:
            self._web_server_status.setText("Остановлен")
            self._qr_label.setVisible(False)

    def _update_checkbox_style(self):
        """Update checkbox stylesheets with current accent color."""
        accent = cfg.get_accent_color()
        checkbox_style = f"""
            QCheckBox {{
                color: #CCCCCC;
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid rgba(80, 80, 80, 0.8);
                border-radius: 4px;
                background-color: #1a1a1a;
            }}
            QCheckBox::indicator:hover {{
                border-color: {accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
        """
        self.mini_widget_cb.setStyleSheet(checkbox_style)
        self.dynamic_color_cb.setStyleSheet(checkbox_style)
        self.web_server_cb.setStyleSheet(checkbox_style)
        self.prevent_sleep_cb.setStyleSheet(checkbox_style)

    def _on_cleanup_clicked(self):
        """Run database cleanup in background thread and show result."""
        self._cleanup_btn.setEnabled(False)
        self._cleanup_btn.setText("Чистка...")
        self._cleanup_worker = CleanupWorker(self)
        self._cleanup_worker.finished.connect(self._on_cleanup_finished)
        self._cleanup_worker.start()

    def _on_cleanup_finished(self, removed: int):
        """Handle cleanup completion."""
        if self.isVisible():
            self._cleanup_result_label.setText(f"Удалено треков: {removed}")
            self._cleanup_result_label.setVisible(True)
            self._cleanup_btn.setEnabled(True)
            self._cleanup_btn.setText("Чистка мусора")
            self._update_stats()
            QTimer.singleShot(3000, lambda: self._cleanup_result_label.setVisible(False))

    def closeEvent(self, event):
        self._port_debounce_timer.stop()
        self._spinner.stop()
        if hasattr(self, '_cleanup_worker') and self._cleanup_worker.isRunning():
            self._cleanup_worker.quit()
            self._cleanup_worker.wait()
        event.accept()

    def _update_combo_style(self):
        """Update combo box style with current accent."""
        accent = cfg.get_accent_color()
        self._opacity_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #000000;
                border: none;
                border-bottom: 1px solid {accent};
                color: #FFFFFF;
                font-size: 12px;
                padding: 3px 6px 2px 6px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #000000;
                border: 1px solid {accent};
                color: #FFFFFF;
                selection-background-color: {accent};
            }}
        """)

    def apply_accent_color(self, color: str):
        """Update accent color within this dialog."""
        self._update_combo_style()
        # Close button hover
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)

        # Folder button - preserve red border state
        folder = self.settings.music_folder
        has_folder = bool(folder and os.path.isdir(folder))
        self._update_folder_button_style(has_folder)

        # Checkbox
        self._update_checkbox_style()

        # Similarity slider
        self._sim_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(80, 80, 80, 0.5);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px;
                margin: -5px 0;
                background: {color};
                border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #FFFFFF;
            }}
            QSlider::sub-page:horizontal {{
                background: {color};
                border-radius: 2px;
            }}
        """)

        # Status bar labels
        self.library_count_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.covers_size_label.setStyleSheet(f"color: {color}; font-size: 12px;")

        # Web server port input
        self.port_input.setStyleSheet(self._port_style("#FFFFFF"))




