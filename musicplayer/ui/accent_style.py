"""
Accent Style Applier — динамическое применение акцентного цвета ко всем виджетам.

Позволяет менять акцентный цвет без перезагрузки интерфейса.
"""

from musicplayer import config as cfg


def apply_accent_to_main_window(window, settings_dialog=None):
    """Обновить акцентный цвет во всех виджетах главного окна."""
    accent = cfg.get_accent_color()

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
    if hasattr(window, '_get_title_button_style'):
        window.close_btn.setStyleSheet(
            window._get_title_button_style(accent)
        )

    # Settings dialog (if open)
    if settings_dialog is not None:
        settings_dialog.apply_accent_color(accent)
