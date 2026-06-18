import hashlib
import logging
import subprocess
from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QByteArray, QUrl, QThread, Signal, QTimer
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtGui import QPixmap, QPainter, QFont
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

logger = logging.getLogger("register")


class _HwIdWorker(QThread):
    hwid_ready = Signal(str)

    def run(self):
        hwid = _get_hardware_id()
        self.hwid_ready.emit(hwid)


def _get_hardware_id() -> str:
    parts = []
    try:
        out = subprocess.check_output("wmic csproduct get uuid", shell=True, timeout=3, stderr=subprocess.DEVNULL)
        uuid = out.decode("utf-8", errors="ignore").strip().split("\n")[-1].strip()
        if uuid:
            parts.append(uuid)
    except Exception as e:
        print(f"_get_hardware_id: wmic uuid failed: {e}")
    try:
        out = subprocess.check_output("wmic cpu get processorid", shell=True, timeout=3, stderr=subprocess.DEVNULL)
        cpu = out.decode("utf-8", errors="ignore").strip().split("\n")[-1].strip()
        if cpu:
            parts.append(cpu)
    except Exception as e:
        print(f"_get_hardware_id: wmic cpu failed: {e}")
    try:
        out = subprocess.check_output("wmic diskdrive get serialnumber", shell=True, timeout=3, stderr=subprocess.DEVNULL)
        serial = out.decode("utf-8", errors="ignore").strip().split("\n")[-1].strip()
        if serial:
            parts.append(serial)
    except Exception as e:
        print(f"_get_hardware_id: wmic diskdrive failed: {e}")
    try:
        import uuid as _uuid
        parts.append(str(_uuid.getnode()))
    except Exception as e:
        print(f"_get_hardware_id: getnode failed: {e}")

    raw = "-".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:24]}"

from musicplayer import config as cfg
from musicplayer.core.db.system import get_system_value
from musicplayer.ui.svg_icons import get_music_note_svg


class AboutPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._net = QNetworkAccessManager(self)
        self._build_ui()

    def _build_ui(self):
        accent = cfg.get_accent_color()

        lo = QVBoxLayout(self)
        lo.setContentsMargins(12, 10, 12, 10)
        lo.setSpacing(0)

        lo.addStretch(1)

        # App title + version (accent color)
        self._title_label = QLabel(f"SonicFlame Player  v{cfg.APP_VERSION}")
        self._title_label.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 600;")
        self._title_label.setAlignment(Qt.AlignCenter)
        lo.addWidget(self._title_label)

        lo.addSpacing(10)
        db_ver = get_system_value('db_version_compare')
        db_ver_str = db_ver if db_ver is not None else "не установлена"
        ver_label = QLabel(f"Версия БД: {db_ver_str}.   Требуемая версия БД: {cfg.DB_VERSION}")
        ver_label.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 12px;")
        ver_label.setAlignment(Qt.AlignCenter)
        lo.addWidget(ver_label)
        lo.addSpacing(20)

        # Author note
        note = QLabel(
            "Музыкальный плеер, созданный с душой и вниманием к деталям.\n"
            "Спасибо, что пользуетесь!\nАвтор: ramzes (ramzes@sonicflame.pro)"
        )
        note.setStyleSheet("color: #AAAAAA; font-size: 13px;")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        lo.addWidget(note)
        lo.addSpacing(30)

        # Icon (transparent, 128x128)
        self._icon_label = QLabel()
        self._update_icon(accent)
        lo.addWidget(self._icon_label)

        lo.addSpacing(16)

        # Registration section
        self._reg_widget = QWidget()
        self._reg_widget.setStyleSheet("background: transparent;")
        reg_lo = QVBoxLayout(self._reg_widget)
        reg_lo.setContentsMargins(0, 0, 0, 0)
        reg_lo.setSpacing(6)

        self._reg_btn = QPushButton("Регистрация плеера")
        self._reg_btn.setFixedHeight(34)
        self._reg_btn.setCursor(Qt.PointingHandCursor)
        self._reg_btn.clicked.connect(self._on_register)
        reg_lo.addWidget(self._reg_btn, 0, Qt.AlignCenter)

        self._reg_status = QLabel()
        self._reg_status.setAlignment(Qt.AlignCenter)
        self._reg_status.setWordWrap(True)
        self._reg_status.setVisible(False)
        reg_lo.addWidget(self._reg_status)

        lo.addWidget(self._reg_widget)

        lo.addStretch(1)

        # Links row at bottom: GitHub (white) + 100px + Site (orange)
        links_row = QHBoxLayout()
        links_row.addStretch()

        gh_link = QLabel(f'<a href="https://github.com/ramzes-s/SonicFlame-Player" '
                         f'style="color: {cfg.BG_COLOR}; text-decoration: none; font-weight: bold; font-size: 14px;">GitHub</a>')
        gh_link.setOpenExternalLinks(True)
        gh_link.setCursor(Qt.PointingHandCursor)
        gh_link.setAlignment(Qt.AlignCenter)
        gh_link.setFixedSize(120, 36)

        gh_frame = QWidget()
        gh_lo = QHBoxLayout(gh_frame)
        gh_lo.setContentsMargins(0, 0, 0, 0)
        gh_lo.addWidget(gh_link)
        gh_frame.setFixedSize(120, 36)
        gh_frame.setStyleSheet(f"""
            QWidget {{
                background-color: {cfg.TEXT_COLOR};
                border-radius: 6px;
            }}
        """)
        links_row.addWidget(gh_frame)
        links_row.addSpacing(100)

        site_link = QLabel(f'<a href="https://sonicflame.pro/" '
                           f'style="color: {cfg.TEXT_COLOR}; text-decoration: none; font-weight: bold; font-size: 14px;">Сайт проекта</a>')
        site_link.setOpenExternalLinks(True)
        site_link.setCursor(Qt.PointingHandCursor)
        site_link.setAlignment(Qt.AlignCenter)
        site_link.setFixedSize(120, 36)

        site_frame = QWidget()
        site_lo = QHBoxLayout(site_frame)
        site_lo.setContentsMargins(0, 0, 0, 0)
        site_lo.addWidget(site_link)
        site_frame.setFixedSize(120, 36)
        site_frame.setStyleSheet("""
            QWidget {
                background-color: #ed6a02;
                border-radius: 6px;
            }
        """)
        links_row.addWidget(site_frame)
        links_row.addStretch()
        lo.addLayout(links_row)

        lo.addSpacing(16)

        self._update_reg_btn_style(accent)
        self._update_reg_ui()

    def _update_reg_ui(self):
        accent = cfg.get_accent_color()
        pid = self._settings.player_id
        lo = self._reg_widget.layout()

        # remove old key block if any
        for attr in ('_reg_key_block', '_reg_hwid_block'):
            blk = getattr(self, attr, None)
            if blk:
                lo.removeWidget(blk)
                blk.deleteLater()
                setattr(self, attr, None)

        self._reg_btn.setVisible(pid is None)
        self._reg_status.setVisible(False)

        if pid:
            self._reg_key_block = QWidget()
            self._reg_key_block.setFixedHeight(40)
            self._reg_key_block.setStyleSheet(f"""
                QWidget {{
                    background-color: {cfg.BG_COLOR};
                    border: 1px solid {accent};
                }}
            """)
            bl = QHBoxLayout(self._reg_key_block)
            bl.setContentsMargins(14, 0, 14, 0)

            key_lbl = QLabel(pid)
            key_lbl.setFont(QFont("Consolas", 12))
            key_lbl.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
            key_lbl.setAlignment(Qt.AlignCenter)
            bl.addWidget(key_lbl)

            lo.insertWidget(1, self._reg_key_block, 0, Qt.AlignCenter)

    def _update_reg_btn_style(self, accent):
        self._reg_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                border: none;
                color: {cfg.CTR_TEXT_COLOR};
                font-size: 13px; font-weight: bold;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {cfg.TEXT_COLOR};
                color: {cfg.BG_COLOR};
            }}
            QPushButton:disabled {{
                background-color: {cfg.DISABLED_TEXT_COLOR};
            }}
        """)

    def _on_register(self):
        self._reg_btn.setEnabled(False)
        self._reg_btn.setText("Получение HWID...")
        self._reg_status.setVisible(False)
        self._update_reg_btn_style(cfg.get_accent_color())

        self._hwid_worker = _HwIdWorker(self)
        self._hwid_worker.hwid_ready.connect(self._on_hwid_ready)
        self._hwid_worker.finished.connect(self._hwid_worker.deleteLater)
        self._hwid_worker.start()

    def _on_hwid_ready(self, hwid: str):
        self._reg_btn.setText("Регистрация...")
        today = datetime.now().strftime("%d%m%Y")

        logger.info("Sending POST to https://sonicflame.pro/api/register.php with firstkey=%s", today)

        url = QUrl("https://sonicflame.pro/api/register.php")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        req.setRawHeader(b"User-Agent", b"SonicFlame Player")

        body = f'{{"firstkey":"{today}","hardware_id":"{hwid}"}}'.encode("utf-8")
        reply = self._net.post(req, body)
        reply.finished.connect(self._on_reg_reply)
        QTimer.singleShot(10000, reply, reply.abort)

    def _on_reg_reply(self):
        reply = self.sender()
        if not reply:
            return
        reply.finished.disconnect(self._on_reg_reply)
        reply.deleteLater()

        self._reg_btn.setEnabled(True)
        self._reg_btn.setText("Регистрация плеера")
        self._update_reg_btn_style(cfg.get_accent_color())

        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        if status == 403:
            self._show_status("Сервер регистрации отключен.", error=True)
            return

        if reply.error() != QNetworkReply.NetworkError.NoError:
            if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                self._show_status("Сервер недоступен (таймаут 10 с)", error=True)
            else:
                self._show_status(f"Ошибка сети: {reply.errorString()}", error=True)
            return

        data = reply.readAll().data()

        try:
            text = data.decode("utf-8")
            logger.info("HTTP %s: %s", status, text)
            import json
            resp = json.loads(text)
        except Exception as e:
            print(f"_on_reg_reply: JSON parse failed: {e}")
            code = status if status else "—"
            logger.warning("HTTP %s, parse error", code)
            self._show_status(f"Ошибка сервера (HTTP {code})", error=True)
            return

        if resp.get("status") == "ok":
            pid = resp.get("player_id", "").strip()
            if pid:
                self._settings.player_id = pid
                self._update_reg_ui()
        else:
            msg = resp.get("message", f"Ошибка (HTTP {status})")
            self._show_status(msg, error=True)

    def _show_status(self, text: str, error: bool = False):
        accent = cfg.get_accent_color()
        self._reg_status.setText(text)
        self._reg_status.setStyleSheet(
            f"color: {'#ff4444' if error else accent}; font-size: 12px; background: transparent; border: none;"
        )
        self._reg_status.setVisible(True)

    def _update_icon(self, accent: str):
        pixmap = QPixmap(128, 128)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        note_svg = QSvgWidget()
        note_svg.renderer().load(QByteArray(get_music_note_svg(128, accent).encode('utf-8')))
        note_svg.renderer().render(p)
        p.end()
        self._icon_label.setPixmap(pixmap)
        self._icon_label.setAlignment(Qt.AlignCenter)

    def apply_accent_color(self, color: str):
        self._title_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")
        self._update_icon(color)
        self._update_reg_btn_style(color)
        self._update_reg_ui()