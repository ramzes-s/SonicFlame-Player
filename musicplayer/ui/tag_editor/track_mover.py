import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox


def move_track_to_folder(file_path: str, parent=None) -> str | None:
    """
    Move an audio track to a different folder within the music root.

    Preserves favorite status and updates the path in the favorites table.

    Args:
        file_path: Current absolute path to the audio file.
        parent: Parent widget for modal dialogs.

    Returns:
        New file path if the move was successful, None otherwise.
    """
    from musicplayer.core.settings import AppSettings
    from musicplayer.core.db.favorites import is_favorite, toggle_favorite

    old_path = Path(file_path)
    current_dir = str(old_path.parent)

    music_folder = AppSettings().music_folder
    if not music_folder or not os.path.isdir(music_folder):
        QMessageBox.warning(parent, "Ошибка", "Корневая папка музыки не настроена.")
        return None

    dest_dir = QFileDialog.getExistingDirectory(
        parent, "Выберите папку для перемещения", current_dir)
    if not dest_dir:
        return None

    if os.path.normpath(dest_dir) == os.path.normpath(current_dir):
        QMessageBox.information(parent, "Информация", "Файл уже находится в этой папке.")
        return None

    abs_dest = os.path.normpath(dest_dir)
    abs_music = os.path.normpath(music_folder)
    if not abs_dest.startswith(abs_music + os.sep) and abs_dest != abs_music:
        QMessageBox.warning(parent, "Ошибка",
                            "Папка должна находиться внутри корневой папки музыки.")
        return None

    new_filepath = os.path.join(dest_dir, old_path.name)
    if os.path.exists(new_filepath):
        QMessageBox.warning(parent, "Ошибка",
                            f"Файл «{old_path.name}» уже существует в целевой папке.")
        return None

    was_favorite = is_favorite(file_path)

    try:
        shutil.move(file_path, new_filepath)
    except Exception as e:
        QMessageBox.critical(parent, "Ошибка",
                             f"Не удалось переместить файл: {e}")
        return None

    if was_favorite:
        toggle_favorite(new_filepath)

    return new_filepath
