"""
Music Player - Main Entry Point

Modern Python Audio Player built with PySide6.
Features:
- Album art with ambient blur backdrop
- Playlist with smart auto-scroll
- Caching metadata for fast loading
- Full playback controls with SVG icons
"""

import sys
import os
import time
import json
import logging
import ctypes
from pathlib import Path

# Ensure mutagen is bundled (PyInstaller sometimes misses it)
import mutagen

# === SPLASH — BEFORE any heavy imports ===
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, QByteArray, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QPainterPath, QColor
from PySide6.QtSvg import QSvgRenderer


# === LOGGING CONFIGURATION ===
def _setup_logging():
    """Configure root logger with file + console handlers at DEBUG level."""
    from musicplayer import config as cfg

    log_dir = cfg.CACHE_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "debug.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler — простая запись в файл, каждая сессия начинается с чистого листа
    # Only created when LOG_DEBUG is True
    if cfg.LOG_DEBUG:
        fh = logging.FileHandler(str(log_file), mode='w', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d — %(message)s",
            datefmt="%H:%M:%S"
        ))
        root_logger.addHandler(fh)

    # Console handler — WARNING+ only (avoid clutter in terminal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root_logger.addHandler(ch)

    if cfg.LOG_DEBUG:
        logging.getLogger().info("Logging initialised — log file: %s", log_file)
    return log_file


def _setup_excepthook(log_file):
    """Install global exception hooks to catch unhandled crashes."""
    import traceback

    def excepthook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger().critical("UNHANDLED EXCEPTION:\n%s", msg)
        # Also write directly in case logging fails
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n==== UNHANDLED EXCEPTION ====\n{msg}\n")

    sys.excepthook = excepthook

    # Qt message handler — catches qWarning/qCritical from C++ side
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType

    def qt_message_handler(msg_type, context, message):
        level = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.CRITICAL,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }.get(msg_type, logging.WARNING)
        record = logging.getLogger("qt").makeRecord(
            "qt", level, context.file or "", context.line or 0,
            message, [], None
        )
        logging.getLogger("qt").handle(record)
        if msg_type == QtMsgType.QtFatalMsg:
            logging.getLogger("qt").critical("Qt FATAL — aborting")

    qInstallMessageHandler(qt_message_handler)


class AnimatedSplash(QSplashScreen):
    """Splash screen with fade-in/fade-out animation."""

    def __init__(self, pixmap):
        super().__init__(pixmap, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(50)
        self._fade_in.setStartValue(0)
        self._fade_in.setEndValue(1)
        self._fade_in.setEasingCurve(QEasingCurve.OutQuad)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(50)
        self._fade_out.setStartValue(1)
        self._fade_out.setEndValue(0)
        self._fade_out.setEasingCurve(QEasingCurve.InQuad)
        self._fade_out.finished.connect(self.close)

    def show_animated(self):
        self.show()
        self._fade_in.start()

    def finish_animated(self, widget):
        widget.show()
        self._fade_out.start()


def _ensure_icon():
    """Ensure Sonic-Flame.ico exists next to the executable (for frozen builds)."""
    if getattr(sys, 'frozen', False):
        dest = Path(sys.executable).parent / "Sonic-Flame.ico"
        if not dest.exists():
            src = Path(sys._MEIPASS) / "Sonic-Flame.ico"
            if src.exists():
                import shutil
                shutil.copy2(str(src), str(dest))

def _try_activate_existing_instance():
    """
    Single-instance lock via QSharedMemory.
    Returns True if another instance is running (and sends it an activate command).
    Keeps the shared memory reference alive via function attribute to prevent GC.
    """
    from PySide6.QtCore import QSharedMemory
    from PySide6.QtNetwork import QLocalSocket

    _lock = QSharedMemory("SonicFlamePlayer_SingleInstance")
    if _lock.attach():
        # Another instance exists — send activate command via the IPC server
        print("[SingleInstance] Existing instance detected, activating...")
        socket = QLocalSocket()
        socket.connectToServer("SonicFlamePlayerIPC_v2")
        if socket.waitForConnected(2000):
            payload = json.dumps({"type": "activate"}).encode("utf-8") + b'\n'
            socket.write(payload)
            socket.flush()
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            print("[SingleInstance] Activate command sent.")
        else:
            print(f"[SingleInstance] Could not connect to IPC server: "
                  f"{socket.errorString()}", file=sys.stderr)
        return True

    _lock.create(1)
    # Keep reference alive for the entire process lifetime
    _try_activate_existing_instance._lock = _lock
    print("[SingleInstance] First instance lock acquired.")
    return False


def main():
    """Application entry point."""
    log_file = _setup_logging()
    _setup_excepthook(log_file)
    _ensure_icon()

    logging.getLogger(__name__).info("App started (library=%s)", "--library" in sys.argv)

    # Suppress mpg123 logs (may or may not work depending on Qt backend setup)
    os.environ['MPG123_QUIET'] = '1'
    # Suppress FFmpeg/Qt Multimedia internal logs
    os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg*=false"

    # Check for --library flag to launch in library mode
    is_library_mode = "--library" in sys.argv

    # Windows: set application icon for taskbar
    appid_base = "MusicPlayer.SonicFlame.1.0"
    myappid = f"{appid_base}.Library" if is_library_mode else appid_base
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # Single-instance check (skip for library subprocess)
    if not is_library_mode and _try_activate_existing_instance():
        logging.getLogger(__name__).info("Existing instance detected, activating and exiting.")
        os._exit(0)

    if is_library_mode:
        # === LIBRARY MODE ===
        _run_library_mode(app)
        return

    # === PLAYER MODE (normal) ===
    _run_player_mode(app)

def _run_library_mode(app: QApplication):
    """Run the application in library subprocess mode."""
    from musicplayer.ui.library import LibraryDialog
    from musicplayer.ui.tag_editor import TagEditorDialog
    from musicplayer.core.db import extract_metadata, upsert_track, delete_track
    from musicplayer.core.ipc import IPCClient, SERVER_NAME
    import musicplayer.config

    def _get_accent_color() -> str:
        if musicplayer.config.SETTINGS_FILE.exists():
            try:
                data = json.loads(musicplayer.config.SETTINGS_FILE.read_text(encoding="utf-8"))
                color = data.get("accent_color")
                if color: return color
            except (json.JSONDecodeError, IOError): pass
        return "#ed6a02"

    app.setApplicationName("SonicFlame Library")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    musicplayer.config.ACCENT_COLOR = _get_accent_color()

    icon_path = musicplayer.config.PROJECT_DIR / "Sonic-Flame.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    dialog = LibraryDialog(None)
    if icon_path.exists():
        dialog.setWindowIcon(QIcon(str(icon_path)))

    # --- New IPC Client Setup ---
    ipc_client = IPCClient(SERVER_NAME, parent=app)

    def _open_tag_editor(filepath: str):
        editor = TagEditorDialog(filepath, None, update_player=False)
        if editor.exec() == 1:
            new_filepath = editor.file_path
            if os.path.exists(new_filepath):
                if os.path.normpath(new_filepath) != os.path.normpath(filepath):
                    delete_track(filepath)
                updated_track = extract_metadata(new_filepath)
                if updated_track:
                    upsert_track(updated_track, os.path.getmtime(new_filepath))
                    ipc_client.send_refresh()

    # Connect signals from dialog to IPC client
    dialog.track_selected.connect(ipc_client.send_play_track)
    dialog.edit_tags_requested.connect(_open_tag_editor)
    dialog.artist_play_requested.connect(ipc_client.send_play_artist)
    dialog.closed.connect(ipc_client.send_library_closed)

    ipc_client.refresh_requested.connect(dialog.refresh_data)
    ipc_client.show_requested.connect(dialog.show)
    ipc_client.close_requested.connect(app.quit)
    ipc_client.accent_color_changed.connect(dialog.on_accent_color_changed)

    ipc_client.start()

    dialog.show()
    sys.exit(app.exec())

def _run_player_mode(app: QApplication):
    """Run the application in main player mode."""

    def get_icon_path():
        """Get path to icon file (works for both dev and PyInstaller onefile)."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / "Sonic-Flame.ico"
        return Path(__file__).parent / "Sonic-Flame.ico"

    icon_path = get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Early DB version check before showing the splash
    from musicplayer.core.db.connection import init_db, check_db_version
    init_db()
    db_error = check_db_version()

    W, H = 1100, 600
    RADIUS = 12
    pixmap = QPixmap(W, H)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, W, H, RADIUS, RADIUS)
    painter.fillPath(path, Qt.black)

    logo_x = (W - 440) // 2
    logo_y = 20
    logo_size = 440

    if icon_path.exists():
        logo = QPixmap(str(icon_path))
        if not logo.isNull():
            logo_size = 440
            scaled_logo = logo.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_x = (W - scaled_logo.width()) // 2
            painter.drawPixmap(logo_x, logo_y, scaled_logo)

    painter.setPen(Qt.white)
    painter.setFont(QFont("Segoe UI", 28, QFont.Bold))
    painter.drawText(0, logo_y + logo_size + 10, W, 50, Qt.AlignCenter, "SonicFlame Player")

    if db_error:
        painter.setPen(QColor("#ed6a02"))
        painter.setFont(QFont("Segoe UI", 16))
        painter.drawText(0, logo_y + logo_size + 60, W, 80, Qt.AlignCenter | Qt.TextWordWrap, db_error)

    painter.end()

    splash = AnimatedSplash(pixmap)
    screen = app.primaryScreen().availableGeometry()
    splash.move((screen.width() - W) // 2, (screen.height() - H) // 2)
    splash.setWindowOpacity(1)
    splash.show()
    for _ in range(5):
        app.processEvents()
    time.sleep(0.15)

    if db_error:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10000, app.quit)
        sys.exit(app.exec())
        return

    from musicplayer.ui.main_window import MainWindow

    app.setApplicationName("SonicFlame Player")
    app.setOrganizationName("ramzes")

    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyle("Fusion")

    window = MainWindow()

    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))

    # Check if music_folder is set, force settings dialog if not
    if not window.settings.music_folder or not os.path.isdir(window.settings.music_folder):
        def deferred_settings():
            splash.hide()
            from musicplayer.ui.settings import SettingsDialog
            settings_dialog = SettingsDialog(window.settings, window)
            settings_dialog.music_folder_changed.connect(window.sidebar.set_music_folder_configured)
            if settings_dialog.exec():
                pass
            splash.finish_animated(window)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, deferred_settings)
    else:
        splash.finish_animated(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
