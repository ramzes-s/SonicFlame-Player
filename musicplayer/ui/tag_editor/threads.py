from PySide6.QtCore import QThread, Signal
from pathlib import Path
import os
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture as FlacPicture
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, ID3NoHeaderError
from .api import _search_itunes_tracks_static, _search_deezer_tracks_static


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


class _SaveTagsThread(QThread):
    finished = Signal(str)
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
        try:
            current_filepath = self.file_path
            old_path_obj = Path(current_filepath)

            if self.new_filename_stem:
                new_filename = self.new_filename_stem + old_path_obj.suffix

                if new_filename.lower() != old_path_obj.name.lower():
                    new_path_str = str(old_path_obj.with_name(new_filename))
                    if os.path.exists(new_path_str) and os.path.normpath(new_path_str) != os.path.normpath(current_filepath):
                        self.error.emit(f"Файл «{new_filename}» уже существует!")
                        return
                    os.rename(current_filepath, new_path_str)
                    current_filepath = new_path_str

            audio = MutagenFile(current_filepath, easy=False)
            if audio is None:
                raise ValueError("Не удалось загрузить файл для сохранения.")

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