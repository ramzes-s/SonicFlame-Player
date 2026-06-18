import os
import sys
import random
import io
import platform as _platform
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .constants import COVER_SIZE, TEXT_PADDING, FALLBACK_FONT_SIZE_ARTIST, FALLBACK_FONT_SIZE_TITLE


def _get_font(bold_name, regular_name, size_bold, size_regular):
    system = _platform.system()
    if system == "Windows":
        windir = os.environ.get("WINDIR", "C:\\Windows")
        base = os.path.join(windir, "Fonts")
        candidates = [
            (os.path.join(base, bold_name), os.path.join(base, regular_name)),
        ]
    elif system == "Darwin":
        candidates = [
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"),
            ("/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial.ttf"),
        ]
    else:
        candidates = [
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"),
        ]

    for bold_path, regular_path in candidates:
        if os.path.exists(bold_path):
            font_artist = ImageFont.truetype(bold_path, size_bold)
            font_title = ImageFont.truetype(regular_path if os.path.exists(regular_path) else bold_path, size_regular)
            return font_artist, font_title
    raise IOError("No suitable font found")


def _generate_abstract_cover(artist: str, title: str) -> bytes:
    """Generates an abstract cover art."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent.parent.parent.parent

    res_folder_path = base_path / "res" / "covers"
    background_images = [f"{i}.jpg" for i in range(1, 15)]
    selected_image_name = random.choice(background_images)
    background_image_path = res_folder_path / selected_image_name

    try:
        background_img = Image.open(background_image_path).convert('RGBA')
        background_img = background_img.resize((COVER_SIZE, COVER_SIZE), Image.Resampling.LANCZOS)
        img = background_img
    except FileNotFoundError:
        img = Image.new('RGBA', (COVER_SIZE, COVER_SIZE), (0, 0, 0, 255))
    except Exception as e:
        print(f"_generate_abstract_cover: failed to open background image: {e}")
        img = Image.new('RGBA', (COVER_SIZE, COVER_SIZE), (0, 0, 0, 255))

    draw = ImageDraw.Draw(img)

    try:
        font_artist, font_title = _get_font("arialbd.ttf", "arial.ttf",
                                             FALLBACK_FONT_SIZE_ARTIST, FALLBACK_FONT_SIZE_TITLE)
    except (IOError, KeyError):
        font_artist = ImageFont.load_default()
        font_title = ImageFont.load_default()

    text_color = (255, 255, 255, 255)
    shadow_color = (0, 0, 0, 255)
    shadow_offset = 3

    def wrap_text(text, font, max_width):
        lines = []
        if not text:
            return lines
        words = text.split()
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            if draw.textlength(test_line, font=font) <= max_width:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    max_text_width = COVER_SIZE - 2 * TEXT_PADDING
    artist_lines = wrap_text(artist, font_artist, max_text_width)

    if artist_lines:
        artist_bboxes = [draw.textbbox((0, 0), line, font=font_artist) for line in artist_lines]
        total_artist_height = sum(bbox[3] - bbox[1] for bbox in artist_bboxes) + (len(artist_lines) - 1) * 5

        y_text_artist = COVER_SIZE // 10 - total_artist_height // 2
        y_text_artist = max(TEXT_PADDING, y_text_artist)

        for bbox, line in zip(artist_bboxes, artist_lines):
            text_width = bbox[2] - bbox[0]
            x = (COVER_SIZE - text_width) // 2
            draw.text((x + shadow_offset, y_text_artist + shadow_offset), line, font=font_artist, fill=shadow_color)
            draw.text((x, y_text_artist), line, font=font_artist, fill=text_color)
            y_text_artist += bbox[3] - bbox[1] + 5

    title_lines = wrap_text(title, font_title, max_text_width)
    title_text_color = (20, 20, 20, 113)
    title_shadow_color = (188, 188, 188, 152)

    if title_lines:
        title_bboxes = [draw.textbbox((0, 0), line, font=font_title) for line in title_lines]
        total_title_height = sum(bbox[3] - bbox[1] for bbox in title_bboxes) + (len(title_lines) - 1) * 5

        y_text_title = COVER_SIZE // 7 * 6 - total_title_height // 2
        y_text_title = max(COVER_SIZE // 2 + TEXT_PADDING, y_text_title)

        for bbox, line in zip(title_bboxes, title_lines):
            text_width = bbox[2] - bbox[0]
            x = (COVER_SIZE - text_width) // 2
            draw.text((x + shadow_offset, y_text_title + shadow_offset), line, font=font_title, fill=title_shadow_color)
            draw.text((x, y_text_title), line, font=font_title, fill=title_text_color)
            y_text_title += bbox[3] - bbox[1] + 5

    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()