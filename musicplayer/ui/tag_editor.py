"""
Tag Editor Dialog

Dialog for editing track metadata (ID3 tags) with:
- Cover art display, upload, and search via iTunes API
- Track info search via iTunes Search API
- Fields: title, artist, album, year, genre, track number, filename
- Save tags to file and rename file
"""

import os
import re
import time
import json
import urllib.request
from pathlib import Path
import sys

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                QLabel, QLineEdit, QPushButton, QFileDialog,
                                QMessageBox, QWidget, QScrollArea, QFrame,
                                QGridLayout)
from PySide6.QtCore import Qt, QSize, QPoint, QByteArray, Signal, QTimer, QRectF, QThread
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPaintEvent, QMouseEvent, QLinearGradient
from PySide6.QtSvgWidgets import QSvgWidget

# NEW Imports
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import random

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture as FlacPicture
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, ID3NoHeaderError

from musicplayer import config as cfg
from musicplayer.ui.svg_icons import get_music_note_svg


class LoadingBar(QWidget):
    """Thin animated loading bar at the bottom of the dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._offset = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._visible = False

    def start(self):
        """Start the loading animation."""
        self._visible = True
        self._offset = 0.0
        self._timer.start(16)  # ~60fps
        self.show()
        self.update()

    def stop(self):
        """Stop the loading animation."""
        self._timer.stop()
        self._visible = False
        self.hide()

    def _animate(self):
        self._offset += 0.03
        if self._offset > 1.0:
            self._offset = 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent):
        if not self._visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)

        w = self.width()
        h = self.height()

        # Gradient bar: a soft "beam" that sweeps across
        bar_width = int(w * 0.3)
        x_start = int(self._offset * w) - bar_width

        gradient = QLinearGradient(x_start, 0, x_start + bar_width, 0)
        gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 0))
        gradient.setColorAt(0.3, color)
        gradient.setColorAt(0.7, color)
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))

        painter.fillRect(x_start, 0, bar_width, h, gradient)


class _CoverSearchThread(QThread):
    """Background thread for cover search."""
    finished_covers = Signal(list)  # list of (label, cover_data)

    def __init__(self, artist, album):
        super().__init__()
        self.artist = artist
        self.album = album

    def run(self):
        covers = []
        seen_hashes = set()

        # iTunes
        itunes_covers = _search_itunes_covers_static(self.artist, self.album)
        for label, data in itunes_covers:
            h = hash(data)
            if h not in seen_hashes:
                seen_hashes.add(h)
                covers.append((label, data))

        # Deezer
        deezer_covers = _search_deezer_covers_static(self.artist, self.album)
        for label, data in deezer_covers:
            h = hash(data)
            if h not in seen_hashes:
                seen_hashes.add(h)
                covers.append((label, data))

        self.finished_covers.emit(covers[:6])


def _search_itunes_covers_static(artist, album):
    results = []
    query = urllib.request.quote(f"{artist} {album}".strip())
    url = f"https://itunes.apple.com/search?term={query}&media=music&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("results", []):
            if item.get("wrapperType") != "collection":
                continue
            art_url = item.get("artworkUrl100", "")
            if not art_url:
                continue
            art_url = art_url.replace("100x100", "600x600")
            title = item.get("collectionName", "")
            a_name = item.get("artistName", "")
            label = f"{a_name} — {title}" if title else a_name
            try:
                req_img = urllib.request.Request(art_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_img, timeout=5) as resp_img:
                    img_data = resp_img.read()
                results.append((label, img_data))
            except Exception:
                pass
    except Exception:
        pass
    return results


def _search_deezer_covers_static(artist, album):
    results = []
    query = urllib.request.quote(f"{artist} {album}".strip())
    url = f"https://api.deezer.com/search/album?q={query}&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("data", []):
            cover_url = item.get("cover_xl", "") or item.get("cover_big", "")
            if not cover_url:
                continue
            title = item.get("title", "")
            artist_name = item.get("artist", {}).get("name", "")
            label = f"{artist_name} — {title}" if title else artist_name
            try:
                req_img = urllib.request.Request(cover_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_img, timeout=5) as resp_img:
                    img_data = resp_img.read()
                results.append((label, img_data))
            except Exception:
                pass
    except Exception:
        pass
    return results


# Constants for generated cover
COVER_SIZE = 600
TEXT_PADDING = 30
FALLBACK_FONT_SIZE_ARTIST = 50 # Increased
FALLBACK_FONT_SIZE_TITLE = 60 # Increased
BRIGHT_COLORS = [
    (255, 99, 71),  # Tomato
    (255, 140, 0),  # DarkOrange
    (255, 215, 0),  # Gold
    (50, 205, 50),  # LimeGreen
    (60, 179, 113), # MediumAquaMarine
    (30, 144, 255), # DodgerBlue
    (106, 90, 205), # SlateBlue
    (147, 112, 219),# MediumPurple
    (255, 20, 147), # DeepPink
]

def _generate_abstract_cover(artist: str, title: str) -> bytes:
    """
    Generates an abstract cover art using a randomly selected background image
    from the 'res' folder, and colored text for artist and title.
    """
    # Base path to the res folder (assuming it's relative to the project root)
    # The current file is musicplayer/ui/tag_editor.py
    # Project root is D:\DEV\MusicPlayer2
    # So, res folder is D:\DEV\MusicPlayer2\res
    # Path(__file__).resolve().parent gives musicplayer/ui
    # Path(__file__).resolve().parent.parent gives musicplayer
    # Path(__file__).resolve().parent.parent.parent gives D:\DEV\MusicPlayer2
    # Determine the base path for resources, considering PyInstaller's _MEIPASS
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running from source (e.g., python main.py)
        # The current file is musicplayer/ui/tag_editor.py
        # Project root is D:\DEV\MusicPlayer2
        base_path = Path(__file__).resolve().parent.parent.parent

    res_folder_path = base_path / "res"
    
    background_images = [f"cover{i}.jpg" for i in range(1, 11)] # cover1.jpg to cover10.jpg
    
    selected_image_name = random.choice(background_images)
    background_image_path = res_folder_path / selected_image_name

    try:
        # Load the background image
        background_img = Image.open(background_image_path).convert('RGB')
        # Resize to COVER_SIZE, maintaining aspect ratio and cropping if necessary
        background_img = background_img.resize((COVER_SIZE, COVER_SIZE), Image.Resampling.LANCZOS)
        img = background_img
    except FileNotFoundError:
        # Fallback to black background if image not found
        print(f"Background image not found at {background_image_path}. Falling back to black.")
        img = Image.new('RGB', (COVER_SIZE, COVER_SIZE), (0, 0, 0))
    except Exception as e:
        # Generic error handling for image loading/processing
        print(f"Error loading background image {background_image_path}: {e}. Falling back to black.")
        img = Image.new('RGB', (COVER_SIZE, COVER_SIZE), (0, 0, 0))

    draw = ImageDraw.Draw(img)

    # Text rendering
    # Attempt to load a system font that supports Cyrillic
    try:
        # Common path for Arial on Windows
        arial_font_path = os.path.join(os.environ["WINDIR"], "Fonts", "arial.ttf")
        arial_bold_font_path = os.path.join(os.environ["WINDIR"], "Fonts", "arialbd.ttf") # Arial Bold
        
        try: # Try to load Arial Bold for artist
            font_artist = ImageFont.truetype(arial_bold_font_path, FALLBACK_FONT_SIZE_ARTIST)
        except IOError: # Fallback to regular Arial if bold not found
            font_artist = ImageFont.truetype(arial_font_path, FALLBACK_FONT_SIZE_ARTIST)
            
        font_title = ImageFont.truetype(arial_font_path, FALLBACK_FONT_SIZE_TITLE)
    except (IOError, KeyError): # KeyError for os.environ["WINDIR"] if not Windows
        # Fallback to default font if Arial not found or not on Windows
        font_artist = ImageFont.load_default(FALLBACK_FONT_SIZE_ARTIST)
        font_title = ImageFont.load_default(FALLBACK_FONT_SIZE_TITLE)

    text_color = (255, 255, 255) # White color for text
    shadow_color = (0, 0, 0)    # Black color for shadow
    shadow_offset = 3           # Offset for the shadow

    # Function to wrap text
    def wrap_text(text, font, max_width):
        lines = []
        if not text:
            return lines
        words = text.split()
        current_line = []
        for word in words:
            # Check if adding the word exceeds max_width
            test_line = " ".join(current_line + [word])
            # Use getlength for width calculation, bbox gives bounding box relative to (0,0)
            if draw.textlength(test_line, font=font) <= max_width:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    max_text_width = COVER_SIZE - 2 * TEXT_PADDING

    # Artist text (top half)
    artist_lines = wrap_text(artist, font_artist, max_text_width)
    
    if artist_lines:
        # Calculate total height of artist text
        total_artist_height = 0
        for line in artist_lines:
            total_artist_height += draw.textbbox((0,0), line, font=font_artist)[3] - draw.textbbox((0,0), line, font=font_artist)[1]
        total_artist_height += (len(artist_lines) - 1) * 5 # Line spacing

        y_text_artist = COVER_SIZE // 10 - total_artist_height // 2 # Moved higher
        y_text_artist = max(TEXT_PADDING, y_text_artist) # Ensure not too high

        for line in artist_lines:
            text_width = draw.textbbox((0, 0), line, font=font_artist)[2] - draw.textbbox((0, 0), line, font=font_artist)[0]
            x = (COVER_SIZE - text_width) // 2
            # Draw shadow
            draw.text((x + shadow_offset, y_text_artist + shadow_offset), line, font=font_artist, fill=shadow_color)
            # Draw main text
            draw.text((x, y_text_artist), line, font=font_artist, fill=text_color)
            y_text_artist += (draw.textbbox((0,0), line, font=font_artist)[3] - draw.textbbox((0,0), line, font=font_artist)[1]) + 5 # Line spacing


    # Title text (bottom half)
    title_lines = wrap_text(title, font_title, max_text_width)
    
    # New color definitions for title
    title_text_color = (20, 20, 20, 113)  # Black with 20% transparency
    title_shadow_color = (188, 188, 188, 152) # White shadow
    
    if title_lines:
        # Calculate total height of title text
        total_title_height = 0
        for line in title_lines:
            total_title_height += draw.textbbox((0,0), line, font=font_title)[3] - draw.textbbox((0,0), line, font=font_title)[1]
        total_title_height += (len(title_lines) - 1) * 5 # Line spacing

        y_text_title = COVER_SIZE // 7 * 6 - total_title_height // 2 # Moved lower
        y_text_title = max(COVER_SIZE // 2 + TEXT_PADDING, y_text_title) # Ensure not too high

        for line in title_lines:
            text_width = draw.textbbox((0, 0), line, font=font_title)[2] - draw.textbbox((0, 0), line, font=font_title)[0]
            x = (COVER_SIZE - text_width) // 2
            # Draw shadow
            draw.text((x + shadow_offset, y_text_title + shadow_offset), line, font=font_title, fill=title_shadow_color)
            # Draw main text
            draw.text((x, y_text_title), line, font=font_title, fill=title_text_color)
            y_text_title += (draw.textbbox((0,0), line, font=font_title)[3] - draw.textbbox((0,0), line, font=font_title)[1]) + 5 # Line spacing


    # Convert to bytes
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()


class _TrackSearchThread(QThread):
    """Background thread for track info search."""
    finished_tracks = Signal(list)  # list of track dicts

    def __init__(self, artist, title):
        super().__init__()
        self.artist = artist
        self.title = title

    def run(self):
        all_results = []
        all_results.extend(_search_itunes_tracks_static(self.artist, self.title))
        all_results.extend(_search_deezer_tracks_static(self.artist, self.title))
        self.finished_tracks.emit(all_results)


class _SaveTagsThread(QThread):
    """Background thread for saving tags to avoid blocking the UI."""
    finished = Signal(str)  # Emits new file path on success
    error = Signal(str)     # Emits error message on failure

    def __init__(self, file_path, new_filename_stem, title, artist, album, year, track, genres, cover_data):
        super().__init__()
        self.file_path = file_path
        self.new_filename_stem = new_filename_stem
        self.title = title
        self.artist = artist
        self.album = album
        self.year = year
        self.track = track
        self.genres = genres
        self.cover_data = cover_data

    def run(self):
        try:
            current_filepath = self.file_path
            old_path_obj = Path(current_filepath)

            # --- Handle renaming ---
            if self.new_filename_stem:
                new_filename = self.new_filename_stem + old_path_obj.suffix

                if new_filename.lower() != old_path_obj.name.lower():
                    new_path_str = str(old_path_obj.with_name(new_filename))
                    if os.path.exists(new_path_str) and os.path.normpath(new_path_str) != os.path.normpath(current_filepath):
                        self.error.emit(f"Файл «{new_filename}» уже существует!")
                        return
                    os.rename(current_filepath, new_path_str)
                    current_filepath = new_path_str

            # --- Save tags ---
            audio = MutagenFile(current_filepath, easy=False)
            if audio is None:
                raise ValueError("Не удалось загрузить файл для сохранения.")

            # MP3 specific saving
            if isinstance(audio, MP3):
                try:
                    tags = audio.tags or ID3()
                except ID3NoHeaderError:
                    tags = ID3()

                tags["TIT2"] = TIT2(text=self.title)
                tags["TPE1"] = TPE1(text=self.artist)
                tags["TALB"] = TALB(text=self.album)
                tags["TDRC"] = TDRC(text=self.year)
                tags["TRCK"] = TRCK(text=self.track)
                tags["TCON"] = TCON(text=";".join(self.genres))

                tags.delall("APIC")
                if self.cover_data:
                    mime = "image/jpeg"
                    if self.cover_data.startswith(b'\x89PNG'):
                        mime = "image/png"
                    tags["APIC"] = APIC(encoding=3, mime=mime, type=3, desc="Cover", data=self.cover_data)

                audio.tags = tags
                audio.save(v2_version=3)

            # FLAC specific saving
            elif isinstance(audio, FLAC):
                audio.delete()
                audio["title"] = self.title
                audio["artist"] = self.artist
                audio["album"] = self.album
                audio["date"] = self.year
                audio["tracknumber"] = self.track
                audio["genre"] = self.genres

                audio.clear_pictures()
                if self.cover_data:
                    pic = FlacPicture()
                    pic.data = self.cover_data
                    mime = "image/jpeg"
                    if self.cover_data.startswith(b'\x89PNG'):
                        mime = "image/png"
                    pic.mime = mime
                    pic.type = 3
                    pic.desc = "Cover"
                    audio.add_picture(pic)

                audio.save()

            else:
                self.error.emit("Сохранение тегов для этого формата файла не поддерживается.")
                return

            self.finished.emit(current_filepath)
        except Exception as e:
            self.error.emit(f"Не удалось сохранить теги:{e}")


def _search_itunes_tracks_static(artist, title):
    results = []
    params_parts = []
    if artist:
        params_parts.append(f"artistTerm={urllib.request.quote(artist)}")
    if title:
        params_parts.append(f"term={urllib.request.quote(title)}")
    params = "&".join(params_parts) + "&media=music&entity=song&limit=15"
    url = f"https://itunes.apple.com/search?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("results", []):
            item["trackId"] = item.get("trackId", hash(item.get("trackName", "")))
            item["source"] = "iTunes"
            results.append(item)
    except Exception:
        pass
    return results


def _search_deezer_tracks_static(artist, title):
    results = []
    query = urllib.request.quote(f"{artist} {title}".strip())
    url = f"https://api.deezer.com/search?q={query}&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("data", []):
            track_data = {
                "trackId": item.get("id", hash(item.get("title", ""))),
                "trackName": item.get("title", ""),
                "artistName": item.get("artist", {}).get("name", ""),
                "collectionName": item.get("album", {}).get("title", ""),
                "releaseDate": item.get("release_date", ""),
                "genres": [],
                "primaryGenreName": item.get("genre", ""),
                "trackTimeMillis": item.get("duration", 0) * 1000 if item.get("duration") else 0,
                "artworkUrl100": item.get("album", {}).get("cover_xl", "") or item.get("album", {}).get("cover_big", ""),
                "source": "Deezer",
            }
            results.append(track_data)
    except Exception:
        pass
    return results


# Standard genres
ID3_GENRES = [
    "Blues", "Classical", "Country", "Club", "Dance", "Disco", "Funk", "Grunge",
    "Hip-Hop", "Jazz", "Metal", "New Age", "Oldies", "Pop", "R&B",
    "Rap", "Reggae", "Rock", "Techno", "Trance", "Acapella",  "Alternative", "Ambient",
    "Bluegrass", "Bossa Nova", "Breakbeat", "Chillout", "Chorus",
    "Contemporary Christian", "Country Rock", "Drum & Bass", "Dubstep", "Death Metal",
    "Easy Listening", "Electronic", "Eurodance", "Folk", "Folk-Rock",
    "Gospel", "Gothic Rock", "Hard Rock", "Hardcore", "Heavy Metal",
    "House", "Indie", "Industrial", "Instrumental", "Jungle", "Lo-Fi", "Lounge",
    "New Wave", "Opera", "Orchestral", "Party", "Podcast", "Pop", "Post-Rock", "Post-Hardcore",
    "Pop Punk", "Pop Rock", "Power Pop", "Progressive Rock", "Psychedelic", "Punk", "Salsa",
    "Samba", "Singer-Songwriter", "Ska", "Ska-Punk", "Slow Rock", "Smooth Jazz",
    "Soundtrack", "Soul", "Synthwave", "Tango", "Thrash Metal",
    "Trance", "Trap", "Trip-Hop", "Vocal", "World Music"
]


class CoverDisplayLabel(QLabel):
    """
    QLabel that displays cover art and emits a signal on double click.
    It can track if the displayed cover was generated internally.
    """
    cover_double_clicked = Signal()
    _is_generated_cover: bool = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Нет обложки")
        self.setStyleSheet("""
            QLabel {
                background-color: #111111;
                border: 1px solid rgba(80, 80, 80, 0.5);
                color: #666666;
                font-size: 11px;
            }
        """)

    def setPixmap(self, pixmap: QPixmap):
        super().setPixmap(pixmap)
        if not pixmap.isNull():
            self.setText("") # Clear "Нет обложки" text
        else:
            self.setText("Нет обложки") # Show "Нет обложки" text

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.cover_double_clicked.emit()
            super().mouseDoubleClickEvent(event)


class TagEditorDialog(QDialog):
    """Frameless dialog for editing track ID3 tags."""

    def __init__(self, file_path, parent=None, update_player: bool = False):
        super().__init__(parent)
        self.file_path = file_path
        self.cover_data = None
        self.genre_tags = []
        self._update_player = update_player
        self._save_thread = None
        self.delete_confirmed = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(800, 500)
        self.setModal(True)

        self._drag_pos = QPoint()

        self._build_ui()
        self._load_tags()

    def paintEvent(self, event: QPaintEvent):
        """Draw semi-transparent accent border around the dialog."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)
        color.setAlpha(26)  # ~10% opacity

        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(rect)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # --- Container ---
        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: #000000; }")

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- Title bar ---
        title_bar = self._title_bar()
        inner.addWidget(title_bar)

        # --- Content ---
        content = self._content_widget()
        inner.addWidget(content, stretch=1)

        # --- Loading bar (hidden by default) ---
        self.loading_bar = LoadingBar()
        inner.addWidget(self.loading_bar)

        layout.addWidget(container)

    def _title_bar(self):
        """Create title bar matching settings dialog style."""
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        # SVG icon
        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        svg_data = get_music_note_svg(60).encode('utf-8')
        title_icon.renderer().load(QByteArray(svg_data))
        title_layout.addWidget(title_icon)

        # Title
        title_label = QLabel("Редактирование тегов")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        return title_bar

    def _content_widget(self):
        """Build the main content area."""
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(20)

        # Left column — cover art + actions
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # Cover art display
        self.cover_label = CoverDisplayLabel() # Используем наш новый класс
        self.cover_label.setFixedSize(200, 200) # Устанавливаем размер
        self.cover_label.cover_double_clicked.connect(self._on_cover_double_clicked) # Подключаем сигнал
        left_col.addWidget(self.cover_label)

        # Action buttons
        self.load_cover_btn = self._action_button("Загрузить обложку")
        self.load_cover_btn.clicked.connect(self._load_cover)
        left_col.addWidget(self.load_cover_btn)

        self.search_cover_btn = self._action_button("Поиск обложки")
        self.search_cover_btn.clicked.connect(self._search_cover)
        left_col.addWidget(self.search_cover_btn)

        self.search_track_btn = self._action_button("Поиск информации о треке")
        self.search_track_btn.clicked.connect(self._search_track_info)
        left_col.addWidget(self.search_track_btn)

        left_col.addStretch()
        layout.addLayout(left_col)

        # Right column — fields
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Title row with "From filename" button
        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        self.title_edit = self._text_input()
        title_row.addWidget(self.title_edit)
        self.title_from_fname_btn = self._action_button("Из имени файла", width=120)
        self.title_from_fname_btn.clicked.connect(self._apply_title_from_filename)
        title_row.addWidget(self.title_from_fname_btn)
        form.addRow("Название:", title_row)

        # Artist row with "From filename" button
        artist_row = QHBoxLayout()
        artist_row.setSpacing(0)
        self.artist_edit = self._text_input()
        artist_row.addWidget(self.artist_edit)
        self.artist_from_fname_btn = self._action_button("Из имени файла", width=120)
        self.artist_from_fname_btn.clicked.connect(self._apply_artist_from_filename)
        artist_row.addWidget(self.artist_from_fname_btn)
        form.addRow("Артист:", artist_row)

        # Connect textChanged signals to update button visibility
        self.title_edit.textChanged.connect(self._update_fname_buttons)
        self.artist_edit.textChanged.connect(self._update_fname_buttons)

        self.album_edit = self._text_input()
        form.addRow("Альбом:", self.album_edit)

        self.year_edit = self._text_input()
        form.addRow("Год:", self.year_edit)

        # Genre tags container
        genre_container = QWidget()
        genre_layout = QHBoxLayout(genre_container)
        genre_layout.setContentsMargins(0, 0, 0, 0)
        genre_layout.setSpacing(6)

        self.add_genre_btn = self._action_button("+ Добавить жанр", width=140)
        self.add_genre_btn.clicked.connect(self._show_genre_menu)
        genre_layout.addWidget(self.add_genre_btn)
        genre_layout.addStretch()
        form.addRow("Жанр:", genre_container)
        self.genre_layout = genre_layout
        self.genre_container = genre_container

        self.track_edit = self._text_input()
        form.addRow("Трек №:", self.track_edit)

        # Filename row
        fname_row = QHBoxLayout()
        fname_row.setSpacing(0)
        self.filename_edit = self._text_input()
        fname_row.addWidget(self.filename_edit)

        self.filename_from_tags_btn = self._action_button("Из тегов", width=100)
        self.filename_from_tags_btn.clicked.connect(self._apply_title_from_tags)
        fname_row.addWidget(self.filename_from_tags_btn)
        form.addRow("Имя файла:", fname_row)

        # File info badges
        badge_style = """
            QLabel {
                background-color: rgba(40, 40, 40, 0.8);
                color: #BBBBBB;
                border: 1px solid rgba(80, 80, 80, 0.5);
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }
        """
        self.bitrate_lbl = QLabel("—")
        self.bitrate_lbl.setStyleSheet(badge_style)
        self.bitrate_lbl.setFixedHeight(28)

        self.samplerate_lbl = QLabel("—")
        self.samplerate_lbl.setStyleSheet(badge_style)
        self.samplerate_lbl.setFixedHeight(28)

        self.size_lbl = QLabel("—")
        self.size_lbl.setStyleSheet(badge_style)
        self.size_lbl.setFixedHeight(28)

        self.duration_lbl = QLabel("—")
        self.duration_lbl.setStyleSheet(badge_style)
        self.duration_lbl.setFixedHeight(28)

        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge_row.addWidget(self.bitrate_lbl)
        badge_row.addWidget(self.samplerate_lbl)
        badge_row.addWidget(self.size_lbl)
        badge_row.addWidget(self.duration_lbl)
        right_col.addLayout(badge_row)

        right_col.addLayout(form)
        right_col.addStretch()

        # Bottom buttons
        btn_row = QHBoxLayout()
        self.delete_btn = self._destructive_button("Удалить")
        self.delete_btn.clicked.connect(self._prompt_delete_track)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()

        self.save_btn = self._primary_button("Сохранить")
        self.save_btn.clicked.connect(self._save_tags)
        btn_row.addWidget(self.save_btn)

        self.cancel_btn = self._secondary_button("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        right_col.addLayout(btn_row)
        layout.addLayout(right_col)

        return widget

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    # --- Helpers ---

    def _text_input(self):
        edit = QLineEdit()
        edit.setFixedHeight(32)
        edit.setMinimumWidth(350)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a1a;
                border: 1px solid rgba(80, 80, 80, 0.5);
                border-radius: 0;
                padding: 0 10px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: """ + cfg.get_accent_color() + """;
            }
        """)
        return edit

    def _action_button(self, text, width=None):
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        if width:
            btn.setFixedWidth(width)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 0.8);
                border: 1px solid rgba(80, 80, 80, 0.5);
                border-radius: 0;
                color: #FFFFFF;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 0.8);
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 30, 0.9);
            }
        """)
        return btn

    def _primary_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                border: none;
                border-radius: 0;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FFFFFF;
                color: {accent};
            }}
            QPushButton:pressed {{
                background-color: {accent};
                color: #FFFFFF;
            }}
        """)
        return btn

    def _secondary_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 0.8);
                border: 1px solid rgba(80, 80, 80, 0.5);
                border-radius: 0;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 0.8);
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 30, 0.9);
            }
        """)
        return btn

    def _destructive_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #501010;
                border: 1px solid #802020;
                border-radius: 0;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #801010;
                border-color: #A02020;
            }
            QPushButton:pressed {
                background-color: #A01010;
            }
        """)
        return btn

    def _prompt_delete_track(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Подтверждение удаления")
        msg_box.setIcon(QMessageBox.Warning)
        
        artist = self.artist_edit.text()
        title = self.title_edit.text()

        msg_box.setText(
            f"Вы уверены, что хотите удалить этот трек?<br><br>"
            f"<b>{artist} - {title}</b><br>"
            f"<span style='color: #888888; font-size: 11px;'>{self.file_path}</span><br><br>"
            f"Это действие <b>безвозвратно удалит</b> файл с диска."
        )
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        
        yes_button = msg_box.button(QMessageBox.Yes)
        yes_button.setText("Удалить")

        if msg_box.exec() == QMessageBox.Yes:
            self._delete_and_close()

    def _delete_and_close(self):
        self.delete_confirmed = True
        self.accept()

    # --- Genre tags ---

    def _show_genre_menu(self):
        """Show genre selection popup."""
        available = [g for g in ID3_GENRES if g not in self.genre_tags]
        if not available:
            QMessageBox.information(self, "Информация", "Все жанры уже добавлены!")
            return

        popup = QWidget(None)
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_DeleteOnClose)
        popup.setStyleSheet("QWidget { background: #1a1a1a; border: 1px solid rgba(80,80,80,0.5); }")

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(350)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) # Changed from AlwaysOff
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #000;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(80,80,80,0.5);
                min-height: 30px;
                border-radius: 2px; /* Adjusted to half of new width */
            }
            QScrollBar:horizontal {
                background: #000;
                height: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(80,80,80,0.5);
                min-width: 30px;
                border-radius: 2px; /* Adjusted to half of new height */
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        for genre in available:
            lbl = QLabel(f"  {genre}")
            lbl.setFixedHeight(26)
            lbl.setStyleSheet("""
                QLabel { color: #FFFFFF; font-size: 12px; padding: 0 8px; }
                QLabel:hover { background: rgba(80, 80, 80, 0.5); color: """ + cfg.get_accent_color() + """; }
            """)
            lbl.setAttribute(Qt.WA_Hover)
            lbl.mouseReleaseEvent = lambda event, g=genre: self._on_genre_select(g, popup)
            c_layout.addWidget(lbl)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        popup.setMinimumWidth(220)

        # Position near add genre button
        btn_pos = self.add_genre_btn.mapToGlobal(self.add_genre_btn.rect().bottomLeft())
        popup.move(btn_pos)
        popup.show()

    def _on_genre_select(self, genre, popup):
        self.genre_tags.append(genre)
        self._refresh_genre_tags()
        popup.close()

    def _remove_genre_tag(self, tag):
        if tag in self.genre_tags:
            self.genre_tags.remove(tag)
            self._refresh_genre_tags()

    def _refresh_genre_tags(self):
        # Remove all genre label widgets (keep add_genre_btn)
        for i in reversed(range(self.genre_layout.count())):
            widget = self.genre_layout.itemAt(i).widget()
            if widget and widget != self.add_genre_btn:
                widget.deleteLater()

        # Recreate genre labels before the add button
        accent = cfg.get_accent_color()
        for tag in self.genre_tags:
            btn = QPushButton(f"✕ {tag}")
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1a1a1a;
                    border: 1px solid {accent};
                    border-radius: 0;
                    padding: 0 8px;
                    font-size: 11px;
                    color: {accent};
                }}
                QPushButton:hover {{
                    background-color: #252525;
                }}
            """)
            btn.clicked.connect(lambda checked=False, t=tag: self._remove_genre_tag(t))
            self.genre_layout.insertWidget(self.genre_layout.count() - 1, btn)

    # --- Load tags ---

    def _load_tags(self):
        self.genre_tags = []
        self.bitrate_lbl.setText("—")
        self.samplerate_lbl.setText("—")
        self.size_lbl.setText("—")
        self.duration_lbl.setText("—")

        try:
            audio = MutagenFile(self.file_path, easy=False)
            if audio is None:
                raise ValueError("Неподдерживаемый формат файла")

            # --- Get file info ---
            if hasattr(audio, 'info'):
                info = audio.info
                if hasattr(info, 'bitrate') and info.bitrate:
                    self.bitrate_lbl.setText(f"{info.bitrate // 1000}kb")
                if hasattr(info, 'sample_rate') and info.sample_rate:
                    self.samplerate_lbl.setText(f"{info.sample_rate / 1000:.0f}khz")
                if hasattr(info, 'length') and info.length:
                    mins, secs = divmod(int(info.length), 60)
                    self.duration_lbl.setText(f"{mins}:{secs:02d}")
            
            try:
                size_bytes = os.path.getsize(self.file_path)
                if size_bytes < 1024 * 1024:
                    self.size_lbl.setText(f"{size_bytes / 1024:.0f}KB")
                else:
                    self.size_lbl.setText(f"{size_bytes / (1024 * 1024):.1f}MB")
            except Exception:
                pass


            # --- Get tags ---
            if isinstance(audio, MP3):
                self.title_edit.setText(str(audio.tags.get("TIT2", "")))
                self.artist_edit.setText(str(audio.tags.get("TPE1", "")))
                self.album_edit.setText(str(audio.tags.get("TALB", "")))
                self.year_edit.setText(str(audio.tags.get("TDRC", "")))
                self.track_edit.setText(str(audio.tags.get("TRCK", "")))
                tcon = audio.tags.get("TCON")
                if tcon:
                    genre_str = str(tcon)
                    genre_str = re.sub(r'\(\d+\)', '', genre_str).strip()
                    self.genre_tags = [g.strip() for g in genre_str.split(';') if g.strip()]
                
                # Cover
                for key in audio.tags.keys():
                    if key.startswith("APIC:"):
                        self.cover_data = audio.tags[key].data
                        break

            elif isinstance(audio, FLAC):
                tags = audio.tags
                if tags:
                    self.title_edit.setText(tags.get("title", [""])[0])
                    self.artist_edit.setText(tags.get("artist", [""])[0])
                    self.album_edit.setText(tags.get("album", [""])[0])
                    self.year_edit.setText(tags.get("date", [""])[0])
                    self.track_edit.setText(tags.get("tracknumber", [""])[0])
                    self.genre_tags = tags.get("genre", [])

                # Cover
                if audio.pictures:
                    self.cover_data = audio.pictures[0].data
        
        except Exception as e:
            # Fallback for untagged files or read errors
            pass

        # --- Display Cover ---
        if self.cover_data:
            # When loading from file, it's not a generated cover
            self._apply_cover_data(self.cover_data, is_generated=False)

        self._refresh_genre_tags()

        # --- Filename ---
        self.filename_edit.setText(Path(self.file_path).stem)
        self._update_fname_buttons()

    # --- Filename from tags ---

    def _apply_title_from_tags(self):
        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        if artist or title:
            name = f"{artist} - {title}" if artist and title else (artist or title)
            name = name.replace('/', '+')
            self.filename_edit.setText(name)
        else:
            QMessageBox.information(self, "Информация", "Теги названия и артиста пусты!")

    # --- Tags from filename ---

    def _parse_filename(self):
        """Parse filename in 'Artist - Title' format."""
        basename = os.path.basename(self.file_path)
        name = Path(basename).stem  # Remove extension

        # Split on ' - ' or ' – ' (em-dash)
        for sep in [' - ', ' \u2013 ']:
            if sep in name:
                parts = name.split(sep, 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                if artist and title:
                    return artist, title

        # If no separator found, return filename stem as title
        return '', name

    def _apply_title_from_filename(self):
        """Fill title field from filename."""
        artist, title = self._parse_filename()
        if title:
            self.title_edit.setText(title)
        if artist:
            self.artist_edit.setText(artist)
        self._update_fname_buttons()

    def _apply_artist_from_filename(self):
        """Fill artist field from filename."""
        artist, title = self._parse_filename()
        if artist:
            self.artist_edit.setText(artist)
        if title:
            self.title_edit.setText(title)
        self._update_fname_buttons()

    def _update_fname_buttons(self):
        """Show/hide 'From filename' buttons based on field contents."""
        title_empty = not self.title_edit.text().strip()
        artist_empty = not self.artist_edit.text().strip()

        # Show button when its field OR the other field is empty
        self.title_from_fname_btn.setVisible(title_empty or artist_empty)
        self.artist_from_fname_btn.setVisible(title_empty or artist_empty)

    # --- Cover search ---

    def _fill_fields_from_filename(self):
        """If artist or title fields are empty, try to fill them from filename."""
        title_empty = not self.title_edit.text().strip()
        artist_empty = not self.artist_edit.text().strip()
        if title_empty or artist_empty:
            artist, title = self._parse_filename()
            if artist and artist_empty:
                self.artist_edit.setText(artist)
            if title and title_empty:
                self.title_edit.setText(title)

    def _search_cover(self):
        # Try to fill empty fields from filename before searching
        self._fill_fields_from_filename()

        artist = self.artist_edit.text().strip()
        album = self.album_edit.text().strip()

        if not artist and not album:
            QMessageBox.information(self, "Информация", "Заполните поля Артист и/или Альбом для поиска!")
            return

        # Show loading animation
        self.loading_bar.start()

        # Run search in background thread
        from PySide6.QtCore import QThread
        self._cover_search_thread = _CoverSearchThread(artist, album)
        self._cover_search_thread.finished_covers.connect(self._on_cover_search_done)
        self._cover_search_thread.start()

    def _on_cover_search_done(self, covers):
        """Called from background thread when cover search completes."""
        self.loading_bar.stop()

        if not covers:
            QMessageBox.information(self, "Результат", "Обложка не найдена.")
            return

        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        dialog = CoverSearchResultsDialog(covers, self, artist=artist, title=title)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_cover:
            self._apply_cover_data(dialog.selected_cover, is_generated=False)

    def _apply_cover_data(self, cover_data: bytes, is_generated: bool = False):
        """Set cover from bytes and update display.
        'is_generated' indicates if the cover was created by abstract generation.
        """
        self.cover_data = cover_data
        self.cover_label._is_generated_cover = is_generated
        pixmap = QPixmap()
        pixmap.loadFromData(self.cover_data)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                200, 200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled)
            self.cover_label.setText("")

    # --- Cover upload ---

    def _load_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите обложку", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            with open(path, "rb") as f:
                cover_data_from_file = f.read()
            self._apply_cover_data(cover_data_from_file, is_generated=False)

    # --- Track info search ---

    def _find_best_match(self, results, artist, title):
        def normalize(s):
            return re.sub(r'[^\w\s]', '', s.lower().strip())

        norm_artist = normalize(artist) if artist else ""
        norm_title = normalize(title) if title else ""

        scored = []
        for r in results:
            score = 0
            r_artist = normalize(r.get("artistName", ""))
            r_title = normalize(r.get("trackName", ""))

            has_artist_match = False
            has_title_match = False

            if norm_artist and r_artist:
                if norm_artist == r_artist:
                    score += 100
                    has_artist_match = True
                elif norm_artist in r_artist or r_artist in norm_artist:
                    score += 50
                    has_artist_match = True

            if norm_title and r_title:
                if norm_title == r_title:
                    score += 100
                    has_title_match = True
                elif norm_title in r_title or r_title in norm_title:
                    score += 50
                    has_title_match = True

            if has_artist_match and has_title_match:
                score += 20

            if norm_artist and norm_title and not has_artist_match:
                continue

            if score > 0:
                scored.append((score, r))

        if not scored:
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        scored = [(s, r) for s, r in scored if s >= 50]

        seen_ids = set()
        unique = []
        for s, r in scored:
            tid = r.get("trackId")
            if tid not in seen_ids:
                seen_ids.add(tid)
                unique.append((s, r))

        return unique[:6]

    def _search_track_info(self):
        # Try to fill empty fields from filename before searching
        self._fill_fields_from_filename()

        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()

        if not artist and not title:
            QMessageBox.information(self, "Информация", "Заполните хотя бы одно поле: Артист или Название!")
            return

        # Show loading animation
        self.loading_bar.start()

        # Run search in background thread
        self._track_search_thread = _TrackSearchThread(artist, title)
        self._track_search_thread.finished_tracks.connect(self._on_track_search_done)
        self._track_search_thread.start()

    def _on_track_search_done(self, all_results):
        """Called from background thread when track search completes."""
        self.loading_bar.stop()

        if not all_results:
            QMessageBox.information(self, "Результат", "Информация о треке не найдена.")
            return

        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        duration = self.duration_lbl.text() if self.duration_lbl.text() != "—" else ""
        matches = self._find_best_match(all_results, artist, title)
        if not matches:
            matches = [(0, r) for r in all_results[:6]]

        dialog = TrackSearchResultsDialog(matches, self, artist=artist, title=title, duration=duration)
        result = dialog.exec()

        if result != QDialog.DialogCode.Accepted or dialog.selected_track is None:
            return

        best_match = dialog.selected_track
        self._apply_track_search_result(best_match)

    def _apply_track_search_result(self, track):
        """Apply search result to tag editor fields."""
        self.title_edit.setText(track.get("trackName", ""))
        self.artist_edit.setText(track.get("artistName", ""))
        self.album_edit.setText(track.get("collectionName", ""))

        new_genres = track.get("genres", [])
        if not new_genres:
            primary_genre = track.get("primaryGenreName", "")
            if primary_genre:
                new_genres = [primary_genre]

        if new_genres:
            if len(self.genre_tags) == 1 and self.genre_tags[0] == "Other":
                self.genre_tags.clear()

            added = False
            for g in new_genres:
                if g and g not in self.genre_tags:
                    self.genre_tags.append(g)
                    added = True
            if added:
                self._refresh_genre_tags()

        release_date = track.get("releaseDate", "")
        if release_date:
            self.year_edit.setText(release_date[:4])

        # Load cover art
        art_url = track.get("artworkUrl100", "")
        if art_url:
            art_url = art_url.replace("100x100", "600x600")
            try:
                req_img = urllib.request.Request(art_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_img, timeout=10) as resp_img:
                    cover_data_from_search = resp_img.read()
                self._apply_cover_data(cover_data_from_search, is_generated=False)
            except Exception:
                pass

    # --- Save tags ---

    def _save_tags(self):
        if self._save_thread and self._save_thread.isRunning():
            return

        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.loading_bar.start()

        self._save_thread = _SaveTagsThread(
            file_path=self.file_path,
            new_filename_stem=self.filename_edit.text().strip(),
            title=self.title_edit.text(),
            artist=self.artist_edit.text(),
            album=self.album_edit.text(),
            year=self.year_edit.text(),
            track=self.track_edit.text(),
            genres=self.genre_tags,
            cover_data=self.cover_data
        )

        self._save_thread.finished.connect(self._on_save_finished)
        self._save_thread.error.connect(self._on_save_error)
        self._save_thread.start()

    def _on_save_finished(self, new_filepath):
        self.loading_bar.stop()
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.file_path = new_filepath
        self.accept()

    def _on_save_error(self, message):
        self.loading_bar.stop()
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", message)

    def _on_cover_double_clicked(self):
        """Handle double-click on cover area. Generate abstract cover if applicable."""
        # Only generate if there's no cover, or if the current cover is a generated one
        if self.cover_data is None or self.cover_label._is_generated_cover:
            artist = self.artist_edit.text().strip()
            title = self.title_edit.text().strip()

            if not artist and not title:
                QMessageBox.information(self, "Генерация обложки", "Для генерации обложки заполните поля 'Артист' и/или 'Название'.")
                return

            generated_cover_data = _generate_abstract_cover(artist, title)
            self._apply_cover_data(generated_cover_data, is_generated=True)
        else:
            # If there's an existing non-generated cover, do nothing.
            # We could add a message here, but the user's request implies
            # only repeated generation for unsaved generated covers.
            pass
        # QMessageBox.information(self, "Генерация обложки", "Абстрактная обложка сгенерирована. Не забудьте сохранить изменения!") # Removed notification


# --- Search Results Dialog ---

class TrackSearchResultsDialog(QDialog):
    """Frameless dialog showing search results with confirmation."""

    def __init__(self, track_results, parent=None, artist="", title="", duration=""):
        super().__init__(parent)
        self.track_results = track_results
        self.selected_track = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(760, 710)
        self.setModal(True)

        self._drag_pos = QPoint()
        self._artist = artist
        self._title = title
        self._duration = duration
        self._build_ui()

    def paintEvent(self, event: QPaintEvent):
        """Draw semi-transparent accent border around the dialog."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)
        color.setAlpha(26)  # ~10% opacity

        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(rect)

    def showEvent(self, event):
        super().showEvent(event)
        # Offset position by 50px down from center
        if self.parent():
            parent_center = self.parent().geometry().center()
            self_rect = self.rect()
            new_x = parent_center.x() - self_rect.width() // 2
            new_y = parent_center.y() - self_rect.height() // 2 + 50
            self.move(new_x, new_y)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # --- container ---
        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: #000000; }")

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- title bar ---
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        svg_data = get_music_note_svg(60).encode('utf-8')
        title_icon.renderer().load(QByteArray(svg_data))
        title_layout.addWidget(title_icon)

        title_text = "Результаты поиска"
        if self._artist or self._title or self._duration:
            title_text = f"Результаты поиска для: {self._artist} - {self._title}"
            if self._duration:
                title_text += f" ♪ {self._duration}"
        title_label = QLabel(title_text)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        inner.addWidget(title_bar)

        # --- content ---
        content = QWidget()
        content.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
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
        """)

        card_container = QWidget()
        card_layout = QVBoxLayout(card_container)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(8)

        for score, track_data in self.track_results:
            card = self._build_card(track_data, score, self._artist, self._title, self._duration)
            card_layout.addWidget(card)

        card_layout.addStretch()
        scroll.setWidget(card_container)
        content_layout.addWidget(scroll)

        inner.addWidget(content, stretch=1)
        layout.addWidget(container)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _build_card(self, track_data, score, original_artist, original_title, original_duration):
        card = QFrame()
        accent = cfg.get_accent_color()

        # --- Get data and compare ---
        track_name = track_data.get("trackName", "—")
        artist_name = track_data.get("artistName", "—")
        duration_ms = track_data.get("trackTimeMillis", 0)
        
        # Format API duration to M:SS
        api_duration = f"{duration_ms // 60000}:{duration_ms % 60000 // 1000:02d}" if duration_ms else ""

        is_artist_match = original_artist.strip().lower() == artist_name.strip().lower()
        is_title_match = original_title.strip().lower() == track_name.strip().lower()
        is_duration_match = original_duration == api_duration if (original_duration and api_duration) else False

        is_perfect_match = is_artist_match and is_title_match
        is_full_match = is_perfect_match and is_duration_match

        # --- Set styles based on match level ---
        card_border_style = "border: 1px solid rgba(80, 80, 80, 0.5);" # Always normal border
        title_color_style = f"color: {accent};" if is_perfect_match else "color: #FFFFFF;"

        card.setStyleSheet(f"""
            QFrame {{
                background-color: #111111;
                {card_border_style}
                padding: 10px;
            }}
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(12)

        COVER_SIZE = 120
        cover_label = QLabel()
        cover_label.setFixedSize(COVER_SIZE, COVER_SIZE)
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #666666;
                font-size: 11px;
            }
        """)

        art_url = track_data.get("artworkUrl100", "").replace("100x100", "300x300")
        if art_url:
            try:
                req = urllib.request.Request(art_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    img_data = resp.read()
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        COVER_SIZE, COVER_SIZE,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    cover_label.setPixmap(scaled)
                    cover_label.setText("")
            except Exception:
                cover_label.setText("🎵")
        else:
            cover_label.setText("🎵")

        pick_btn = QPushButton("✓ Подходит")
        pick_btn.setFixedWidth(COVER_SIZE)
        pick_btn.setFixedHeight(28)
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #FFFFFF;
                border: none;
                border-radius: 0;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #FFFFFF;
                color: {accent};
            }}
        """)
        pick_btn.clicked.connect(lambda checked=False, td=track_data: self._select_track(td))

        left_col = QVBoxLayout()
        left_col.setSpacing(0)
        left_col.setAlignment(Qt.AlignTop)
        left_col.addWidget(cover_label)
        left_col.addWidget(pick_btn)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(0, 2, 0, 2)

        collection = track_data.get("collectionName", "—")
        release = track_data.get("releaseDate", "")
        year = release[:4] if release else ""
        genres = track_data.get("genres", [])
        if not genres:
            primary = track_data.get("primaryGenreName", "")
            if primary:
                genres = [primary]

        title_artist = f"{artist_name} — {track_name}"
        name_lbl = QLabel(f"<b>{title_artist}</b>")
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"{title_color_style} font-size: 13px;")
        info_layout.addWidget(name_lbl)

        if collection and collection != "—":
            album_lbl = QLabel(f"Альбом: {collection}")
            album_lbl.setStyleSheet("color: #AAAAAA; font-size: 12px;")
            info_layout.addWidget(album_lbl)

        meta_parts = []
        if year:
            meta_parts.append(year)
        if api_duration:
            meta_parts.append(api_duration)
        genre_str = ", ".join(genres) if genres else ""
        if genre_str:
            meta_parts.append(genre_str)

        if meta_parts:
            meta_lbl = QLabel("  •  ".join(meta_parts))
            meta_lbl.setStyleSheet("color: #888888; font-size: 12px;")
            meta_lbl.setWordWrap(True)
            info_layout.addWidget(meta_lbl)

        # Source badge + score
        source = track_data.get("source", "")
        source_color = "#888888"
        if source == "iTunes":
            source_color = "#d563a1"
        elif source == "Deezer":
            source_color = "#1EC65E"

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        if source:
            source_lbl = QLabel(source)
            source_lbl.setStyleSheet(f"color: {source_color}; font-size: 10px; font-weight: bold;")
            bottom_row.addWidget(source_lbl)

        bottom_row.addStretch()

        score_label_color = "#FFFFFF" if is_full_match else "#666666"
        score_label = QLabel(f"Совпадение: {score}")
        score_label.setStyleSheet(f"color: {score_label_color}; font-size: 11px;")
        bottom_row.addWidget(score_label)

        info_layout.addLayout(bottom_row)

        card_layout.addLayout(left_col)
        card_layout.addLayout(info_layout)

        return card

    def _select_track(self, track_data):
        self.selected_track = track_data
        self.accept()


class CoverTile(QWidget):
    """A single cover tile with hover overlay and click-to-select."""

    selected = Signal(bytes)

    def __init__(self, label: str, cover_data: bytes, parent=None):
        super().__init__(parent)
        self.label = label
        self.cover_data = cover_data
        self.TILE_SIZE = 200
        self._hovered = False
        self.setFixedSize(self.TILE_SIZE, self.TILE_SIZE)
        self.setCursor(Qt.PointingHandCursor)

        # Load pixmap
        self._pixmap = QPixmap()
        self._pixmap.loadFromData(cover_data)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.cover_data)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw cover image
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.TILE_SIZE, self.TILE_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            # Center the image
            x = (self.TILE_SIZE - scaled.width()) // 2
            y = (self.TILE_SIZE - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(0, 0, self.TILE_SIZE, self.TILE_SIZE, QColor("#1a1a1a"))
            painter.setPen(QColor("#666666"))
            font = painter.font()
            font.setPointSize(24)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "🎵")

        if self._hovered:
            # Draw accent checkmark in center
            accent = cfg.get_accent_color()
            painter.setPen(QColor(accent))
            font = painter.font()
            font.setPointSize(48)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "✓")
        else:
            # Draw semi-transparent overlay with label text
            painter.fillRect(0, 0, self.TILE_SIZE, self.TILE_SIZE, QColor(0, 0, 0, 180))
            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)

            # Word-wrap the label text
            from PySide6.QtGui import QTextOption
            text_rect = self.rect().adjusted(8, 8, -8, -8)
            painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignCenter, self.label)


class CoverSearchResultsDialog(QDialog):
    """Frameless dialog showing cover art search results in a 3-column grid."""

    def __init__(self, covers, parent=None, artist="", title=""):
        super().__init__(parent)
        self.covers = covers
        self.selected_cover = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 3 cols × 200px + gaps + margins ≈ 700px, 2 rows × 200px + gaps + margins + titlebar ≈ 480px
        self.setFixedSize(700, 500)
        self.setModal(True)

        self._drag_pos = QPoint()
        self._artist = artist
        self._title = title
        self._build_ui()

    def paintEvent(self, event: QPaintEvent):
        """Draw semi-transparent accent border around the dialog."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        accent = cfg.get_accent_color()
        color = QColor(accent)
        color.setAlpha(26)  # ~10% opacity

        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRect(rect)

    def showEvent(self, event):
        super().showEvent(event)
        # Offset position by 50px down from center
        if self.parent():
            parent_center = self.parent().geometry().center()
            self_rect = self.rect()
            new_x = parent_center.x() - self_rect.width() // 2
            new_y = parent_center.y() - self_rect.height() // 2 + 50
            self.move(new_x, new_y)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: #000000; }")

        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # --- title bar with icon and title ---
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #000000;")

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(10)

        # App icon
        title_icon = QSvgWidget()
        title_icon.setFixedSize(20, 20)
        svg_data = get_music_note_svg(60).encode('utf-8')
        title_icon.renderer().load(QByteArray(svg_data))
        title_layout.addWidget(title_icon)

        # Title
        title_text = "Выбор обложки трека"
        if self._artist or self._title:
            title_text = f"Выбор обложки для: {self._artist} - {self._title}"
        title_label = QLabel(title_text)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        accent = cfg.get_accent_color()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: #555555;
            }}
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        inner.addWidget(title_bar)

        # --- grid of cover tiles (3 columns, no scroll) ---
        content = QWidget()
        content.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(0)

        card_container = QWidget()
        card_container.setStyleSheet("background-color: #000000;")
        card_layout = QGridLayout(card_container)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignCenter)

        COLS = 3
        for i, (label, cover_data) in enumerate(self.covers):
            row = i // COLS
            col = i % COLS
            tile = CoverTile(label, cover_data)
            tile.selected.connect(self._select_cover)
            card_layout.addWidget(tile, row, col)

        card_layout.setRowStretch((len(self.covers) + COLS - 1) // COLS, 1)
        content_layout.addWidget(card_container)

        inner.addWidget(content, stretch=1)
        layout.addWidget(container)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _select_cover(self, cover_data: bytes):
        self.selected_cover = cover_data
        self.accept()

