import os

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                                QListWidgetItem, QWidget, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, QByteArray, QRectF, Signal
from PySide6.QtGui import QPixmap, QPainter, QFont
from PySide6.QtSvg import QSvgRenderer

from musicplayer import config as cfg
from musicplayer.ui.svg_icons import get_all_music_svg
from musicplayer.core.db.queries import get_all_folders
from .helpers import (_norm_path, _get_folder_icon, _get_track_count,
                      _SCROLLBAR_STYLE, get_favorite_folders,
                      remove_favorite_folder, FAVORITE_LIMIT)


class KeyFoldersWidget(QWidget):
    folder_selected = Signal(str, bool)  # path, is_root

    def __init__(self, norm_root=None, parent=None):
        super().__init__(parent)
        self._norm_root = norm_root
        self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(264)
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("\u041a\u043b\u044e\u0447\u0435\u0432\u044b\u0435 \u043f\u0430\u043f\u043a\u0438")
        header.setStyleSheet(f"color: {cfg.SECONDARY_TEXT_COLOR}; font-size: 11px; font-weight: bold; padding: 4px 2px;")
        layout.addWidget(header)

        self._key_list = QListWidget()
        self._key_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 12px; outline: none;
            }}
            QListWidget::item {{
                padding: 10px 4px 10px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }}
            QListWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
        """ + _SCROLLBAR_STYLE)
        self._key_list.itemClicked.connect(self._on_item_clicked)
        self._key_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._key_list, 1)

        # Favorite folders section
        self._fav_header = QLabel("\u0418\u0437\u0431\u0440\u0430\u043d\u043d\u044b\u0435 \u043f\u0430\u043f\u043a\u0438")
        self._apply_fav_header_style(cfg.get_accent_color())
        layout.addWidget(self._fav_header)

        self._fav_list = QListWidget()
        self._fav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 12px; outline: none;
            }}
            QListWidget::item {{
                padding: 8px 4px 8px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }}
            QListWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
        """ + _SCROLLBAR_STYLE)
        self._fav_list.itemClicked.connect(self._on_fav_item_clicked)
        self._fav_list.currentItemChanged.connect(self._on_fav_selection_changed)
        layout.addWidget(self._fav_list)

    def load_key_folders(self):
        items = get_all_folders()
        if self._norm_root is not None:
            root_norm = _norm_path(self._norm_root)
            items = [(p, c) for p, c in items if _norm_path(os.path.dirname(p)) == root_norm]
        items.sort(key=lambda x: -x[1])
        items = items[:10]

        for folder_path, count in items:
            name = os.path.basename(folder_path) or folder_path

            widget = QWidget()
            widget.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(widget)
            hl.setContentsMargins(2, 2, 4, 2)
            hl.setSpacing(6)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(_get_folder_icon().pixmap(16, 16))
            hl.addWidget(icon_lbl)

            name_lbl = QLabel(name)
            name_lbl.setObjectName("key_name")
            name_lbl.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px;")
            hl.addWidget(name_lbl, 1)

            cnt_lbl = QLabel(str(count))
            cnt_lbl.setStyleSheet(f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px;")
            hl.addWidget(cnt_lbl)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, folder_path)
            item.setToolTip(folder_path)
            self._key_list.addItem(item)
            self._key_list.setItemWidget(item, widget)

    def prepend_root_to_key_list(self, root_name: str):
        accent = cfg.get_accent_color()
        root_path = os.path.normpath(self._norm_root)
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        widget.setFixedHeight(28)
        hl = QHBoxLayout(widget)
        hl.setContentsMargins(2, 0, 4, 0)
        hl.setSpacing(2)

        icon_lbl = QLabel()
        svg = get_all_music_svg(22, accent)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, 22, 22))
        painter.end()
        icon_lbl.setPixmap(pixmap)
        icon_lbl.setStyleSheet("margin-bottom: 12px; margin-left: 4px;")
        hl.addWidget(icon_lbl)

        name_lbl = QLabel(root_name)
        name_lbl.setText("\u0412\u0441\u044f \u043c\u0443\u0437\u044b\u043a\u0430")
        name_lbl.setObjectName("root_name")
        name_lbl.setStyleSheet(f"color: {accent}; font-size: 14px; font-weight: 600; margin-bottom: 12px;")
        hl.addWidget(name_lbl, 1)

        cnt = _get_track_count(root_path)
        cnt_lbl = QLabel(str(cnt) if cnt else "")
        cnt_lbl.setObjectName("root_count")
        cnt_lbl.setStyleSheet(f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px; margin-bottom: 12px;")
        hl.addWidget(cnt_lbl)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, root_path)
        item.setData(Qt.UserRole + 1, True)
        item.setToolTip(root_path)
        self._key_list.insertItem(0, item)
        self._key_list.setItemWidget(item, widget)

    def clear_selection(self):
        self._key_list.clearSelection()
        self._key_list.setCurrentItem(None)

    def apply_accent_color(self, accent: str):
        self._key_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 12px; outline: none;
            }}
            QListWidget::item {{
                padding: 10px 4px 10px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }}
            QListWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
            QListWidget::item:selected {{
                background-color: {accent}; color: {cfg.BG_COLOR};
            }}
        {_SCROLLBAR_STYLE}""")
        self._fav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 12px; outline: none;
            }}
            QListWidget::item {{
                padding: 8px 4px 8px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }}
            QListWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
            QListWidget::item:selected {{
                background-color: {accent}; color: {cfg.BG_COLOR};
            }}
        {_SCROLLBAR_STYLE}""")
        self._apply_fav_header_style(accent)
        self._update_root_item_accent(accent)

    def _update_root_item_accent(self, accent: str):
        for i in range(self._key_list.count()):
            item = self._key_list.item(i)
            if item and item.data(Qt.UserRole + 1):
                is_selected = self._key_list.currentItem() is item
                widget = self._key_list.itemWidget(item)
                if widget is None:
                    return
                icon_color = cfg.BG_COLOR if is_selected else accent
                icon_lbl = widget.findChild(QLabel)
                if icon_lbl:
                    svg = get_all_music_svg(22, icon_color)
                    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
                    pixmap = QPixmap(22, 22)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    renderer.render(painter, QRectF(0, 0, 22, 22))
                    painter.end()
                    icon_lbl.setPixmap(pixmap)
                root_lbl = widget.findChild(QLabel, "root_name")
                if root_lbl:
                    root_color = cfg.BG_COLOR if is_selected else accent
                    root_lbl.setStyleSheet(f"color: {root_color}; font-size: 14px; font-weight: 600; margin-bottom: 12px;")
                cnt_lbl = widget.findChild(QLabel, "root_count")
                if cnt_lbl:
                    cnt_color = cfg.BG_COLOR if is_selected else cfg.DISABLED_TEXT_COLOR
                    cnt_lbl.setStyleSheet(f"color: {cnt_color}; font-size: 11px; margin-bottom: 12px;")
                return

    def _on_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        if not path or not os.path.isdir(path):
            return
        is_root = bool(item.data(Qt.UserRole + 1))
        self.folder_selected.emit(path, is_root)

    def _on_selection_changed(self, current, previous):
        accent = cfg.get_accent_color()
        for item, is_selected in ((current, True), (previous, False)):
            if item is None:
                continue
            widget = self._key_list.itemWidget(item)
            if widget is None:
                continue
            if item.data(Qt.UserRole + 1):
                icon_lbl = widget.findChild(QLabel)
                if icon_lbl:
                    icon_color = cfg.BG_COLOR if is_selected else accent
                    svg = get_all_music_svg(22, icon_color)
                    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
                    pixmap = QPixmap(22, 22)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    renderer.render(painter, QRectF(0, 0, 22, 22))
                    painter.end()
                    icon_lbl.setPixmap(pixmap)
                root_lbl = widget.findChild(QLabel, "root_name")
                if root_lbl:
                    root_lbl.setStyleSheet(
                        f"color: {cfg.BG_COLOR}; font-size: 14px; font-weight: 600; margin-bottom: 12px;" if is_selected
                        else f"color: {accent}; font-size: 14px; font-weight: 600; margin-bottom: 12px;"
                    )
                cnt_lbl = widget.findChild(QLabel, "root_count")
                if cnt_lbl:
                    cnt_lbl.setStyleSheet(
                        f"color: {cfg.BG_COLOR}; font-size: 11px; margin-bottom: 12px;" if is_selected
                        else f"color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px; margin-bottom: 12px;"
                    )
            else:
                name_lbl = widget.findChild(QLabel, "key_name")
                if name_lbl:
                    name_lbl.setStyleSheet(
                        f"color: {cfg.BG_COLOR}; font-size: 12px;" if is_selected
                        else f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px;"
                    )

    def is_in_key_list(self, path: str) -> bool:
        np = os.path.normpath(path)
        for i in range(self._key_list.count()):
            item = self._key_list.item(i)
            if item and os.path.normpath(item.data(Qt.UserRole)) == np:
                return True
        return False

    def _apply_fav_header_style(self, accent: str):
        self._fav_header.setStyleSheet(f"""
            color: {accent}; font-size: 11px; font-weight: bold;
            padding: 8px 2px 6px 2px;
            border-bottom: 1px solid rgba(80,80,80,0.1);
        """)

    # -- favorite folders --

    def load_favorite_folders(self):
        self._fav_list.clear()
        folders = get_favorite_folders()
        visible = bool(folders)
        self._fav_header.setVisible(visible)
        self._fav_list.setVisible(visible)
        if not visible:
            self._fav_list.setMaximumHeight(0)
            return
        for fp in folders:
            name = os.path.basename(fp) or fp
            widget = QWidget()
            widget.setStyleSheet("background: transparent;")
            hl = QHBoxLayout(widget)
            hl.setContentsMargins(2, 2, 4, 2)
            hl.setSpacing(6)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(_get_folder_icon().pixmap(16, 16))
            hl.addWidget(icon_lbl)

            name_lbl = QLabel(name)
            name_lbl.setObjectName("fav_name")
            name_lbl.setStyleSheet(f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px;")
            hl.addWidget(name_lbl, 1)

            rm_btn = QPushButton("\u2715")
            rm_btn.setFixedSize(18, 18)
            rm_btn.setCursor(Qt.PointingHandCursor)
            rm_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {cfg.DISABLED_TEXT_COLOR}; font-size: 11px;
                }}
                QPushButton:hover {{ color: {cfg.get_accent_color()}; }}
            """)
            fp_copy = fp
            rm_btn.clicked.connect(lambda checked=True, p=fp_copy: self._remove_fav(p))
            hl.addWidget(rm_btn)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, fp)
            item.setToolTip(fp)
            self._fav_list.addItem(item)
            self._fav_list.setItemWidget(item, widget)

        # limit fav_list height to its actual content
        row_h = self._fav_list.sizeHintForRow(0)
        if row_h > 0:
            self._fav_list.setMaximumHeight(row_h * self._fav_list.count())

    def _remove_fav(self, path: str):
        remove_favorite_folder(path)
        self.load_favorite_folders()

    def _on_fav_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        if not path or not os.path.isdir(path):
            return
        self.folder_selected.emit(path, False)

    def _on_fav_selection_changed(self, current, previous):
        for item, is_selected in ((current, True), (previous, False)):
            if item is None:
                continue
            widget = self._fav_list.itemWidget(item)
            if widget is None:
                continue
            name_lbl = widget.findChild(QLabel, "fav_name")
            if name_lbl:
                name_lbl.setStyleSheet(
                    f"color: {cfg.BG_COLOR}; font-size: 12px;" if is_selected
                    else f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 12px;"
                )
