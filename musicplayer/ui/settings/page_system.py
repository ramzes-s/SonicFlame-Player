from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QComboBox, QLabel, QStyledItemDelegate, QFrame
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
from PySide6.QtGui import QFont

from musicplayer import config as cfg
from musicplayer.core.db_cleaner import cleanup_missing_tracks
from musicplayer.core.audio_device_manager import AudioDeviceManager


class CleanupWorker(QThread):
    """Background worker for database cleanup."""
    finished = Signal(int)

    def run(self):
        removed = cleanup_missing_tracks()
        self.finished.emit(removed)


class TallItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(sz.height(), 44))
        return sz


class SystemPage(QWidget):
    prevent_sleep_toggled = Signal(bool)
    idle_shutdown_changed = Signal(int)
    cleanup_finished = Signal(int)
    audio_device_changed = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(16)

        # Idle shutdown
        idle_row = QHBoxLayout()
        idle_row.setSpacing(10)
        idle_label = QLabel("Закрывать программу после простоя")
        idle_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        idle_row.addWidget(idle_label)
        idle_row.addStretch()
        self._idle_combo = QComboBox()
        self._idle_combo.setFixedWidth(200)
        self._idle_combo.setItemDelegate(TallItemDelegate(self._idle_combo))
        idle_options = [
            ("Никогда", 0),
            ("15 минут", 15),
            ("30 минут", 30),
            ("1 час", 60),
            ("3 часа", 180),
            ("6 часов", 360),
            ("12 часов", 720),
        ]
        saved = self._settings.idle_shutdown_minutes
        selected = 0
        for i, (label, mins) in enumerate(idle_options):
            self._idle_combo.addItem(label, mins)
            if mins == saved:
                selected = i
        self._idle_combo.setCurrentIndex(selected)
        self._idle_combo.currentIndexChanged.connect(self._on_idle_changed)
        idle_row.addWidget(self._idle_combo)
        lo.addLayout(idle_row)
        self._apply_idle_combo_style()

        # Prevent sleep
        self.prevent_sleep_cb = QCheckBox("Блокировать сон при работающем плеере")
        self.prevent_sleep_cb.setChecked(self._settings.prevent_sleep)
        self.prevent_sleep_cb.toggled.connect(self._on_prevent_sleep_toggled)
        lo.addWidget(self.prevent_sleep_cb)

        # Audio output device
        device_row = QHBoxLayout()
        device_row.setSpacing(10)
        device_label = QLabel("Устройство вывода звука")
        device_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        device_row.addWidget(device_label)
        device_row.addStretch()
        self._device_combo = QComboBox()
        self._device_combo.setFixedWidth(300)
        self._populate_device_list()
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._apply_combo_style()
        device_row.addWidget(self._device_combo)
        lo.addLayout(device_row)

        lo.addStretch()

        # DB Cleanup
        self._cleanup_btn = QPushButton("Чистка мусора в БД")
        self._cleanup_btn.setFixedHeight(36)
        self._cleanup_btn.setCursor(Qt.PointingHandCursor)
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        lo.addWidget(self._cleanup_btn)
        self._update_cleanup_btn_style()

        self._apply_checkbox_style()

    def _populate_device_list(self):
        self._device_combo.clear()
        self._device_combo.setItemDelegate(TallItemDelegate(self._device_combo))
        view = self._device_combo.view()
        if view:
            view.setFrameShape(QFrame.NoFrame)
            view.setFrameShadow(QFrame.Plain)
        self._device_combo.addItem("По умолчанию", None)
        for desc, dev_id in AudioDeviceManager.enumerate_devices():
            self._device_combo.addItem(desc, dev_id)
        saved_id = self._settings.audio_output_device
        for i in range(self._device_combo.count()):
            if self._device_combo.itemData(i) == saved_id:
                self._device_combo.setCurrentIndex(i)
                break

    def refresh_devices(self):
        current_id = self._device_combo.currentData()
        self._populate_device_list()
        for i in range(self._device_combo.count()):
            if self._device_combo.itemData(i) == current_id:
                self._device_combo.setCurrentIndex(i)
                break

    def _on_device_changed(self, idx: int):
        device_id = self._device_combo.itemData(idx)
        self._settings.audio_output_device = device_id
        self.audio_device_changed.emit(device_id)

    def _apply_idle_combo_style(self):
        accent = cfg.get_accent_color()
        self._idle_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {cfg.BG_COLOR};
                border: none;
                outline: none;
                border-bottom: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                font-size: 13px;
                padding: 1px 8px 1px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
                outline: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cfg.BG_COLOR};
                border: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                outline: none;
                margin: 0px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::viewport {{
                background-color: {cfg.BG_COLOR};
                border: none;
            }}
        """)

    def _apply_combo_style(self):
        accent = cfg.get_accent_color()
        self._device_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {cfg.BG_COLOR};
                border: none;
                outline: none;
                border-bottom: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                font-size: 14px;
                padding: 1px 8px 1px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
                outline: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cfg.BG_COLOR};
                border: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                outline: none;
                margin: 0px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::viewport {{
                background-color: {cfg.BG_COLOR};
                border: none;
            }}
        """)

    def _on_idle_changed(self, idx: int):
        mins = self._idle_combo.itemData(idx)
        self._settings.idle_shutdown_minutes = mins
        self.idle_shutdown_changed.emit(mins)

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
            self._cleanup_btn.setText(f"Удалено треков: {removed}")
            QTimer.singleShot(3000, lambda: self._cleanup_btn.setText("Чистка мусора в БД"))
            self.cleanup_finished.emit(removed)

    def _update_cleanup_btn_style(self):
        accent = cfg.get_accent_color()
        self._cleanup_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: 1px solid {cfg.DIVIDER_COLOR};
                color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px; text-align: center;
            }}
            QPushButton:hover {{ color: {accent}; }}
        """)

    def _apply_checkbox_style(self):
        accent = cfg.get_accent_color()
        style = f"""
            QCheckBox {{
                color: {cfg.TERTIARY_TEXT_COLOR};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {cfg.BUTTON_BORDER_COLOR};
                border-radius: 4px;
                background-color: {cfg.SECONDARY_BG_COLOR};
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
        self._apply_combo_style()
        self._apply_idle_combo_style()

    def cleanup(self):
        if hasattr(self, '_cleanup_worker') and self._cleanup_worker.isRunning():
            self._cleanup_worker.quit()
            self._cleanup_worker.wait()
