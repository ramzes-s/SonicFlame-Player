from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont

from musicplayer import config as cfg
from musicplayer.core.db_cleaner import cleanup_missing_tracks


class CleanupWorker(QThread):
    """Background worker for database cleanup."""
    finished = Signal(int)

    def run(self):
        removed = cleanup_missing_tracks()
        self.finished.emit(removed)


class SystemPage(QWidget):
    prevent_sleep_toggled = Signal(bool)
    cleanup_finished = Signal(int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(16)

        # Prevent sleep
        self.prevent_sleep_cb = QCheckBox("Блокировать сон при работающем плеере")
        self.prevent_sleep_cb.setChecked(self._settings.prevent_sleep)
        self.prevent_sleep_cb.toggled.connect(self._on_prevent_sleep_toggled)
        lo.addWidget(self.prevent_sleep_cb)

        lo.addStretch()

        # DB Cleanup
        self._cleanup_btn = QPushButton("Чистка мусора в БД")
        self._cleanup_btn.setFixedHeight(36)
        self._cleanup_btn.setCursor(Qt.PointingHandCursor)
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        lo.addWidget(self._cleanup_btn)
        self._update_cleanup_btn_style()

        self._apply_checkbox_style()

    def _on_prevent_sleep_toggled(self, checked: bool):
        self._settings.prevent_sleep = checked
        self.prevent_sleep_toggled.emit(checked)

    def _on_cleanup_clicked(self):
        self._cleanup_btn.setEnabled(False)
        self._cleanup_btn.setText("Чистка...")
        self._cleanup_worker = CleanupWorker(self)
        self._cleanup_worker.finished.connect(self._on_cleanup_finished)
        self._cleanup_worker.start()

    def _on_cleanup_finished(self, removed: int):
        if self.isVisible():
            self._cleanup_btn.setEnabled(True)
            self._cleanup_btn.setText("Чистка мусора")
            self.cleanup_finished.emit(removed)

    def _update_cleanup_btn_style(self):
        accent = cfg.get_accent_color()
        self._cleanup_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: 1px solid rgba(80,80,80,0.5);
                color: #CCCCCC; font-size: 13px; text-align: center;
            }}
            QPushButton:hover {{ color: {accent}; }}
        """)

    def _apply_checkbox_style(self):
        accent = cfg.get_accent_color()
        style = f"""
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
        self.prevent_sleep_cb.setStyleSheet(style)
        self.prevent_sleep_cb.setCursor(Qt.PointingHandCursor)

    def apply_accent_color(self, color: str):
        self._apply_checkbox_style()
        self._update_cleanup_btn_style()

    def cleanup(self):
        if hasattr(self, '_cleanup_worker') and self._cleanup_worker.isRunning():
            self._cleanup_worker.quit()
            self._cleanup_worker.wait()
