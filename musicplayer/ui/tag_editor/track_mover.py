import os
import shutil
from pathlib import Path

from musicplayer.ui.widgets.styled_message_box import StyledMessageBox
from musicplayer.core.db.connection import normalize_path


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
        StyledMessageBox.critical(parent, "Ошибка", text="Корневая папка музыки не настроена.")
        return None

    from musicplayer.ui.widgets.folder_browse_dialog import FolderBrowseDialog
    dlg = FolderBrowseDialog(
        parent=parent,
        title="Выберите папку для перемещения",
        start_path=current_dir,
        root_path=music_folder
    )
    if dlg.exec() != 1:
        return None
    dest_dir = dlg.selected_path

    if os.path.normpath(dest_dir) == os.path.normpath(current_dir):
        StyledMessageBox.info(parent, "Информация", text="Файл уже находится в этой папке.")
        return None

    new_filepath = os.path.join(dest_dir, old_path.name)
    if os.path.exists(new_filepath):
        StyledMessageBox.critical(parent, "Ошибка",
                                   key=f"Файл «{old_path.name}» уже существует в целевой папке.")
        return None

    was_favorite = is_favorite(file_path)

    try:
        shutil.move(file_path, new_filepath)
    except Exception as e:
        StyledMessageBox.critical(parent, "Ошибка",
                                   key=f"Не удалось переместить файл: {e}")
        return None

    new_filepath = normalize_path(new_filepath)

    if was_favorite:
        toggle_favorite(new_filepath)

    return new_filepath
