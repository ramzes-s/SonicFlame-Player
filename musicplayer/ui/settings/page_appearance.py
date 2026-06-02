from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QFrame, QStyledItemDelegate
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class TallItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(sz.height(), 36))
        return sz

from musicplayer import config as cfg
from .constants import ACCENT_PRESETS
from .widgets import ColorCircleButton


class AppearancePage(QWidget):
    accent_color_selected = Signal(str)
    dynamic_color_toggled = Signal(bool)
    mini_widget_toggled = Signal(bool)
    opacity_changed = Signal(int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(16)

        # Accent color
        accent_label = QLabel("Акцентный цвет")
        accent_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        lo.addWidget(accent_label)
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_buttons = {}
        for color_hex, _name in ACCENT_PRESETS:
            btn = ColorCircleButton(color_hex, size=22)
            btn.clicked.connect(lambda checked=False, c=color_hex: self._on_color_clicked(c))
            btn.setToolTip(color_hex)
            self._color_buttons[color_hex] = btn
            color_row.addWidget(btn)
        color_row.addStretch()
        lo.addLayout(color_row)

        # Dynamic color
        self.dynamic_color_cb = QCheckBox("Динамический цвет (из обложки)")
        self.dynamic_color_cb.setChecked(self._settings.dynamic_color)
        self.dynamic_color_cb.toggled.connect(self._on_dynamic_toggled)
        lo.addWidget(self.dynamic_color_cb)

        # Mini widget
        self.mini_widget_cb = QCheckBox("Включать виджет при сворачивании")
        self.mini_widget_cb.setChecked(self._settings.mini_widget_on_minimize)
        self.mini_widget_cb.toggled.connect(self._on_mini_widget_toggled)
        lo.addWidget(self.mini_widget_cb)

        # Opacity
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(10)
        self._opacity_combo = QComboBox()
        self._opacity_combo.setItemDelegate(TallItemDelegate(self._opacity_combo))
        opacity_label = QLabel("Прозрачность мини-виджета")
        opacity_label.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 13px;")
        for val in range(0, 81, 10):
            self._opacity_combo.addItem(str(val), None)
        self._opacity_combo.setCurrentText(str(self._settings.mini_widget_opacity))
        self._opacity_combo.currentTextChanged.connect(self._on_opacity_combo_changed)
        self._opacity_combo.setEnabled(self._settings.mini_widget_on_minimize)
        self._opacity_combo.setFixedWidth(70)
        opacity_row.addWidget(self._opacity_combo)
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch()
        lo.addLayout(opacity_row)

        lo.addStretch()

        self._apply_checkbox_style()
        self._update_combo_style()

    def _on_color_clicked(self, color_hex: str):
        self.accent_color_selected.emit(color_hex)

    def _on_dynamic_toggled(self, checked: bool):
        self._settings.dynamic_color = checked
        self.dynamic_color_toggled.emit(checked)

    def _on_mini_widget_toggled(self, checked: bool):
        self._settings.mini_widget_on_minimize = checked
        self._opacity_combo.setEnabled(checked)
        self.mini_widget_toggled.emit(checked)

    def _on_opacity_combo_changed(self, text: str):
        try:
            self._settings.mini_widget_opacity = int(text)
            self.opacity_changed.emit(int(text))
        except ValueError:
            pass

    def highlight_color(self, color_hex: str):
        for hex_key, btn in self._color_buttons.items():
            btn.set_selected(hex_key == color_hex)

    def _apply_checkbox_style(self):
        accent = cfg.get_accent_color()
        style = f"""
            QCheckBox {{
                color: {cfg.TERTIARY_TEXT_COLOR};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid rgba(80, 80, 80, 0.8);
                border-radius: 4px;
                background-color: #1a1a1a;
            }}
            QCheckBox::indicator:hover {{
                border-color: {accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
        """
        self.dynamic_color_cb.setStyleSheet(style)
        self.dynamic_color_cb.setCursor(Qt.PointingHandCursor)
        self.mini_widget_cb.setStyleSheet(style)
        self.mini_widget_cb.setCursor(Qt.PointingHandCursor)

    def _style_combo(self, combo: QComboBox):
        """Apply full stylesheet to a combo box using descendant selectors."""
        accent = cfg.get_accent_color()
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {cfg.BG_COLOR};
                border: none;
                outline: none;
                border-bottom: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                font-size: 14px;
                padding: 1px 8px 1px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
                outline: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cfg.BG_COLOR};
                border: 1px solid {accent};
                color: {cfg.TEXT_COLOR};
                outline: none;
                margin: 0px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::viewport {{
                background-color: {cfg.BG_COLOR};
                border: none;
            }}
        """)
        view = combo.view()
        if view:
            view.setFrameShape(QFrame.NoFrame)
            view.setFrameShadow(QFrame.Plain)

    def _update_combo_style(self):
        self._style_combo(self._opacity_combo)

    def apply_accent_color(self, color: str):
        self._apply_checkbox_style()
        self._style_combo(self._opacity_combo)
