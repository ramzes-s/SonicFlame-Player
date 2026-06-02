import socket
from io import BytesIO

import qrcode

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QValidator, QFont

from musicplayer import config as cfg
from .constants import FORBIDDEN_PORTS
from .widgets import SpinnerWidget


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


class WebServerPage(QWidget):
    web_server_toggled = Signal(bool)
    port_changed = Signal(int)
    allow_remote_shutdown_toggled = Signal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pending_port = None
        self._port_debounce_timer = QTimer(self)
        self._port_debounce_timer.setSingleShot(True)
        self._port_debounce_timer.timeout.connect(self._on_port_debounce_complete)
        self._spinner = SpinnerWidget(self)
        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(16)

        h_row = QHBoxLayout()
        h_row.setSpacing(24)

        # Left column
        left = QVBoxLayout()
        left.setSpacing(16)

        self.web_server_cb = QCheckBox("Веб-сервер (удалённое управление)")
        self.web_server_cb.setChecked(self._settings.web_server_enabled)
        self.web_server_cb.toggled.connect(self._on_web_server_toggled)
        left.addWidget(self.web_server_cb)

        self.remote_shutdown_cb = QCheckBox("Разрешать удаленное закрытие программы")
        self.remote_shutdown_cb.setChecked(self._settings.allow_remote_shutdown)
        self.remote_shutdown_cb.setEnabled(self._settings.web_server_enabled)
        self.remote_shutdown_cb.toggled.connect(self._on_remote_shutdown_toggled)
        left.addWidget(self.remote_shutdown_cb)

        # Port
        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        port_label = QLabel("Порт:")
        port_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        self.port_input = QLineEdit()
        initial_port = self._settings.web_server_port
        if initial_port in FORBIDDEN_PORTS or not (1024 <= initial_port <= 65535):
            initial_port = 8080
            self._settings.web_server_port = 8080
        self.port_input.setText(str(initial_port))
        self.port_input.setFixedWidth(80)
        self.port_input.setAlignment(Qt.AlignCenter)
        self.port_input.setEnabled(self._settings.web_server_enabled)
        self.port_input.setValidator(PortValidator())
        self.port_input.textChanged.connect(self._on_port_changed)
        self._update_port_style("#FFFFFF")
        port_row.addWidget(self.port_input)
        port_row.addWidget(port_label)
        port_row.addWidget(self._spinner)
        self._web_server_status = QLabel()
        self._web_server_status.setStyleSheet("color: #888888; font-size: 11px;")
        port_row.addWidget(self._web_server_status)
        port_row.addStretch()
        left.addLayout(port_row)
        left.addStretch()
        h_row.addLayout(left)

        # Right column: QR
        self._qr_label = QLabel()
        self._qr_label.setFixedSize(150, 150)
        self._qr_label.setScaledContents(True)
        self._qr_label.setVisible(False)
        h_row.addWidget(self._qr_label, 0, Qt.AlignRight | Qt.AlignTop)

        lo.addLayout(h_row)

        self._apply_checkbox_style()

    def _on_web_server_toggled(self, checked: bool):
        self._settings.web_server_enabled = checked
        self.port_input.setEnabled(checked)
        self.remote_shutdown_cb.setEnabled(checked)
        self._update_status()
        self.web_server_toggled.emit(checked)

    def _on_remote_shutdown_toggled(self, checked: bool):
        self._settings.allow_remote_shutdown = checked
        self.allow_remote_shutdown_toggled.emit(checked)

    def _on_port_changed(self, text: str):
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
            self._update_port_style("#ff4444")
        else:
            self._update_port_style("#FFFFFF")

        self._spinner.start()
        self._port_debounce_timer.start(2000)

    def _on_port_debounce_complete(self):
        port = self._pending_port
        if port is None:
            self._spinner.stop()
            return

        if port in FORBIDDEN_PORTS or not (1024 <= port <= 65535):
            return

        self._settings.web_server_port = port
        self._spinner.stop()
        self.port_changed.emit(port)
        self._update_status()

    def _update_port_style(self, text_color: str) -> str:
        style = f"""
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
        self.port_input.setStyleSheet(style)
        return style

    def _get_local_ip(self):
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

    def _update_status(self):
        if self._settings.web_server_enabled:
            ip = self._get_local_ip()
            url = f"http://{ip}:{self._settings.web_server_port}"
            self._web_server_status.setText(url)

            qr = qrcode.QRCode(box_size=6, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="white", back_color="black")

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            pixmap = QPixmap()
            pixmap.loadFromData(buffer.read())
            self._qr_label.setPixmap(pixmap)
            self._qr_label.setVisible(True)
        else:
            self._web_server_status.setText("Остановлен")
            self._qr_label.setVisible(False)

    def refresh_status(self):
        self._update_status()

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
        self.web_server_cb.setStyleSheet(style)
        self.web_server_cb.setCursor(Qt.PointingHandCursor)
        self.remote_shutdown_cb.setStyleSheet(style)
        self.remote_shutdown_cb.setCursor(Qt.PointingHandCursor)

    def apply_accent_color(self, color: str):
        self._apply_checkbox_style()
        self._update_port_style("#FFFFFF")

    def cleanup(self):
        self._port_debounce_timer.stop()
        self._spinner.stop()
