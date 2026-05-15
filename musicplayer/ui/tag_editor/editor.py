import os
import re
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QLabel, QLineEdit, QPushButton, QFileDialog,
                              QMessageBox, QWidget, QScrollArea, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from musicplayer import config as cfg

from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC

from .constants import ID3_GENRES
from .cover import _generate_abstract_cover
from .cover_thread import _CoverSearchThread
from .threads import _TrackSearchThread, _SaveTagsThread, _CoverDownloadThread
from .widgets import LoadingBar, CoverDisplayLabel
from .dialogs import CoverSearchResultsDialog, TrackSearchResultsDialog
from .base_dialog import BaseFramelessDialog
from .track_mover import move_track_to_folder


class TagEditorDialog(BaseFramelessDialog):
    def __init__(self, file_path, parent=None, update_player: bool = False):
        super().__init__(parent)
        self.file_path = file_path
        self.cover_data = None
        self.genre_tags = []
        self._save_thread = None
        self.delete_confirmed = False
        self.setMinimumSize(800, 500)

        self._build_ui()
        self._load_tags()

    def _build_ui(self):
        inner = self._setup_ui()

        title_bar = self._build_title_bar("Редактирование тегов")
        inner.addWidget(title_bar)

        content = self._content_widget()
        inner.addWidget(content, stretch=1)

        self.loading_bar = LoadingBar()
        inner.addWidget(self.loading_bar)

    def _content_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(20)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        self.cover_label = CoverDisplayLabel()
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.cover_double_clicked.connect(self._on_cover_double_clicked)
        left_col.addWidget(self.cover_label)

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
        content_layout.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        self.title_edit = self._text_input()
        title_row.addWidget(self.title_edit)
        self.title_from_fname_btn = self._action_button("Из имени файла", width=120)
        self.title_from_fname_btn.clicked.connect(self._apply_title_from_filename)
        title_row.addWidget(self.title_from_fname_btn)
        form.addRow("Название:", title_row)

        artist_row = QHBoxLayout()
        artist_row.setSpacing(0)
        self.artist_edit = self._text_input()
        artist_row.addWidget(self.artist_edit)
        self.artist_from_fname_btn = self._action_button("Из имени файла", width=120)
        self.artist_from_fname_btn.clicked.connect(self._apply_artist_from_filename)
        artist_row.addWidget(self.artist_from_fname_btn)
        form.addRow("Артист:", artist_row)

        self.title_edit.textChanged.connect(self._update_fname_buttons)
        self.artist_edit.textChanged.connect(self._update_fname_buttons)

        self.album_edit = self._text_input()
        form.addRow("Альбом:", self.album_edit)

        self.year_edit = self._text_input()
        form.addRow("Год:", self.year_edit)

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

        fname_col = QVBoxLayout()
        fname_col.setSpacing(4)
        fname_row = QHBoxLayout()
        fname_row.setSpacing(0)
        self.filename_edit = self._text_input()
        fname_row.addWidget(self.filename_edit)
        self.filename_from_tags_btn = self._action_button("Из тегов", width=100)
        self.filename_from_tags_btn.clicked.connect(self._apply_title_from_tags)
        fname_row.addWidget(self.filename_from_tags_btn)
        fname_col.addLayout(fname_row)
        self.filepath_hint = QLabel()
        self.filepath_hint.setStyleSheet("color: #999999; font-size: 11px; padding-left: 2px;")
        fname_col.addWidget(self.filepath_hint)
        form.addRow("Имя файла:", fname_col)

        badge_style = """
            QLabel { background-color: rgba(40, 40, 40, 0.8); color: #BBBBBB; border: 1px solid rgba(80, 80, 80, 0.5); border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: bold; }
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

        content_layout.addLayout(right_col)
        layout.addLayout(content_layout)

        btn_row = QHBoxLayout()
        self.delete_btn = self._destructive_button("Удалить")
        self.delete_btn.clicked.connect(self._prompt_delete_track)
        btn_row.addWidget(self.delete_btn)

        self.move_btn = self._action_button("Переместить в папку")
        self.move_btn.clicked.connect(self._move_track)
        btn_row.addWidget(self.move_btn)
        btn_row.addStretch()

        self.save_btn = self._primary_button("Сохранить")
        self.save_btn.clicked.connect(self._save_tags)
        btn_row.addWidget(self.save_btn)

        self.cancel_btn = self._secondary_button("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)
        return widget

    def _text_input(self):
        edit = QLineEdit()
        edit.setFixedHeight(32)
        edit.setMinimumWidth(350)
        edit.setStyleSheet(f"""
            QLineEdit {{ background-color: #1a1a1a; border: 1px solid rgba(80, 80, 80, 0.5); border-radius: 0; padding: 0 10px; color: #FFFFFF; font-size: 13px; }}
            QLineEdit:focus {{ border-color: {cfg.get_accent_color()}; }}
        """)
        return edit

    def _action_button(self, text, width=None):
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        if width:
            btn.setFixedWidth(width)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { background-color: rgba(40, 40, 40, 0.8); border: 1px solid rgba(80, 80, 80, 0.5); border-radius: 0; color: #FFFFFF; font-size: 12px; padding: 0 12px; }
            QPushButton:hover { background-color: rgba(60, 60, 60, 0.8); }
        """)
        return btn

    def _primary_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        accent = cfg.get_accent_color()
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {accent}; border: none; border-radius: 0; color: #FFFFFF; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #FFFFFF; color: {accent}; }}
        """)
        return btn

    def _secondary_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { background-color: rgba(40, 40, 40, 0.8); border: 1px solid rgba(80, 80, 80, 0.5); border-radius: 0; color: #FFFFFF; font-size: 13px; }
            QPushButton:hover { background-color: rgba(60, 60, 60, 0.8); }
        """)
        return btn

    def _destructive_button(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setFixedWidth(120)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { background-color: #501010; border: 1px solid #802020; border-radius: 0; color: #FFFFFF; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background-color: #801010; border-color: #A02020; }
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

    def _move_track(self):
        new_filepath = move_track_to_folder(self.file_path, self)
        if new_filepath:
            self.file_path = new_filepath
            self.accept()

    def _show_genre_menu(self):
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
        scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { background: #000; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(80,80,80,0.5); border-radius: 2px; min-height: 30px; }
        """)

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        for genre in available:
            lbl = QLabel(f"  {genre}")
            lbl.setFixedHeight(26)
            lbl.setStyleSheet(f"""
                QLabel {{ color: #FFFFFF; font-size: 12px; padding: 0 8px; }}
                QLabel:hover {{ background: rgba(80, 80, 80, 0.5); color: {cfg.get_accent_color()}; }}
            """)
            lbl.setAttribute(Qt.WA_Hover)
            lbl.mouseReleaseEvent = lambda event, g=genre: self._on_genre_select(g, popup)
            c_layout.addWidget(lbl)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        popup.setMinimumWidth(220)
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
        for i in reversed(range(self.genre_layout.count())):
            widget = self.genre_layout.itemAt(i).widget()
            if widget and widget != self.add_genre_btn:
                widget.deleteLater()
        accent = cfg.get_accent_color()
        for tag in self.genre_tags:
            btn = QPushButton(f"✕ {tag}")
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: #1a1a1a; border: 1px solid {accent}; border-radius: 0; padding: 0 8px; font-size: 11px; color: {accent}; }}
                QPushButton:hover {{ background-color: #252525; }}
            """)
            btn.clicked.connect(lambda checked=False, t=tag: self._remove_genre_tag(t))
            self.genre_layout.insertWidget(self.genre_layout.count() - 1, btn)

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

            if hasattr(audio, 'info'):
                info = audio.info
                if hasattr(info, 'bitrate') and info.bitrate:
                    self.bitrate_lbl.setText(f"{info.bitrate // 1000}kb")
                if hasattr(info, 'sample_rate') and info.sample_rate:
                    self.samplerate_lbl.setText(f"{info.sample_rate / 1000:.0f}khz")
                if hasattr(info, 'length') and info.length:
                    mins, secs = divmod(int(info.length), 60)
                    self.duration_lbl.setText(f"{mins}:{secs:02d}")

            size_bytes = os.path.getsize(self.file_path)
            if size_bytes < 1024 * 1024:
                self.size_lbl.setText(f"{size_bytes / 1024:.0f}KB")
            else:
                self.size_lbl.setText(f"{size_bytes / (1024 * 1024):.1f}MB")

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
                if audio.pictures:
                    self.cover_data = audio.pictures[0].data

        except Exception:
            pass

        if self.cover_data:
            self._apply_cover_data(self.cover_data, is_generated=False)

        self._refresh_genre_tags()
        self.filename_edit.setText(Path(self.file_path).stem)
        self.filepath_hint.setText(str(Path(self.file_path).parent).replace(os.sep, " ➤ "))
        self._update_fname_buttons()

    def _apply_title_from_tags(self):
        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        if artist or title:
            name = f"{artist} - {title}" if artist and title else (artist or title)
            name = name.replace('/', '+')
            self.filename_edit.setText(name)
        else:
            QMessageBox.information(self, "Информация", "Теги названия и артиста пусты!")

    def _parse_filename(self):
        basename = os.path.basename(self.file_path)
        name = Path(basename).stem
        for sep in [' - ', ' \u2013 ']:
            if sep in name:
                parts = name.split(sep, 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                if artist and title:
                    return artist, title
        return '', name

    def _apply_title_from_filename(self):
        artist, title = self._parse_filename()
        if title:
            self.title_edit.setText(title)
        if artist:
            self.artist_edit.setText(artist)
        self._update_fname_buttons()

    def _apply_artist_from_filename(self):
        artist, title = self._parse_filename()
        if artist:
            self.artist_edit.setText(artist)
        if title:
            self.title_edit.setText(title)
        self._update_fname_buttons()

    def _update_fname_buttons(self):
        title_empty = not self.title_edit.text().strip()
        artist_empty = not self.artist_edit.text().strip()
        self.title_from_fname_btn.setVisible(title_empty or artist_empty)
        self.artist_from_fname_btn.setVisible(title_empty or artist_empty)

    def _fill_fields_from_filename(self):
        title_empty = not self.title_edit.text().strip()
        artist_empty = not self.artist_edit.text().strip()
        if title_empty or artist_empty:
            artist, title = self._parse_filename()
            if artist and artist_empty:
                self.artist_edit.setText(artist)
            if title and title_empty:
                self.title_edit.setText(title)

    def _search_cover(self):
        self._fill_fields_from_filename()
        artist = self.artist_edit.text().strip()
        album = self.album_edit.text().strip()
        if not artist and not album:
            QMessageBox.information(self, "Информация", "Заполните поля Артист и/или Альбом для поиска!")
            return
        self.loading_bar.start()
        self._cover_search_thread = _CoverSearchThread(artist, album)
        self._cover_search_thread.finished_covers.connect(self._on_cover_search_done)
        self._cover_search_thread.start()

    def _on_cover_search_done(self, covers):
        self.loading_bar.stop()
        if not covers:
            QMessageBox.information(self, "Результат", "Обложка не найдена.")
            return
        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        dialog = CoverSearchResultsDialog(covers, self, artist=artist, title=title)
        result = dialog.exec()
        if result == QDialog.Accepted and dialog.selected_cover:
            self._apply_cover_data(dialog.selected_cover, is_generated=False)

    def _apply_cover_data(self, cover_data: bytes, is_generated: bool = False):
        self.cover_data = cover_data
        self.cover_label._is_generated_cover = is_generated
        pixmap = QPixmap()
        pixmap.loadFromData(self.cover_data)
        if not pixmap.isNull():
            scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover_label.setPixmap(scaled)
            self.cover_label.setText("")

    def _load_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите обложку", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            with open(path, "rb") as f:
                cover_data_from_file = f.read()
            self._apply_cover_data(cover_data_from_file, is_generated=False)

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
        self._fill_fields_from_filename()
        artist = self.artist_edit.text().strip()
        title = self.title_edit.text().strip()
        if not artist and not title:
            QMessageBox.information(self, "Информация", "Заполните хотя бы одно поле: Артист или Название!")
            return
        self.loading_bar.start()
        self._track_search_thread = _TrackSearchThread(artist, title)
        self._track_search_thread.finished_tracks.connect(self._on_track_search_done)
        self._track_search_thread.start()

    def _on_track_search_done(self, all_results):
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
        if result == QDialog.Accepted and dialog.selected_track:
            self._apply_track_search_result(dialog.selected_track)

    def _apply_track_search_result(self, track):
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

        art_url = track.get("artworkUrl100", "")
        if art_url:
            art_url = art_url.replace("100x100", "600x600")
            self._cover_dl_thread = _CoverDownloadThread(art_url)
            self._cover_dl_thread.finished_cover.connect(
                lambda data: self._apply_cover_data(data, is_generated=False))
            self._cover_dl_thread.start()

    def _save_tags(self):
        if self._save_thread and self._save_thread.isRunning():
            return
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
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
        self.delete_btn.setEnabled(True)
        self.file_path = new_filepath
        self.accept()

    def _on_save_error(self, message):
        self.loading_bar.stop()
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        QMessageBox.critical(self, "Ошибка", message)

    def _on_cover_double_clicked(self):
        if self.cover_data is None or self.cover_label._is_generated_cover:
            artist = self.artist_edit.text().strip()
            title = self.title_edit.text().strip()
            if not artist and not title:
                QMessageBox.information(self, "Генерация обложки", "Для генерации обложки заполните поля 'Артист' и/или 'Название'.")
                return
            generated_cover_data = _generate_abstract_cover(artist, title)
            self._apply_cover_data(generated_cover_data, is_generated=True)