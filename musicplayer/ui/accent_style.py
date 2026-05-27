"""
Accent Style Applier — динамическое применение акцентного цвета ко всем виджетам.

Позволяет менять акцентный цвет без перезагрузки интерфейса.
"""

from musicplayer import config as cfg
from PySide6.QtWidgets import QWidget


def apply_accent_to_main_window(window, settings_dialog=None):
    """Обновить акцентный цвет во всех виджетах главного окна."""
    accent = cfg.get_accent_color()

    # Update container border
    container = window.findChild(QWidget, "main_container")
    if container:
        r = int(accent[1:3], 16)
        g = int(accent[3:5], 16)
        b = int(accent[5:7], 16)
        container.setStyleSheet(f"""
            #main_container {{
                background-color: #000000;
                border: 1px solid rgba({r}, {g}, {b}, 0.1);
            }}
        """)

    # Controls
    if hasattr(window, 'controls_widget'):
        window.controls_widget.apply_accent_color(accent)

    # Sidebar
    if hasattr(window, 'sidebar'):
        window.sidebar.apply_accent_color(accent)

    # Playlist
    if hasattr(window, 'playlist_widget'):
        window.playlist_widget.apply_accent_color(accent)

    # Track info
    if hasattr(window, 'track_info_widget'):
        window.track_info_widget.apply_accent_color(accent)

    # Обновить QSS seek slider (пересоздаём стиль)
    if hasattr(window, 'controls_widget') and hasattr(window.controls_widget, 'seek_slider'):
        window.controls_widget.seek_slider.setStyleSheet(
            window.controls_widget.seek_slider._get_style()
        )

    # Обновить QSS volume slider
    if hasattr(window, 'controls_widget') and hasattr(window.controls_widget, 'volume_slider'):
        window.controls_widget.volume_slider.setStyleSheet(
            window.controls_widget.volume_slider._get_style()
        )

    # Перерисовать playlist viewport
    if hasattr(window, 'playlist_widget') and hasattr(window.playlist_widget, 'list_widget'):
        window.playlist_widget.list_widget.viewport().update()

    # Title bar close button
    if hasattr(window, 'title_bar'):
        window.title_bar.close_button.setStyleSheet(
            window.title_bar._get_title_button_style(accent)
        )

    # Settings dialog (if open)
    if settings_dialog is not None:
        settings_dialog.apply_accent_color(accent)

    # FolderBrowseDialog (if open anywhere under main window)
    from musicplayer.ui.folder_browse.dialog import FolderBrowseDialog
    for dlg in window.findChildren(FolderBrowseDialog):
        dlg.apply_accent_color()
