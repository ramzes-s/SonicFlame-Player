from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer import config as cfg
from musicplayer.core.db.system import get_system_value
from musicplayer.ui.svg_icons import get_music_note_svg


class AboutPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
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
