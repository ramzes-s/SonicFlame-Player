"""Settings page — 'Плагины' tab with enable/disable toggles.

Config widgets are NOT embedded in the tab. Plugins with a
settings_widget_factory get a generic «Настроить» button that opens
a FramelessDialog with the plugin's config inside — avoiding the
DWM frame flash that HWND-heavy children trigger inside frameless windows.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QCheckBox, QPushButton, QScrollArea)
from PySide6.QtCore import Qt

from musicplayer import config as cfg
from musicplayer.core.plugin_manager import PluginInfo


class PluginsPage(QWidget):
    """One settings tab listing all discovered plugins."""

    def __init__(self, settings, plugin_infos: list[PluginInfo]):
        super().__init__()
        self._settings = settings
        self._plugin_infos = plugin_infos
        self._built = False
        self._inner_layout = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self._built:
            self._built = True
            self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: {cfg.BG_COLOR}; }}
            QScrollBar:vertical {{
                background-color: {cfg.BG_COLOR};
                width: 4px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cfg.SCROLLBAR_HANDLE_COLOR};
                min-height: 30px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cfg.SCROLLBAR_HANDLE_HOVER_COLOR};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        inner = QWidget()
        inner.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setContentsMargins(12, 10, 12, 10)
        self._inner_layout.setSpacing(0)

        if not self._plugin_infos:
            no_plugins = QLabel("Плагины не обнаружены.\n\n"
                                "Поместите папку с плагином в папку plugins/ рядом с программой.")
            no_plugins.setWordWrap(True)
            no_plugins.setStyleSheet(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 13px;")
            self._inner_layout.addWidget(no_plugins)
            self._inner_layout.addStretch()
        else:
            self._plugin_infos.sort(key=lambda i: not self._settings.get_plugin_enabled(i.name))
            for info in self._plugin_infos:
                self._add_plugin_row(info)
            self._inner_layout.addStretch()

        scroll.setWidget(inner)
        lo.addWidget(scroll)

    def _add_plugin_row(self, info: PluginInfo):
        accent = cfg.get_accent_color()
        is_enabled = self._settings.get_plugin_enabled(info.name)

        row = QWidget()
        row.setFixedHeight(60)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(12)

        toggle = QCheckBox()
        toggle.setChecked(is_enabled)
        toggle.setFixedSize(36, 36)
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.setStyleSheet(f"""
            QCheckBox {{ spacing: 0; }}
            QCheckBox::indicator {{
                width: 36px; height: 20px; border-radius: 10px;
                background-color: #444;
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
            }}
            QCheckBox::indicator:indeterminate {{
                background-color: #444;
            }}
        """)
        toggle.toggled.connect(
            lambda checked, name=info.name: self._on_toggle(name, checked))
        row_layout.addWidget(toggle)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_label = QLabel(f"{info.display_name}  "
                            f"<span style='color:{cfg.SECONDARY_TEXT_COLOR};"
                            f"font-size:14px;'>v{info.version}</span>")
        name_label.setStyleSheet(f"color: {cfg.TEXT_COLOR}; font-size: 14px; font-weight: bold;")
        text_col.addWidget(name_label)

        if info.description:
            desc = QLabel(info.description)
            desc.setStyleSheet(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 11px;")
            text_col.addWidget(desc)

        row_layout.addLayout(text_col, 1)

        if info.settings_widget_factory is not None:
            config_btn = QPushButton("\u2699 \u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c")
            config_btn.setAutoDefault(False)
            config_btn.setCursor(Qt.PointingHandCursor)
            config_btn.setFixedHeight(30)
            config_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; border: 1px solid {cfg.DIVIDER_COLOR};
                    color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px; padding: 0 12px;
                }}
                QPushButton:hover {{
                    border-color: {accent}; color: {accent};
                }}
            """)
            config_btn.clicked.connect(
                lambda checked=False, inf=info: self._open_config(inf))
            row_layout.addWidget(config_btn)

        self._inner_layout.addSpacing(8)
        self._inner_layout.addWidget(row)
        self._inner_layout.addSpacing(6)
        sep = QWidget()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background-color: {cfg.DIVIDER_COLOR};")
        self._inner_layout.addWidget(sep)

    def _open_config(self, info: PluginInfo):
        """Open a frameless dialog with the plugin's settings widget."""
        from musicplayer.ui.widgets.frameless_dialog import FramelessDialog

        dlg = FramelessDialog(self.window())
        inner = dlg._setup_ui()
        inner.addWidget(
            dlg._build_title_bar(f"{info.display_name} \u2014 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438"))

        config = info.settings_widget_factory()
        inner.addWidget(config)
        inner.addStretch()

        dlg.setMinimumSize(520, 200)
        content_h = config.sizeHint().height()
        dlg.resize(620, max(220, content_h + 80))
        dlg.center_on_parent()
        dlg.exec()

    def _on_toggle(self, name: str, checked: bool):
        self._settings.set_plugin_enabled(name, checked)

    def apply_accent_color(self, color: str):
        if not self._built or self._inner_layout is None:
            return
        for i in range(self._inner_layout.count()):
            item = self._inner_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                cb = w.findChild(QCheckBox)
                if cb:
                    cb.setStyleSheet(f"""
                        QCheckBox {{ spacing: 0; }}
                        QCheckBox::indicator {{
                            width: 36px; height: 20px; border-radius: 10px;
                            background-color: #444;
                        }}
                        QCheckBox::indicator:checked {{
                            background-color: {color};
                        }}
                        QCheckBox::indicator:indeterminate {{
                            background-color: #444;
                        }}
                    """)
                btn = w.findChild(QPushButton)
                if btn:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: transparent;
                            border: 1px solid {cfg.DIVIDER_COLOR};
                            color: {cfg.TERTIARY_TEXT_COLOR};
                            font-size: 12px; padding: 0 12px;
                        }}
                        QPushButton:hover {{
                            border-color: {color}; color: {color};
                        }}
                    """)
