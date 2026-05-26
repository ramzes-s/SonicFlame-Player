"""
Folder Browse Dialog — custom folder picker with dark theme, quick filter,
key folders sidebar (100+ tracks), and optional root restriction.
"""

import os
from pathlib import Path

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                QTreeWidget, QTreeWidgetItem, QListWidget,
                                QListWidgetItem, QLineEdit, QWidget, QComboBox,
                                QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

from musicplayer import config as cfg
from musicplayer.ui.widgets.frameless_dialog import FramelessDialog
from musicplayer.ui.svg_icons import get_folder_svg, get_all_music_svg
from musicplayer.core.db.queries import get_all_folders


# ── helpers ────────────────────────────────────────────────────

_IS_WIN = os.name == 'nt'


def _norm_path(path: str) -> str:
    """Normalize path separators; on Windows also lowercase for case-insensitive matching."""
    n = os.path.normpath(path)
    return n.lower() if _IS_WIN else n


def _path_startswith(path: str, prefix: str) -> bool:
    """Check if path starts with prefix (case-insensitive on Windows)."""
    p = _norm_path(path)
    pr = _norm_path(prefix) + os.sep
    return p.startswith(pr) or p == _norm_path(prefix)

def _make_folder_icon(px: int = 20, color: str = "#FFFFFF") -> QIcon:
    svg = get_folder_svg(16, color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    off = (px - 16) // 2
    renderer.render(painter, QRectF(off, off, 16, 16))
    painter.end()
    return QIcon(pixmap)


def _track_count_str(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} \u0442\u0440\u0435\u043a"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} \u0442\u0440\u0435\u043a\u0430"
    return f"{n} \u0442\u0440\u0435\u043a\u043e\u0432"

def _folder_count_str(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} \u043f\u0430\u043f\u043a\u0430"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} \u043f\u0430\u043f\u043a\u0438"
    return f"{n} \u043f\u0430\u043f\u043e\u043a"


_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background-color: #000000;
        width: 5px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background-color: rgba(80, 80, 80, 0.6);
        border-radius: 3px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: rgba(120, 120, 120, 0.8);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
"""

_FOLDER_ICON = None

def _get_folder_icon():
    global _FOLDER_ICON
    if _FOLDER_ICON is None:
        _FOLDER_ICON = _make_folder_icon(20, "#FFFFFF")
    return _FOLDER_ICON


# ── main dialog ────────────────────────────────────────────────

class FolderBrowseDialog(FramelessDialog):

    def __init__(self, parent=None, title="\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443",
                 start_path="", root_path=None):
        super().__init__(parent)
        self._norm_root = os.path.normpath(root_path) if root_path else None
        self._start_path = _norm_path(start_path) if start_path else ""
        self._selected_path = None
        self._items_by_path = {}  # path -> QTreeWidgetItem

        self.setWindowTitle(title)
        self.setMinimumSize(640, 500)
        self.resize(800, 720)

        self._build_ui(title)
        self._load_key_folders()
        self.apply_accent_color()
        self._populate_tree()

    @property
    def selected_path(self) -> str:
        return self._selected_path

    # ── build UI ───────────────────────────────────────────────

    def _build_ui(self, title_text: str):
        inner = self._setup_ui()
        title_bar = self._build_title_bar(title_text)
        inner.addWidget(title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel)

        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: rgba(80,80,80,0.2);")
        body.addWidget(sep)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, 1)

        inner.addLayout(body, 1)
        self._build_bottom_bar(inner)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(264)
        panel.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("\u041a\u043b\u044e\u0447\u0435\u0432\u044b\u0435 \u043f\u0430\u043f\u043a\u0438")
        header.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold; padding: 4px 2px;")
        layout.addWidget(header)

        self._key_list = QListWidget()
        self._key_list.setStyleSheet("""
            QListWidget {
                background-color: #000000; color: #CCCCCC; border: none;
                font-size: 12px; outline: none;
            }
            QListWidget::item {
                padding: 10px 4px 10px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }
            QListWidget::item:hover {
                background-color: rgba(80,80,80,0.2);
            }
        """ + _SCROLLBAR_STYLE)
        self._key_list.itemClicked.connect(self._on_key_folder_clicked)
        self._key_list.currentItemChanged.connect(self._on_key_folder_selection_changed)
        layout.addWidget(self._key_list, 1)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── filter + sort bar ───────────────────────────────────
        bar_widget = QWidget()
        bar_widget.setFixedHeight(32)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(6)

        self._sort_combo = QComboBox()
        self._sort_combo.addItem("\u041f\u043e \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044e", "name")
        self._sort_combo.addItem("\u041f\u043e \u0434\u0430\u0442\u0435", "date")
        self._sort_combo.addItem("\u041f\u043e \u0440\u0430\u0437\u043c\u0435\u0440\u0443", "size")
        self._sort_combo.setFixedWidth(100)
        self._sort_combo.setToolTip("\u0421\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u043a\u0430")
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("\U0001F50D  \u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u043f\u043e\u0438\u0441\u043a...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setStyleSheet("""
            QLineEdit {
                background-color: #000000; color: #FFFFFF;
                border: none; border-bottom: 1px solid rgba(80,80,80,0.5);
                padding: 4px 8px; font-size: 12px;
            }
        """)
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        bar.addWidget(self._filter_input, 1)

        bar.addWidget(self._sort_combo)

        layout.addWidget(bar_widget)

        # ── tree ───────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setIconSize(QPixmap(22, 22).size())
        self._tree.setSelectionMode(QTreeWidget.SingleSelection)
        self._tree.setStyleSheet("""
            QTreeWidget {
                background-color: #000000; color: #CCCCCC; border: none;
                font-size: 13px; outline: none;
            }
            QTreeWidget::item {
                padding: 6px 4px 6px 2px; border-bottom: 1px solid rgba(80,80,80,0.05);
            }
            QTreeWidget::item:hover {
                background-color: rgba(80,80,80,0.2);
            }
        """ + _SCROLLBAR_STYLE)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self._tree, 1)

        return panel

    def _build_bottom_bar(self, parent_layout: QVBoxLayout):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background-color: #000000;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 16, 0)
        bar_layout.setSpacing(12)

        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)

        self._breadcrumb_label = QLabel()
        self._breadcrumb_label.setStyleSheet("color: #888888; font-size: 12px;")
        left_layout.addWidget(self._breadcrumb_label)

        self._breadcrumb_count = QLabel()
        self._breadcrumb_count.setStyleSheet("color: #666666; font-size: 12px;")
        left_layout.addWidget(self._breadcrumb_count)

        bar_layout.addWidget(left_widget)
        bar_layout.addStretch(1)

        self._select_btn = QPushButton("\u0412\u044b\u0431\u0440\u0430\u0442\u044c")
        self._select_btn.setFixedHeight(32)
        self._select_btn.setFixedWidth(140)
        self._select_btn.setCursor(Qt.PointingHandCursor)
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 160))
        self._select_btn.setGraphicsEffect(shadow)
        bar_layout.addWidget(self._select_btn)
        parent_layout.addWidget(bar)

    def apply_accent_color(self):
        super().apply_accent_color()
        accent = cfg.get_accent_color()

        self._key_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #000000; color: #CCCCCC; border: none;
                font-size: 12px; outline: none;
            }}
            QListWidget::item {{
                padding: 10px 4px 10px 2px; border-bottom: 1px solid rgba(80,80,80,0.1);
            }}
            QListWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
            QListWidget::item:selected {{
                background-color: {accent}; color: #000000;
            }}
        {_SCROLLBAR_STYLE}""")

        self._sort_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #000000; border: none; outline: none;
                border-bottom: 1px solid {accent};
                color: #FFFFFF; font-size: 12px;
                padding: 4px 4px 4px 8px;
            }}
            QComboBox::drop-down {{
                border: none; outline: none; width: 16px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #000000; border: 1px solid {accent};
                color: #FFFFFF; outline: none; margin: 0px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
            }}
            QComboBox QAbstractItemView::viewport {{
                background-color: #000000; border: none;
            }}
        """)

        self._filter_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #000000; color: #FFFFFF;
                border: none; border-bottom: 1px solid rgba(80,80,80,0.5);
                padding: 4px 8px; font-size: 12px;
            }}
            QLineEdit:focus {{ border: none; border-bottom: 1px solid {accent}; }}
        """)

        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #000000; color: #CCCCCC; border: none;
                font-size: 13px; outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 4px 6px 2px; border-bottom: 1px solid rgba(80,80,80,0.05);
            }}
            QTreeWidget::item:hover {{
                background-color: rgba(80,80,80,0.2);
            }}
            QTreeWidget::item:selected {{
                background-color: {accent}; color: #000000;
            }}
        {_SCROLLBAR_STYLE}""")

        self._select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent}; border: none; border-radius: 0;
                color: #FFFFFF; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #FFFFFF; color: {accent}; }}
            QPushButton:disabled {{ background-color: rgba(80,80,80,0.3); color: #666666; }}
        """)

        self._update_root_item_accent(accent)
        self.update()

    # ── key folders ────────────────────────────────────────────

    def _load_key_folders(self):
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
            name_lbl.setStyleSheet("color: #CCCCCC; font-size: 12px;")
            hl.addWidget(name_lbl, 1)

            cnt_lbl = QLabel(str(count))
            cnt_lbl.setStyleSheet("color: #666666; font-size: 11px;")
            hl.addWidget(cnt_lbl)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, folder_path)
            item.setToolTip(folder_path)
            self._key_list.addItem(item)
            self._key_list.setItemWidget(item, widget)

    def _prepend_root_to_key_list(self, root_name: str):
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
        name_lbl.setObjectName("root_name")
        name_lbl.setStyleSheet(f"color: {accent}; font-size: 14px; font-weight: 600; margin-bottom: 12px;")
        hl.addWidget(name_lbl, 1)

        cnt = self._get_track_count(root_path)
        cnt_lbl = QLabel(str(cnt) if cnt else "")
        cnt_lbl.setObjectName("root_count")
        cnt_lbl.setStyleSheet(f"color: #666666; font-size: 11px; margin-bottom: 12px;")
        hl.addWidget(cnt_lbl)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, root_path)
        item.setData(Qt.UserRole + 1, True)  # mark as root item
        item.setToolTip(root_path)
        self._key_list.insertItem(0, item)
        self._key_list.setItemWidget(item, widget)

    def _update_root_item_accent(self, accent: str):
        for i in range(self._key_list.count()):
            item = self._key_list.item(i)
            if item and item.data(Qt.UserRole + 1):
                is_selected = self._key_list.currentItem() is item
                widget = self._key_list.itemWidget(item)
                if widget is None:
                    return
                icon_color = "#000000" if is_selected else accent
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
                    root_color = "#000000" if is_selected else accent
                    root_lbl.setStyleSheet(f"color: {root_color}; font-size: 14px; font-weight: 600; margin-bottom: 12px;")
                cnt_lbl = widget.findChild(QLabel, "root_count")
                if cnt_lbl:
                    cnt_color = "#000000" if is_selected else "#666666"
                    cnt_lbl.setStyleSheet(f"color: {cnt_color}; font-size: 11px; margin-bottom: 12px;")
                return

    # ── tree population ────────────────────────────────────────

    def _is_inside_root(self, path: str) -> bool:
        if self._norm_root is None:
            return True
        return _path_startswith(path, self._norm_root)

    def _populate_drives(self):
        if _IS_WIN:
            import ctypes, string
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            drives = []
            for i, letter in enumerate(string.ascii_uppercase):
                if bitmask & (1 << i):
                    drives.append(f"{letter}:\\")
        else:
            drives = ["/"]

        for drive in drives:
            if not os.path.isdir(drive):
                continue
            item = QTreeWidgetItem()
            item.setIcon(0, _get_folder_icon())

            item.setText(0, " " + drive)
            item.setToolTip(0, drive)
            item.setData(0, Qt.UserRole, drive)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            self._tree.addTopLevelItem(item)
            self._items_by_path[_norm_path(drive)] = item
            self._selected_path = drive
            self._select_btn.setEnabled(True)
            self._update_breadcrumb(drive)

    def _populate_tree(self):
        self._tree.clear()
        self._items_by_path.clear()

        if self._norm_root and os.path.isdir(self._norm_root):
            root_name = os.path.basename(self._norm_root) or self._norm_root
            self._selected_path = os.path.normpath(self._norm_root)
            self._select_btn.setEnabled(True)
            self._update_breadcrumb(os.path.normpath(self._norm_root))
            self._add_dir_children(self._tree, self._norm_root)
            self._prepend_root_to_key_list(root_name)
        else:
            self._populate_drives()

        if self._start_path and os.path.isdir(self._start_path):
            self._navigate_to(self._start_path)

    def _add_dir_children(self, parent, dir_path: str):
        """Add subdirectory items under parent (QTreeWidget or QTreeWidgetItem)."""
        try:
            entries = list(e for e in os.scandir(dir_path) if e.is_dir())
        except (PermissionError, OSError):
            return

        items = []
        for entry in entries:
            child_path = entry.path
            if not self._is_inside_root(child_path):
                continue
            item = QTreeWidgetItem()
            item.setIcon(0, _get_folder_icon())
            item.setText(0, " " + entry.name)
            item.setToolTip(0, child_path)
            item.setData(0, Qt.UserRole, child_path)
            item.setData(0, Qt.UserRole + 1, entry.stat().st_mtime)
            item.setData(0, Qt.UserRole + 2, entry.stat().st_size)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            items.append(item)
            self._items_by_path[_norm_path(child_path)] = item

        if items:
            items.sort(key=self._sort_key_for_item)
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItems(items)
            else:
                for item in items:
                    parent.addChild(item)

    _sort_mode = "name"

    def _sort_key_for_item(self, item: QTreeWidgetItem):
        mode = self._sort_mode
        if mode == "date":
            return item.data(0, Qt.UserRole + 1) or 0
        if mode == "size":
            return item.data(0, Qt.UserRole + 2) or 0
        return item.text(0).strip(" ").lower()

    def _on_sort_changed(self, index: int):
        self._sort_mode = self._sort_combo.currentData()
        self._resort_tree()

    def _resort_tree(self):
        root = self._tree.invisibleRootItem()
        items = [root.child(i) for i in range(root.childCount())]
        items.sort(key=self._sort_key_for_item)
        for item in items:
            root.removeChild(item)
        for item in items:
            root.addChild(item)

    def _populate_subdirs(self, item: QTreeWidgetItem):
        """Lazy-load children when an item is expanded."""
        if item.childCount() > 0:
            return
        dir_path = item.data(0, Qt.UserRole)
        if not dir_path or not os.path.isdir(dir_path):
            return
        self._add_dir_children(item, dir_path)

    # ── navigation ─────────────────────────────────────────────

    def _navigate_to(self, path: str):
        np_key = _norm_path(path)
        item = self._items_by_path.get(np_key)
        if item:
            self._tree.setCurrentItem(item)
            self._tree.scrollToItem(item)
            self._expand_parents(item)
            display_path = item.data(0, Qt.UserRole) or path
            self._selected_path = display_path
            self._select_btn.setEnabled(True)
            self._update_breadcrumb(display_path)
            return

        # Path not loaded — walk hierarchy loading each level
        if self._norm_root:
            root_key = _norm_path(self._norm_root)
        else:
            root_key = _norm_path(os.path.splitdrive(os.path.normpath(path))[0] + os.sep)

        current_item = self._items_by_path.get(root_key)
        if not current_item:
            return

        # Collect path parts from root to target
        parts = []
        p = os.path.normpath(path)
        while True:
            pk = _norm_path(p)
            if pk == root_key:
                break
            parts.append(p)
            parent = os.path.dirname(p)
            if _norm_path(parent) == root_key:
                break
            p = parent
        parts.reverse()

        for part in parts:
            pk = _norm_path(part)
            child_item = self._items_by_path.get(pk)
            if not child_item:
                self._populate_subdirs(current_item)
                child_item = self._items_by_path.get(pk)
            if child_item:
                self._populate_subdirs(child_item)
                current_item = child_item
                self._tree.setCurrentItem(current_item)
                self._tree.scrollToItem(current_item)
                display_path = child_item.data(0, Qt.UserRole) or part
                self._selected_path = display_path
                self._select_btn.setEnabled(True)
                self._update_breadcrumb(display_path)
            else:
                break

        if current_item:
            self._expand_parents(current_item)

    def _expand_parents(self, item: QTreeWidgetItem):
        """Expand all ancestors of item so it becomes visible."""
        parents = []
        p = item.parent()
        while p:
            parents.append(p)
            p = p.parent()
        for p in reversed(parents):
            self._populate_subdirs(p)
            p.setExpanded(True)

    # ── event handlers ─────────────────────────────────────────

    def _on_filter_text_changed(self, text: str):
        t = text.strip().lower()
        self._apply_filter(t)

    def _apply_filter(self, filter_text: str):
        """Walk all loaded items and hide/show based on filter."""
        def walk(parent_item):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                name = item.text(0).strip().lower() if item.text(0) else ""
                has_visible_child = False
                for ci in range(item.childCount()):
                    cname = item.child(ci).text(0).strip().lower() if item.child(ci).text(0) else ""
                    if not filter_text or filter_text in cname:
                        has_visible_child = True
                        break
                visible = (not filter_text) or (filter_text in name) or has_visible_child
                item.setHidden(not visible)
                if item.childCount():
                    walk(item)

        root = self._tree.invisibleRootItem()
        if root:
            walk(root)

    def _on_key_folder_clicked(self, item: QListWidgetItem):
        self._tree.clearSelection()
        path = item.data(Qt.UserRole)
        if not path or not os.path.isdir(path):
            return
        if item.data(Qt.UserRole + 1):
            self._filter_input.clear()
            self._selected_path = path
            self._select_btn.setEnabled(True)
            self._update_breadcrumb(path)
            return
        self._filter_input.clear()
        self._navigate_to(path)

    def _on_key_folder_selection_changed(self, current, previous):
        accent = cfg.get_accent_color()
        for item, is_selected in ((current, True), (previous, False)):
            if item is None:
                continue
            widget = self._key_list.itemWidget(item)
            if widget is None:
                continue
            if item.data(Qt.UserRole + 1):
                # Root music folder item
                icon_lbl = widget.findChild(QLabel)
                if icon_lbl:
                    icon_color = "#000000" if is_selected else accent
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
                        f"color: #000000; font-size: 14px; font-weight: 600; margin-bottom: 12px;" if is_selected
                        else f"color: {accent}; font-size: 14px; font-weight: 600; margin-bottom: 12px;"
                    )
                cnt_lbl = widget.findChild(QLabel, "root_count")
                if cnt_lbl:
                    cnt_lbl.setStyleSheet(
                        f"color: #000000; font-size: 11px; margin-bottom: 12px;" if is_selected
                        else f"color: #666666; font-size: 11px; margin-bottom: 12px;"
                    )
            else:
                # Regular key folder item
                name_lbl = widget.findChild(QLabel, "key_name")
                if name_lbl:
                    name_lbl.setStyleSheet(
                        f"color: #000000; font-size: 12px;" if is_selected
                        else "color: #CCCCCC; font-size: 12px;"
                    )

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        self._key_list.clearSelection()
        self._key_list.setCurrentItem(None)
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self._selected_path = path
            self._select_btn.setEnabled(True)
            self._update_breadcrumb(path)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self._selected_path = path
            self.accept()

    def _on_item_expanded(self, item: QTreeWidgetItem):
        self._populate_subdirs(item)

    def _on_select(self):
        if self._selected_path and os.path.isdir(self._selected_path):
            self.accept()

    def _update_breadcrumb(self, path: str):
        try:
            track_count = self._get_track_count(path)
            folder_count = self._get_subfolder_count(path)
            self._breadcrumb_label.setText(f'<span style="color:#FFFFFF;">{path}</span>')
            parts = []
            if folder_count:
                parts.append(f'<span style="color:#888888; font-size: 13px;">{_folder_count_str(folder_count)}  и </span>')
            if track_count:
                parts.append(f'<span style="color:#888888; font-size: 13px;">{_track_count_str(track_count)}</span>')
            self._breadcrumb_count.setText(" ".join(parts) if parts else '<span style="color:#666666; font-size: 13px;">Папка пуста</span>')
        except Exception:
            self._breadcrumb_label.setText(path)
            self._breadcrumb_count.clear()

    @staticmethod
    def _get_subfolder_count(folder_path: str) -> int:
        try:
            return sum(1 for e in os.scandir(folder_path) if e.is_dir())
        except (PermissionError, OSError):
            return 0

    @staticmethod
    def _get_track_count(folder_path: str) -> int:
        from musicplayer.core.db.folders import get_folder_track_count
        count = get_folder_track_count(folder_path)
        if count is not None:
            return count
        count = 0
        for ext in ('.mp3', '.flac', '.m4a', '.mp4'):
            try:
                count += len(list(Path(folder_path).glob(f'*{ext}')))
            except (PermissionError, OSError):
                pass
        return count

    # ── overrides ──────────────────────────────────────────────

    def exec(self):
        if self.parent():
            self.center_on_parent(30)
        else:
            self.center_on_screen()
        return super().exec()

    def accept(self):
        if self._selected_path and os.path.isdir(self._selected_path):
            super().accept()
        else:
            super().reject()
