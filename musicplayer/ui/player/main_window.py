"""
Main Window — coordinator assembling all UI blocks.
"""

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QIcon

from musicplayer.core.player import AudioPlayer
from musicplayer.core.playlist import Playlist
from musicplayer.core.settings import AppSettings, get_playlist_sort_mode
from musicplayer.core.ipc import IPCServer
from musicplayer.ui.web_integration import WebIntegration
from musicplayer.utils.analysis_worker import AnalysisManager
from musicplayer.ui.track_info import TrackInfoWidget
from musicplayer.ui.playlist_view import PlaylistWidget
from musicplayer.ui.controls import ControlsWidget
from musicplayer.ui.sidebar import SideBarWidget
from musicplayer.ui.player.title_bar import TitleBarWidget
from musicplayer.core.media_keys import create_media_keys_handler
from musicplayer.core.plugin_manager import PluginManager

from musicplayer import config as cfg
from musicplayer.ui.widgets.styled_message_box import StyledMessageBox

from musicplayer.ui.player.animation import BlinkAnimation
from musicplayer.ui.player.tray import TrayManager
from musicplayer.ui.player.scanning import ScanningManager
from musicplayer.ui.player.playback import PlaybackManager
from musicplayer.ui.player.playlist_ops import PlaylistManager


def _get_icon_path() -> Path:
    """Get path to app icon."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "Sonic-Flame.ico"
    return Path(__file__).parent.parent.parent.parent / "Sonic-Flame.ico"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("SonicFlame Player")
        self.setMinimumSize(1100, 600)
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")

        icon_path = _get_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(200, 200, 200, 100))
        self.setGraphicsEffect(shadow)

        self.player = AudioPlayer()
        self.playlist = Playlist()
        self.settings = AppSettings()
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)
        from musicplayer.core.db.connection import init_db
        init_db()
        self.scanner = None
        self._drag_pos = QPoint()
        self._current_folder_path = None
        self._current_playing_filepath = None
        self._mini_widget = None

        self._blink_animation = BlinkAnimation(self)

        self.__playback = PlaybackManager(self)
        self.__playlist = PlaylistManager(self)
        self.__scanning = ScanningManager(self)
        self.__tray = TrayManager(self)

        self.ipc_server = IPCServer(self)
        self.ipc_server.play_track_requested.connect(self.__playback.play_from_library)
        self.ipc_server.artist_play_requested.connect(self.__playlist.load_artist)
        self.ipc_server.library_closed.connect(self._on_ipc_library_closed)
        self.ipc_server.activate_requested.connect(self._on_activate_requested)
        self.ipc_server.start()

        self._web_integration = WebIntegration(self)
        self.analysis_manager = AnalysisManager(self)

        self._apply_saved_accent_color()
        self._restore_audio_device()
        self._setup_ui()
        self._connect_signals()

        # Ensure temp directory exists (used by plugins)
        cfg.TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # Ensure plugins directory and __init__.py exist
        cfg.PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        init_py = cfg.PLUGINS_DIR / "__init__.py"
        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")

        # Plugin system
        self._plugin_manager = PluginManager(self, self.settings)
        self._plugin_pages = []  # Filled by plugins via PluginHub
        self._plugin_manager.discover()
        self._plugin_manager.register_all()

        has_music_folder = bool(self.settings.music_folder and os.path.isdir(self.settings.music_folder))
        self.sidebar.set_music_folder_configured(has_music_folder)

        self._restore_state()

        self._media_keys_handler = None
        self._setup_media_keys()

        # Wire SMTC next/previous to playback manager
        self.player.smtc_next_requested.connect(self._playback.next)
        self.player.smtc_previous_requested.connect(self._playback.previous)

        if self.settings.web_server_enabled:
            self._web_integration.start(self.settings.web_server_port)

    @property
    def _playback(self) -> PlaybackManager:
        return self.__playback

    @property
    def _playlist(self) -> PlaylistManager:
        return self.__playlist

    @property
    def _scanning(self) -> ScanningManager:
        return self.__scanning

    # -- Public API for PluginHub --

    def add_plugin_page(self, page_widget, tab_name: str):
        """Add a new tab page to the Settings dialog (called by plugins)."""
        self._plugin_pages.append((page_widget, tab_name))

    def get_current_folder(self) -> str | None:
        """Return the currently opened folder path (or None)."""
        return self._current_folder_path

    def rescan_folder(self):
        """Re-scan the currently opened folder."""
        if self._current_folder_path:
            self.__scanning.scan(self._current_folder_path)

    @property
    def _tray(self) -> TrayManager:
        return self.__tray

    def _apply_saved_accent_color(self):
        saved_color = self.settings._data.get("accent_color")
        if saved_color:
            cfg.ACCENT_COLOR = saved_color

    def _restore_audio_device(self):
        saved_id = self.settings.audio_output_device
        if saved_id is not None:
            self.player.set_audio_device(saved_id)

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = cfg.get_accent_color()
        color = QColor(accent)
        for i in range(1, 4):
            c = QColor(color)
            c.setAlpha(80 - i * 15)
            pen = painter.pen()
            pen.setColor(c)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            rect = self.rect().adjusted(i, i, -i, -i)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def showMinimized(self):
        if self.settings.mini_widget_on_minimize:
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            if self._tray.tray_icon:
                self._tray.tray_icon.setVisible(True)
            self.hide()
            self.ipc_server.send_close()
            self._show_mini_widget()
        else:
            super().showMinimized()

    def _show_mini_widget(self):
        if self._mini_widget is None:
            from musicplayer.ui.mini_widget import MiniPlayerWidget
            self._mini_widget = MiniPlayerWidget()
            self._mini_widget.play_pause_clicked.connect(self._on_mini_play_pause)
            self._mini_widget.next_clicked.connect(self._on_mini_next)
            self._mini_widget.previous_clicked.connect(self._on_mini_previous)
            self._mini_widget.expand_requested.connect(self._restore_from_tray)
        self._mini_widget.set_opacity(self.settings.mini_widget_opacity)
        current_fp = self._current_playing_filepath
        if current_fp:
            for t in self.playlist_widget.get_view_tracks():
                if t.filepath == current_fp:
                    self._mini_widget.set_track_info(t.artist, t.title)
                    break
        self._mini_widget.set_play_state(self.player.is_playing())
        self._mini_widget.show()

    def _hide_mini_widget(self):
        if self._mini_widget:
            self._mini_widget.hide()

    def _on_mini_play_pause(self):
        self.player.toggle_play_pause()

    def _on_mini_next(self):
        self._on_next()

    def _on_mini_previous(self):
        self._on_previous()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._tray.hide()
        self._hide_mini_widget()
        self.ipc_server.send_close()

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange and self.windowState() & Qt.WindowMinimized:
            if self.settings.mini_widget_on_minimize:
                if self._tray.tray_icon:
                    self._tray.tray_icon.setVisible(True)
                self.hide()
                self.ipc_server.send_close()
        super().changeEvent(event)

    def closeEvent(self, event):
        self._hide_mini_widget()
        self._tray.hide()
        if self.scanner and self.scanner.isRunning():
            self.scanner.cancel()
        self.__scanning.cancel()
        if self.analysis_manager:
            self.analysis_manager.cancel_analysis()
        self.player.stop()
        self.player.close_smtc()
        self.ipc_server.stop()
        if hasattr(self, '_library_process') and self._library_process and self._library_process.poll() is None:
            self._library_process.terminate()
        if self._media_keys_handler:
            self._media_keys_handler.uninstall()
        self._web_integration.stop()
        # Clean up plugin temp files
        import shutil
        if cfg.TEMP_DIR.exists():
            shutil.rmtree(str(cfg.TEMP_DIR), ignore_errors=True)
        event.accept()

    def _setup_ui(self):
        container = QWidget()
        container.setObjectName("main_container")
        shadow2 = QGraphicsDropShadowEffect()
        shadow2.setBlurRadius(16)
        shadow2.setXOffset(0)
        shadow2.setYOffset(2)
        shadow2.setColor(QColor(200, 200, 200, 100))
        container.setGraphicsEffect(shadow2)
        accent = cfg.get_accent_color()
        r = int(accent[1:3], 16)
        g = int(accent[3:5], 16)
        b = int(accent[5:7], 16)
        container.setStyleSheet(f"#main_container {{ background-color: {cfg.BG_COLOR}; border: 2px solid rgba({r}, {g}, {b}, 0.1); }}")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)

        self.title_bar = TitleBarWidget()
        self.title_bar.minimize_button.clicked.connect(self.showMinimized)
        self.title_bar.close_button.clicked.connect(self.close)
        self.title_bar.sort_mode_changed.connect(self._on_sort_mode_changed)
        main_layout.addWidget(self.title_bar)

        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        self.sidebar = SideBarWidget()
        middle_layout.addWidget(self.sidebar)

        self.track_info_widget = TrackInfoWidget()
        middle_layout.addWidget(self.track_info_widget, stretch=0)

        self.playlist_widget = PlaylistWidget()
        middle_layout.addWidget(self.playlist_widget, stretch=1)
        self.playlist_widget.playlist_loaded.connect(self._web_integration.update_playlist)

        main_layout.addLayout(middle_layout, stretch=1)

        self.controls_widget = ControlsWidget()
        main_layout.addWidget(self.controls_widget)

    def _connect_signals(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.state_changed.connect(self._on_state_changed)
        self.player.error_occurred.connect(self._on_player_error)
        self.player.media_status_changed.connect(self._playback.on_media_status_changed)
        self.player.volume_changed.connect(self._on_volume_changed_for_web)
        self.player.volume_changed.connect(self.controls_widget.set_volume)
        self.player.empty_play_requested.connect(self._on_empty_play_requested)

        self.playlist_widget.track_selected.connect(self._playback.on_track_selected)
        self.playlist_widget.favorite_clicked.connect(self._playback.on_favorite_clicked)
        self.playlist_widget.badge_clicked.connect(self._playback.on_badge_clicked)
        self.playlist_widget.context_similar_tracks.connect(self._on_context_similar_tracks)
        self.playlist_widget.context_artist_tracks.connect(self._on_context_artist_tracks)

        self.track_info_widget.album_art_widget.clicked.connect(self._on_cover_clicked)

        self.controls_widget.play_pause_clicked.connect(self._on_play_pause)
        self.controls_widget.next_clicked.connect(self._on_next)
        self.controls_widget.previous_clicked.connect(self._on_previous)
        self.controls_widget.repeat_toggled.connect(self._on_repeat_toggled)
        self.controls_widget.seek_requested.connect(self._on_seek)
        self.controls_widget.volume_changed.connect(self._on_volume_changed)
        self.controls_widget.favorite_toggled.connect(self._playlist.on_control_favorite_toggled)
        self.controls_widget.similar_tracks_requested.connect(self._on_similar_tracks_requested)
        self.controls_widget.settings_requested.connect(self._on_settings_requested)

        self.sidebar.folder_open_requested.connect(self._on_open_folder)
        self.sidebar.favorites_toggled.connect(self._on_favorites_toggled)
        self.sidebar.top_requested.connect(self._on_top_toggled)
        self.sidebar.playlist_type_changed.connect(self._on_playlist_type_changed)
        self.sidebar.library_requested.connect(self._on_library_requested)

    def _on_volume_changed_for_web(self, volume: float):
        self._web_integration.update_state()

    def _on_open_folder(self):
        from musicplayer.ui.folder_browse.dialog import FolderBrowseDialog
        start_dir = self._current_folder_path or self.settings.last_folder or self.settings.music_folder or ""
        dlg = FolderBrowseDialog(
            parent=self,
            title="Выберите папку с музыкой",
            start_path=start_dir,
            root_path=self.settings.music_folder
        )
        if dlg.exec() != 1:
            return
        folder = dlg.selected_path
        self.settings.last_folder = folder
        self.settings.playlist_type = "Folder"
        self.title_bar.set_playlist_title(Path(folder).name)
        self.title_bar.set_show_separator(True)
        self.title_bar.set_scanning_status_style(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 11px;")
        self.title_bar.set_scanning_status("Сканирование...", True)
        self._blink_animation.start()
        self._scanning.scan(folder)

    def _on_sort_mode_changed(self, mode: str):
        if hasattr(self, 'playlist'):
            self.playlist.set_sort_mode(mode)
        if self.playlist_widget:
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            current = self.playlist.get_current_track()
            current_fp = getattr(self, "_current_playing_filepath", None) or (current.filepath if current else None)
            if current_fp:
                self.playlist_widget.set_current_track_by_filepath(current_fp)
                self.playlist_widget.set_playing_track(current_fp)

    def _on_cover_clicked(self):
        self.playlist_widget.scroll_to_current_track()

    def _on_play_pause(self):
        self.player.toggle_play_pause()
        self._web_integration.update_state()

    def _on_empty_play_requested(self):
        """Play pressed but no source loaded — play focused or first track."""
        tracks = self.playlist_widget.get_view_tracks()
        if not tracks:
            return
        row = self.playlist_widget.list_widget.currentRow()
        if 0 <= row < len(tracks):
            self._play_track_at_view_index(row)
        else:
            self._play_track_at_view_index(0)

    def _on_next(self):
        self._playback.next()

    def _on_previous(self):
        self._playback.previous()

    def _on_repeat_toggled(self, mode: str):
        self.playlist.set_repeat_mode(mode)
        self.settings.repeat_mode = mode

    def _on_seek(self, position_ms: int):
        self.player.set_position(position_ms)

    def _on_volume_changed(self, volume: float):
        self.player.set_volume(volume)
        self.settings.volume = volume

    def _on_position_changed(self, position_ms: int):
        self.controls_widget.set_position(position_ms)
        self._web_integration.update_state()

    def _on_duration_changed(self, duration_ms: int):
        self.controls_widget.set_duration(duration_ms)
        self._web_integration.update_state()

    def _on_state_changed(self, state):
        from PySide6.QtMultimedia import QMediaPlayer
        is_playing = (state == QMediaPlayer.PlayingState)
        self.controls_widget.set_play_state(is_playing)
        if self._mini_widget and self._mini_widget.isVisible():
            self._mini_widget.set_play_state(is_playing)
        self._web_integration.update_state()

        # Idle shutdown timer
        mins = self.settings.idle_shutdown_minutes
        if mins > 0:
            if is_playing:
                self._idle_timer.stop()
            elif not self._idle_timer.isActive():
                self._idle_timer.start(mins * 60 * 1000)

    def _on_idle_timeout(self):
        self._tray.hide()
        self._hide_mini_widget()
        QApplication.quit()

    def _on_player_error(self, error_msg: str):
        StyledMessageBox.critical(self, "Player Error", text=error_msg)

    def _on_favorites_toggled(self, enabled: bool):
        self._playlist.load_favorites(enabled)

    def _on_top_toggled(self, enabled: bool):
        self._playlist.load_top(enabled)

    def _on_playlist_type_changed(self, playlist_type: str):
        self.settings.playlist_type = playlist_type

    def _on_settings_requested(self):
        from musicplayer.ui.settings import SettingsDialog
        from musicplayer.ui.accent_style import apply_accent_to_main_window
        self._settings_dialog = SettingsDialog(
            self.settings, self, plugin_pages=self._plugin_pages,
            plugin_infos=self._plugin_manager.get_discovered_plugins(),
            plugin_manager=self._plugin_manager)
        dialog = self._settings_dialog
        dialog.accent_color_changed.connect(lambda color: apply_accent_to_main_window(self, settings_dialog=dialog))
        dialog.accent_color_changed.connect(lambda color: self.ipc_server.send_accent_color(color))
        dialog.dynamic_color_toggled.connect(self._playback.on_dynamic_color_toggled)
        dialog.web_server_toggled.connect(self._web_integration.set_enabled)
        dialog.web_server_port_changed.connect(self._web_integration.set_port)
        dialog.music_folder_changed.connect(self.sidebar.set_music_folder_configured)
        dialog.prevent_sleep_toggled.connect(self._on_prevent_sleep_toggled)
        dialog.audio_device_changed.connect(self.player.set_audio_device)
        dialog.db_reset_requested.connect(self._on_db_reset_requested)
        dialog.exec()
        self._settings_dialog = None
        apply_accent_to_main_window(self)

    def _on_prevent_sleep_toggled(self, enabled: bool):
        if self.player:
            self.player.set_prevent_sleep(enabled)

    def _on_db_reset_requested(self):
        from musicplayer.core.db.connection import DB_PATH, COVERS_DIR, init_db
        import shutil

        # Stop playback
        self.player.stop()
        self._current_playing_filepath = None

        # Backup DB file (rename to backup.db), delete old backup first
        backup_path = DB_PATH.parent / "backup.db"
        if backup_path.exists():
            backup_path.unlink()
        if DB_PATH.exists():
            DB_PATH.rename(backup_path)
        # Clean up WAL/SHM artifacts
        for suffix in ('-wal', '-shm'):
            p = Path(str(DB_PATH) + suffix)
            if p.exists():
                p.unlink()

        # Clear covers cache
        if COVERS_DIR.exists():
            shutil.rmtree(COVERS_DIR)

        # Recreate empty DB
        init_db()

        # Clear UI
        self.playlist.clear()
        self.playlist_widget.clear()
        self.track_info_widget.clear()

        # Rescan if music folder is set
        if self.settings.music_folder and os.path.isdir(self.settings.music_folder):
            self._scan_folder(self.settings.music_folder)

    def _on_library_requested(self):
        if not self.ipc_server.is_client_connected():
            self.ipc_server.start()

        if hasattr(self, '_library_process') and self._library_process and self._library_process.poll() is None:
            self.ipc_server.send_show()
            QTimer.singleShot(100, self.ipc_server.send_refresh)
            return

        import subprocess
        import sys
        exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent.parent.parent
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--library"]
        else:
            args = [sys.executable, str(exe_dir / "main.py"), "--library"]
        self._library_process = subprocess.Popen(args)

    def _on_ipc_library_closed(self):
        if hasattr(self, '_library_process') and self._library_process:
            self._library_process.poll()

    def _on_activate_requested(self):
        if self.isHidden():
            self._restore_from_tray()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _on_similar_tracks_requested(self):
        self._playlist.load_similar_tracks()

    def _on_artist_tracks_requested(self):
        fp = self._current_playing_filepath
        if not fp:
            return
        for t in self.playlist_widget.get_view_tracks():
            if t.filepath == fp:
                artist = (t.artist or "").split(";")[0].split(",")[0].strip()
                if artist and artist != "Unknown Artist":
                    self._playlist.load_artist(artist, bring_to_front=False)
                break

    def _on_context_similar_tracks(self, track):
        self._playlist.load_similar_tracks(track)

    def _on_context_artist_tracks(self, artist):
        if artist and artist != "Unknown Artist":
            self._playlist.load_artist(artist)

    def _play_track_at_view_index(self, view_index: int):
        self.__playback.play_track_at_view_index(view_index)

    def _scan_folder(self, folder_path: str):
        self.__scanning.scan(folder_path)

    def _scan_folder_and_play(self, folder_path: str, target_filepath: str):
        self.__playback.play_folder_and_track(folder_path, target_filepath)

    def _update_playlist_title(self):
        text, show_sep = "", False
        if self.sidebar._top_active:
            text, show_sep = "Топ", True
        elif self.sidebar._favorites_active:
            text, show_sep = "Избранное", True
        elif self._current_folder_path:
            if self.settings.music_folder and os.path.normpath(self._current_folder_path) == os.path.normpath(self.settings.music_folder):
                text, show_sep = "Вся музыка", True
            else:
                text, show_sep = Path(self._current_folder_path).name, True
        self.title_bar.set_playlist_title(text)
        self.title_bar.set_show_separator(show_sep)

    def _restore_state(self):
        vol = self.settings.volume
        if vol is not None:
            self.player.set_volume(vol)
            self.controls_widget.set_volume(vol)
        if self.settings.repeat_mode:
            self.playlist.set_repeat_mode(self.settings.repeat_mode)
            self.controls_widget.set_repeat_mode(self.settings.repeat_mode)

        path = None
        if self.settings.favorites_mode:
            from musicplayer.core.db import get_favorite_tracks
            self.sidebar._favorites_active = True
            self.sidebar._top_active = False
            self.sidebar.favorites_btn.set_active(True)
            self.sidebar.top_btn.set_active(False)
            fav_tracks = get_favorite_tracks()
            self.playlist.set_tracks(fav_tracks)
            mode = get_playlist_sort_mode()
            self.playlist.set_sort_mode(mode)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            self.settings.playlist_type = "Favorites"
            self._update_playlist_title()
            last_fp = self.settings.last_track
            if last_fp:
                for i, t in enumerate(self.playlist_widget.get_view_tracks()):
                    if t.filepath == last_fp:
                        self._play_track_at_view_index(i)
                        break
        elif self.settings.top_mode:
            from musicplayer.core.db import get_top_tracks
            self.sidebar._favorites_active = False
            self.sidebar._top_active = True
            self.sidebar.favorites_btn.set_active(False)
            self.sidebar.top_btn.set_active(True)
            top_tracks = get_top_tracks(100)
            self.playlist.set_tracks(top_tracks)
            mode = get_playlist_sort_mode()
            self.playlist.set_sort_mode(mode)
            self.playlist_widget.load_tracks(self.playlist.get_tracks())
            self.settings.playlist_type = "Top"
            self._update_playlist_title()
            last_fp = self.settings.last_track
            if last_fp:
                for i, t in enumerate(self.playlist_widget.get_view_tracks()):
                    if t.filepath == last_fp:
                        self._play_track_at_view_index(i)
                        break
        elif self.settings.last_folder and os.path.isdir(self.settings.last_folder):
            path = self.settings.last_folder
        elif self.settings.music_folder and os.path.isdir(self.settings.music_folder):
            path = self.settings.music_folder

        if path:
            self._scan_folder(path)
            self.settings.playlist_type = "Folder"
            self._update_playlist_title()

    def _setup_media_keys(self):
        self._media_keys_handler = create_media_keys_handler(
            int(self.winId()),
            self.player,
            self._on_next,
            self._on_previous
        )