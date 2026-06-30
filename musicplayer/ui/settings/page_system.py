import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QComboBox, QLabel, QStyledItemDelegate, QFrame, QScrollArea
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
from PySide6.QtGui import QFont

from musicplayer import config as cfg
from musicplayer.core.db_cleaner import cleanup_missing_tracks
from musicplayer.core.audio_device_manager import AudioDeviceManager
from musicplayer.core.db.broken_tracks import get_broken_track_count, get_all_broken_tracks
from musicplayer.ui.tag_editor.base_dialog import BaseFramelessDialog
from .constants import format_size
from .widgets import SpinnerWidget


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
    db_reset_requested = Signal()
    refresh_stats_requested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._analysis_manager = None
        self._build_ui()

    def set_analysis_manager(self, mgr):
        self._analysis_manager = mgr

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

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet(f"background-color: {cfg.DIVIDER_COLOR}; max-height: 1px; border: none;")
        lo.addWidget(sep)

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

        # Bottom group: reset db, stats card, cleanup (no gap)
        bottom = QVBoxLayout()
        bottom.setSpacing(0)
        bottom.setContentsMargins(0, 0, 0, 0)

        self._build_db_reset(bottom)

        self._build_stats_block(bottom)

        self._cleanup_btn = QPushButton("Чистка мусора в БД")
        self._cleanup_btn.setFixedHeight(36)
        self._cleanup_btn.setCursor(Qt.PointingHandCursor)
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        bottom.addWidget(self._cleanup_btn)
        self._update_cleanup_btn_style()

        lo.addLayout(bottom)

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

    def _show_broken_files_dialog(self):
        rows = get_all_broken_tracks()
        if not rows:
            return

        dlg = BaseFramelessDialog(self.window() if self.window() else self)
        dlg.setMinimumSize(880, 420)

        inner = dlg._setup_ui()
        inner.setContentsMargins(16, 0, 16, 12)
        inner.setSpacing(6)

        # Title bar
        title_label = QLabel(f"Битые файлы  ({len(rows)})")
        title_bar = dlg._build_title_bar("")
        title_bar.layout().insertWidget(1, title_label)
        inner.addWidget(title_bar)
        inner.addSpacing(8)

        # Scrollable list of custom items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {cfg.BG_COLOR};
                border: 1px solid {cfg.BUTTON_BORDER_COLOR};
            }}
            QScrollBar:vertical {{
                background: {cfg.BG_COLOR};
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {cfg.DIVIDER_COLOR};
                min-height: 30px;
            }}
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        for filepath, _folder, error, _detected_at in rows:
            item_widget = self._build_broken_item(filepath, error, scroll_layout, title_label)
            scroll_layout.addWidget(item_widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        inner.addWidget(scroll, stretch=1)
        dlg.center_on_parent()
        dlg.exec()

    def _build_broken_item(self, filepath: str, error: str, parent_layout: QVBoxLayout, title_label: QLabel) -> QWidget:
        try:
            size = os.path.getsize(filepath)
            size_str = format_size(size)
        except Exception:
            size_str = "—"

        item = QWidget()
        item.setStyleSheet(f"""
            QWidget {{
                background-color: {cfg.BG_COLOR};
                border-bottom: 1px solid {cfg.DIVIDER_COLOR};
            }}
        """)
        item.setMinimumHeight(48)

        row = QHBoxLayout(item)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(12)

        # Left side — two lines
        left = QVBoxLayout()
        left.setSpacing(2)

        path_lbl = QLabel(filepath)
        path_lbl.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 12px; background: transparent; border: none;")
        path_lbl.setWordWrap(True)
        left.addWidget(path_lbl)

        info_lbl = QLabel(f"Вес: {size_str}    Проблема: {error}")
        info_lbl.setStyleSheet(f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px; background: transparent; border: none;")
        left.addWidget(info_lbl)

        row.addLayout(left, stretch=1)

        # Delete button
        del_btn = QPushButton("Удалить файл")
        del_btn.setFixedHeight(26)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid #ff4444;
                color: #ff4444;
                font-size: 11px;
                font-weight: bold;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: #ff4444;
                color: #FFFFFF;
            }}
        """)
        del_btn.clicked.connect(lambda checked, fp=filepath: self._delete_broken_file(fp, item, parent_layout, title_label))
        row.addWidget(del_btn, 0, Qt.AlignVCenter)

        return item

    def _delete_broken_file(self, filepath: str, item_widget: QWidget, parent_layout: QVBoxLayout, title_label: QLabel):
        # Remove from broken_tracks table
        from musicplayer.core.db.broken_tracks import clear_broken_track
        clear_broken_track(filepath)

        # Delete file from disk
        try:
            os.remove(filepath)
            print(f"[broken_dialog] Удалён: {filepath}")
        except Exception as e:
            print(f"[broken_dialog] Ошибка удаления {filepath}: {e}")

        # Remove widget from layout
        parent_layout.removeWidget(item_widget)
        item_widget.deleteLater()

        # Update dialog title count
        remaining = parent_layout.count() - 1  # subtract stretch
        title_label.setText(f"Битые файлы  ({remaining})")

    def _build_db_reset(self, lo: QVBoxLayout):
        self._reset_db_btn = QPushButton("Удалить базу данных (Необратимо!)")
        self._reset_db_btn.setFixedHeight(36)
        self._reset_db_btn.setCursor(Qt.PointingHandCursor)
        self._reset_db_btn.clicked.connect(self._on_reset_db)
        self._update_db_reset_btn_style()
        lo.addWidget(self._reset_db_btn)

    def _update_db_reset_btn_style(self):
        accent = cfg.get_accent_color()
        self._reset_db_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                border: none;
                color: #000000;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FFFFFF;
                color: #000000;
            }}
            QPushButton:pressed {{
                background-color: #cccccc;
                color: #000000;
            }}
        """)

    def _on_reset_db(self):
        from musicplayer.ui.widgets.styled_message_box import StyledMessageBox
        parent = self.window() if self.window() else self
        result = StyledMessageBox.question(
            parent, "Сброс базы данных",
            "Все треки, плейлисты и статистика будут удалены.\n"
            "Настройки останутся без изменений.\n\n"
            "Продолжить?"
        )
        if result == 1:
            self.db_reset_requested.emit()

    def _build_stats_block(self, lo: QVBoxLayout):
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(10000)
        self._stats_timer.timeout.connect(self._auto_refresh_stats)

        self._stats_card = QWidget()
        self._stats_card.setStyleSheet(f"""
            QWidget {{
                background-color: #0a0a0a;
                border: 1px solid {cfg.DIVIDER_COLOR};
                border-bottom: none;
            }}
        """)
        inner = QVBoxLayout(self._stats_card)
        inner.setContentsMargins(16, 10, 16, 10)
        inner.setSpacing(4)

        accent = cfg.get_accent_color()
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._stats_title = QLabel("Библиотека")
        self._stats_title.setStyleSheet(f"color: {accent}; font-size: 13px; font-weight: bold; "
                                        f"background: transparent; border: none;")
        title_row.addWidget(self._stats_title)
        self._stats_spinner = SpinnerWidget()
        title_row.addWidget(self._stats_spinner)
        title_row.addStretch()
        inner.addLayout(title_row)

        self._stats_tracks = QLabel()
        self._stats_tracks.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px; "
                                         f"background: transparent; border: none;")
        inner.addWidget(self._stats_tracks)

        self._stats_covers = QLabel()
        self._stats_covers.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px; "
                                         f"background: transparent; border: none;")
        inner.addWidget(self._stats_covers)

        self._stats_collages = QLabel()
        self._stats_collages.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px; "
                                           f"background: transparent; border: none;")
        inner.addWidget(self._stats_collages)

        # Broken files button — bottom-right
        self._broken_btn = QPushButton("Битых файлов")
        self._broken_btn.setFixedHeight(28)
        self._broken_btn.setCursor(Qt.PointingHandCursor)
        self._broken_btn.setVisible(False)
        self._broken_btn.clicked.connect(self._show_broken_files_dialog)
        self._broken_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #000000;
                border: 1px solid {cfg.BUTTON_BORDER_COLOR};
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background-color: {cfg.SECONDARY_BG_COLOR};
            }}
        """)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._broken_btn)
        inner.addLayout(btn_row)

        lo.addWidget(self._stats_card)

    def update_stats(self, track_count: int, analyzed_count: int,
                     covers_count: int, covers_size: int,
                     collages_count: int, collages_size: int):
        self._stats_tracks.setText(f"Треков: {track_count}  •  Проанализированно: {analyzed_count}")
        self._stats_covers.setText(f"Кеш обложек ({covers_count} шт):  {format_size(covers_size)}")
        self._stats_collages.setText(f"Кеш коллажей ({collages_count} шт):  {format_size(collages_size)}")

        analysis_active = (
            self._analysis_manager is not None
            and self._analysis_manager.is_analysis_running()
        )

        if analysis_active:
            if not self._stats_timer.isActive() and self.isVisible():
                self._stats_spinner.start()
                self._stats_timer.start()
        else:
            self._stats_spinner.stop()
            self._stats_timer.stop()

    def _auto_refresh_stats(self):
        if self.isVisible():
            self.refresh_stats_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._auto_refresh_stats()
        # Lazy-load broken file count without blocking
        QTimer.singleShot(0, self._update_broken_count)

    def _update_broken_count(self):
        count = get_broken_track_count()
        self._broken_btn.setText(f"Битых файлов: {count}" if count > 0 else "Битых файлов")
        self._broken_btn.setVisible(count > 0)

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

    def _apply_stats_style(self, color: str):
        divider = cfg.DIVIDER_COLOR
        self._stats_card.setStyleSheet(f"""
            QWidget {{
                background-color: #0a0a0a;
                border: 1px solid {divider};
                border-bottom: none;
            }}
        """)
        self._stats_title.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; "
                                        f"background: transparent; border: none;")

    def apply_accent_color(self, color: str):
        self._apply_checkbox_style()
        self._update_cleanup_btn_style()
        self._update_db_reset_btn_style()
        self._apply_combo_style()
        self._apply_idle_combo_style()
        self._apply_stats_style(color)

    def cleanup(self):
        self._stats_timer.stop()
        self._stats_spinner.stop()
        if hasattr(self, '_cleanup_worker') and self._cleanup_worker.isRunning():
            self._cleanup_worker.quit()
            self._cleanup_worker.wait()
