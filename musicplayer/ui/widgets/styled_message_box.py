import html

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from musicplayer import config as cfg
from musicplayer.ui.svg_icons import get_info_svg, get_warning_svg, get_error_svg, get_question_svg
from .frameless_dialog import FramelessDialog


class StyledMessageBox(FramelessDialog):
    ICONS = {
        "info": get_info_svg,
        "warning": get_warning_svg,
        "error": get_error_svg,
        "question": get_question_svg,
    }

    def __init__(self, parent=None, title="", text="", key="", icon="info",
                 buttons=None, default_button=0, auto_close=0, widths=None):
        super().__init__(parent)
        self._title = title
        self._text = text
        self._key = key
        self._icon_name = icon
        self._auto_close = auto_close
        self._auto_close_remaining = auto_close
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.timeout.connect(self._on_auto_close_tick)
        self._result = -1
        if buttons is None:
            buttons = ["OK"]
        self._buttons = buttons
        self._widths = widths if widths else [120] * len(buttons)

        self.setMinimumSize(540, 160)
        self.setMaximumWidth(780)
        self._build_ui()

    def _build_ui(self):
        inner = self._setup_ui()
        title_bar = self._build_title_bar(self._title)
        inner.addWidget(title_bar)

        content = QWidget()
        content.setStyleSheet(f"""
            QWidget#msg_body {{ background-color: {cfg.BG_COLOR}; }}
            QLabel#msg_text {{ color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 14px; }}
        """)
        content.setObjectName("msg_body")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 20)
        content_layout.setSpacing(16)

        msg_row = QHBoxLayout()
        msg_row.setSpacing(16)

        icon_widget = QSvgWidget()
        icon_widget.setFixedSize(32, 32)
        icon_func = self.ICONS.get(self._icon_name, get_info_svg)
        svg_data = icon_func(32, cfg.get_accent_color()).encode('utf-8')
        icon_widget.renderer().load(QByteArray(svg_data))
        msg_row.addWidget(icon_widget, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(8)

        full_text = html.escape(self._text).replace("\n", "<br>")
        if self._key:
            full_text += "<br><br><b>" + html.escape(self._key).replace("\n", "<br>") + "</b>"
        self._text_label = QLabel(full_text)
        self._text_label.setTextFormat(Qt.RichText)
        self._text_label.setObjectName("msg_text")
        self._text_label.setWordWrap(True)
        text_col.addWidget(self._text_label)

        self._auto_close_label = QLabel()
        self._auto_close_label.setStyleSheet(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 11px;")
        self._auto_close_label.setVisible(False)
        text_col.addWidget(self._auto_close_label)

        msg_row.addLayout(text_col, 1)
        content_layout.addLayout(msg_row)

        self._btn_widgets = []
        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)
        btn_row.addStretch()

        for i, btn_text in enumerate(self._buttons):
            btn = QPushButton(btn_text)
            btn.setFixedHeight(34)
            btn.setFixedWidth(self._widths[i] if i < len(self._widths) else 120)
            btn.setCursor(Qt.PointingHandCursor)

            if i == len(self._buttons) - 1:
                accent = cfg.get_accent_color()
                btn.setStyleSheet(f"""
                    QPushButton {{ background-color: {accent}; border: none; border-radius: 0; color: {cfg.TEXT_COLOR}; font-size: 13px; font-weight: bold; }}
                    QPushButton:hover {{ background-color: {cfg.TEXT_COLOR}; color: {accent}; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {cfg.BUTTON_BG_COLOR};
                        border: 1px solid {cfg.DIVIDER_COLOR};
                        border-radius: 0;
                        color: {cfg.TEXT_COLOR};
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        background-color: {cfg.BUTTON_HOVER_BG_COLOR};
                    }}
                """)

            btn.clicked.connect(lambda checked=False, idx=i: self._on_button(idx))
            self._btn_widgets.append(btn)
            btn_row.addWidget(btn)

        content_layout.addLayout(btn_row)
        inner.addWidget(content, stretch=1)

        if self._auto_close > 0:
            self._start_auto_close()

    def _start_auto_close(self):
        self._auto_close_remaining = self._auto_close
        self._update_auto_close_label()
        self._auto_close_label.setVisible(True)
        self._auto_close_timer.start(1000)

    def _on_auto_close_tick(self):
        self._auto_close_remaining -= 1
        self._update_auto_close_label()
        if self._auto_close_remaining <= 0:
            self._auto_close_timer.stop()
            self.done(-1)

    def _update_auto_close_label(self):
        self._auto_close_label.setText(
            f"Окно закроется через {self._auto_close_remaining} сек..."
        )

    def _on_button(self, idx: int):
        self._auto_close_timer.stop()
        self.done(idx)

    def done(self, r):
        self._result = r
        super().done(r)

    def result(self):
        return self._result

    def exec(self):
        if self.parent():
            self.center_on_parent(50)
        else:
            self.center_on_screen()
        super().exec()
        return self._result

    @staticmethod
    def _run(parent, title, text, key, icon, buttons, default, auto_close, widths=None):
        dlg = StyledMessageBox(
            parent=parent, title=title, text=text, key=key,
            icon=icon, buttons=buttons, default_button=default,
            auto_close=auto_close, widths=widths
        )
        return dlg.exec()

    @staticmethod
    def info(parent, title, text, key="", auto_close=0):
        return StyledMessageBox._run(parent, title, text, key, "info", ["OK"], 0, auto_close)

    @staticmethod
    def warning(parent, title, text, key="", auto_close=0):
        return StyledMessageBox._run(parent, title, text, key, "warning", ["OK"], 0, auto_close)

    @staticmethod
    def critical(parent, title, text, key="", auto_close=0):
        return StyledMessageBox._run(parent, title, text, key, "error", ["OK"], 0, auto_close)

    @staticmethod
    def question(parent, title, text, key="", auto_close=0):
        return StyledMessageBox._run(parent, title, text, key, "question", ["Нет", "Да"], 1, auto_close)
