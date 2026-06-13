import gc
import logging
import os
import urllib.request
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture as FlacPicture
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from .api import _search_itunes_tracks_static, _search_deezer_tracks_static

logger = logging.getLogger(__name__)


class _TrackSearchThread(QThread):
    finished_tracks = Signal(list)

    def __init__(self, artist, title):
        super().__init__()
        self.artist = artist
        self.title = title

    def run(self):
        all_results = []
        all_results.extend(_search_itunes_tracks_static(self.artist, self.title))
        all_results.extend(_search_deezer_tracks_static(self.artist, self.title))
        self.finished_tracks.emit(all_results)


class _CoverDownloadThread(QThread):
    finished_cover = Signal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            self.finished_cover.emit(data)
        except Exception:
            pass


class _SaveTagsThread(QThread):
    save_finished = Signal(str)
    error = Signal(str)

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
        current_filepath = self.file_path
        old_path_obj = Path(current_filepath)
        format_name = old_path_obj.suffix.lower()

        logger.info("=== SAVE START — %s ===", current_filepath)
        logger.debug("  title=%r, artist=%r, album=%r, year=%r, track=%r, genres=%r, cover=%d bytes, rename=%r",
                     self.title, self.artist, self.album, self.year, self.track,
                     self.genres, len(self.cover_data) if self.cover_data else 0,
                     self.new_filename_stem)

        try:
            audio = MutagenFile(current_filepath, easy=False)
            if audio is None:
                logger.error("MutagenFile returned None for %s", current_filepath)
                raise ValueError("Не удалось загрузить файл для сохранения.")

            if isinstance(audio, MP3):
                logger.debug("Format: MP3 — writing tags")
                tags = audio.tags
                if tags is None:
                    try:
                        tags = ID3()
                    except ID3NoHeaderError:
                        tags = ID3()
                if self.title:
                    tags["TIT2"] = TIT2(text=self.title)
                if self.artist:
                    tags["TPE1"] = TPE1(text=self.artist)
                if self.album:
                    tags["TALB"] = TALB(text=self.album)
                if self.year:
                    tags["TDRC"] = TDRC(text=self.year)
                if self.track:
                    tags["TRCK"] = TRCK(text=self.track)
                if self.genres:
                    tags["TCON"] = TCON(text=";".join(self.genres))

                tags.delall("APIC")
                if self.cover_data:
                    mime = "image/jpeg"
                    if self.cover_data.startswith(b'\x89PNG'):
                        mime = "image/png"
                    tags["APIC"] = APIC(encoding=3, mime=mime, type=3, desc="Cover", data=self.cover_data)

                audio.tags = tags
                logger.debug("MP3: calling audio.save()")
                audio.save()
                logger.debug("MP3: save OK")

            elif isinstance(audio, FLAC):
                logger.debug("Format: FLAC — writing tags")
                audio.delete()
                if self.title:
                    audio["title"] = self.title
                if self.artist:
                    audio["artist"] = self.artist
                if self.album:
                    audio["album"] = self.album
                if self.year:
                    audio["date"] = self.year
                if self.track:
                    audio["tracknumber"] = self.track
                if self.genres:
                    audio["genre"] = ";".join(self.genres)

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

                logger.debug("FLAC: calling audio.save()")
                audio.save()
                logger.debug("FLAC: save OK")

            elif isinstance(audio, MP4):
                logger.debug("Format: MP4/M4A — writing tags")
                if self.title:
                    audio["\xa9nam"] = self.title
                if self.artist:
                    audio["\xa9ART"] = self.artist
                if self.album:
                    audio["\xa9alb"] = self.album
                if self.year:
                    audio["\xa9day"] = self.year
                if self.track:
                    try:
                        track_num = int(self.track.split('/')[0])
                    except ValueError:
                        track_num = 0
                    audio["trkn"] = [(track_num, 0)]
                if self.genres:
                    audio["\xa9gen"] = ";".join(self.genres)
                audio["\xa9too"] = ""

                if "covr" in audio:
                    del audio["covr"]
                if self.cover_data:
                    mime = "image/jpeg" if not self.cover_data.startswith(b'\x89PNG') else "image/png"
                    fmt = MP4Cover.FORMAT_JPEG if mime == "image/jpeg" else MP4Cover.FORMAT_PNG
                    audio["covr"] = [MP4Cover(self.cover_data, fmt)]

                logger.debug("MP4: calling audio.save()")
                audio.save()
                logger.debug("MP4: save OK")

            else:
                logger.warning("Unsupported format: %s", type(audio).__name__)
                self.error.emit("Сохранение тегов для этого формата файла не поддерживается.")
                return

            del audio
            gc.collect()

            if self.new_filename_stem:
                new_filename = self.new_filename_stem + old_path_obj.suffix
                logger.debug("Rename check: new=%s, old=%s", new_filename, old_path_obj.name)
                if new_filename.lower() != old_path_obj.name.lower():
                    new_path_str = str(old_path_obj.with_name(new_filename))
                    if os.path.exists(new_path_str) and os.path.normpath(new_path_str) != os.path.normpath(current_filepath):
                        logger.warning("Rename target exists: %s", new_path_str)
                        self.error.emit(f"Файл «{new_filename}» уже существует!")
                        return
                    logger.info("Renaming %s -> %s", current_filepath, new_path_str)
                    os.rename(current_filepath, new_path_str)
                    current_filepath = new_path_str

            logger.info("=== SAVE FINISHED — %s ===", current_filepath)
            self.save_finished.emit(current_filepath)
        except Exception as e:
            logger.error("Save thread failed: %s", e, exc_info=True)
            self.error.emit(f"Не удалось сохранить теги:{e}")