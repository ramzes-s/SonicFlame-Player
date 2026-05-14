"""
Title Bar Widget

Custom frameless title bar with window controls and playlist info.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer.ui.svg_icons import get_music_note_svg
from musicplayer.core.settings import get_playlist_sort_mode, set_playlist_sort_mode
from musicplayer import config as cfg


class TitleBarWidget(QWidget):
    """Custom title bar widget for the main window."""

    sort_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #000000;")
        self._setup_ui()

    def _setup_ui(self):
        title_layout = QHBoxLayout(self)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        self.title_icon_widget = QSvgWidget()
        self.title_icon_widget.setFixedSize(20, 20)
        self.title_icon_widget.renderer().load(get_music_note_svg(60).encode('utf-8'))
        title_layout.addWidget(self.title_icon_widget)

        title_label = QLabel("SonicFlame Player")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        self.playlist_title_label = QLabel("")
        self.playlist_title_label.setStyleSheet("color: #888888; font-size: 12px; margin-left: 4px;")
        title_layout.addWidget(self.playlist_title_label)

        self.sep_label = QLabel("•")
        self.sep_label.setStyleSheet("color: #555555; font-size: 12px;")
        self.sep_label.setVisible(False)
        title_layout.addWidget(self.sep_label)

        self.scanning_status_label = QLabel("")
        self.scanning_status_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.scanning_status_label.setVisible(False)
        title_layout.addWidget(self.scanning_status_label)

        title_layout.addStretch()

        self._sort_combo = QComboBox()
        self._sort_combo.setStyleSheet("""
            QComboBox { background: #000000; border: none; color: #CCCCCC; font-size: 12px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #000000; color: #CCCCCC; selection-background-color: #333333; }
        """)
        self._sort_combo.setFixedSize(170, 26)
        self._sort_combo.addItems(["По исполнителю", "По названию", "По новизне", "Перемешать"])

        self._sort_combo.blockSignals(True)
        try:
            current = get_playlist_sort_mode()
        except Exception:
            current = "artist"
        index_map = {"artist": 0, "title": 1, "newest": 2, "shuffle": 3}
        self._sort_combo.setCurrentIndex(index_map.get(current, 0))
        self._sort_combo.blockSignals(False)

        self._sort_combo.currentIndexChanged.connect(self._on_sort_mode_changed)
        title_layout.addWidget(self._sort_combo)

        self._min_btn = QPushButton("─")
        self._min_btn.setFixedSize(36, 30)
        self._min_btn.setCursor(Qt.PointingHandCursor)
        self._min_btn.setStyleSheet(self._get_title_button_style())
        title_layout.addWidget(self._min_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(36, 30)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(self._get_title_button_style(cfg.get_accent_color()))
        title_layout.addWidget(self._close_btn)

    def _on_sort_mode_changed(self, index: int):
        mapping = {0: "artist", 1: "title", 2: "newest", 3: "shuffle"}
        mode = mapping.get(index, "artist")
        try:
            set_playlist_sort_mode(mode)
        except Exception:
            pass
        self.sort_mode_changed.emit(mode)

    def set_playlist_title(self, title: str):
        self.playlist_title_label.setText(title)

    def get_playlist_title(self) -> str:
        return self.playlist_title_label.text()

    def set_show_separator(self, show: bool):
        self.sep_label.setVisible(show)

    def set_scanning_status(self, text: str, visible: bool = True):
        self.scanning_status_label.setText(text)
        self.scanning_status_label.setVisible(visible)

    def set_scanning_status_style(self, style: str):
        self.scanning_status_label.setStyleSheet(style)

    def hide_scanning_status(self):
        self.scanning_status_label.setVisible(False)

    def set_sort_enabled(self, enabled: bool):
        self._sort_combo.setEnabled(enabled)

    def set_sort_mode(self, mode: str):
        index_map = {"artist": 0, "title": 1, "newest": 2, "shuffle": 3}
        self._sort_combo.blockSignals(True)
        self._sort_combo.setCurrentIndex(index_map.get(mode, 0))
        self._sort_combo.blockSignals(False)

    def update_close_button_color(self, color: str):
        self._close_btn.setStyleSheet(self._get_title_button_style(color))

    @property
    def minimize_button(self):
        return self._min_btn

    @property
    def close_button(self):
        return self._close_btn

    @property
    def sort_combo(self):
        return self._sort_combo

    def _get_title_button_style(self, hover_color: str = "#333333") -> str:
        return f"""
            QPushButton {{ background-color: transparent; border: none; color: #FFFFFF; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ background-color: #555555; }}
        """