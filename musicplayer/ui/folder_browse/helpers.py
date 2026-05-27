import os
from pathlib import Path

from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from musicplayer.ui.svg_icons import get_folder_svg


_IS_WIN = os.name == 'nt'


def _norm_path(path: str) -> str:
    n = os.path.normpath(path)
    return n.lower() if _IS_WIN else n


def _path_startswith(path: str, prefix: str) -> bool:
    p = _norm_path(path)
    pr = _norm_path(prefix) + os.sep
    return p.startswith(pr) or p == _norm_path(prefix)


def _make_folder_icon(px: int = 20, color: str = "#FFFFFF") -> QIcon:
    svg = get_folder_svg(16, color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    off = (px - 16) // 2
    renderer.render(painter, QRectF(off, off, 16, 16))
    painter.end()
    return QIcon(pixmap)


def _track_count_str(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} трек"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} трека"
    return f"{n} треков"


def _folder_count_str(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} папка"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} папки"
    return f"{n} папок"


_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background-color: #000000;
        width: 5px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background-color: rgba(80, 80, 80, 0.6);
        border-radius: 3px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: rgba(120, 120, 120, 0.8);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""

_FOLDER_ICON = None


def _get_folder_icon():
    global _FOLDER_ICON
    if _FOLDER_ICON is None:
        _FOLDER_ICON = _make_folder_icon(20, "#FFFFFF")
    return _FOLDER_ICON


def _get_track_count(folder_path: str) -> int:
    from musicplayer.core.db.folders import get_folder_track_count
    count = get_folder_track_count(folder_path)
    if count is not None:
        return count
    count = 0
    for ext in ('.mp3', '.flac', '.m4a', '.mp4'):
        try:
            count += len(list(Path(folder_path).glob(f'*{ext}')))
        except (PermissionError, OSError):
            pass
    return count


def _get_subfolder_count(folder_path: str) -> int:
    try:
        return sum(1 for e in os.scandir(folder_path) if e.is_dir())
    except (PermissionError, OSError):
        return 0
