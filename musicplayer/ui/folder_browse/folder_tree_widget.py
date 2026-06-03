import os

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QTreeWidget,
                                QTreeWidgetItem, QLineEdit, QWidget, QComboBox,
                                QFrame, QStyledItemDelegate)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap


class _TallItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        sz = super().sizeHint(option, index)
        sz.setHeight(max(sz.height(), 36))
        return sz

from musicplayer import config as cfg
from .helpers import (_IS_WIN, _norm_path, _path_startswith, _get_folder_icon,
                      _SCROLLBAR_STYLE)


class FolderTreeWidget(QWidget):
    folder_selected = Signal(str)
    folder_activated = Signal(str)

    def __init__(self, norm_root=None, start_path="", parent=None):
        super().__init__(parent)
        self._norm_root = norm_root
        self._start_path = _norm_path(start_path) if start_path else ""
        self._items_by_path = {}
        self._sort_mode = "name"
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {cfg.BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # filter + sort bar
        bar_widget = QWidget()
        bar_widget.setFixedHeight(32)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(6)

        self._sort_combo = QComboBox()
        self._sort_combo.addItem("\u041f\u043e \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044e (\u0410-\u044f)", "name")
        self._sort_combo.addItem("\u041f\u043e \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044e (\u042f-\u0430)", "name_desc")
        self._sort_combo.addItem("\u041f\u043e \u0434\u0430\u0442\u0435", "date")
        self._sort_combo.setFixedWidth(180)
        self._sort_combo.setToolTip("\u0421\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u043a\u0430")
        self._sort_combo.setItemDelegate(_TallItemDelegate(self._sort_combo))
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self._style_sort_combo(cfg.get_accent_color())

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("\U0001F50D  \u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u043f\u043e\u0438\u0441\u043a...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TEXT_COLOR};
                border: none; border-bottom: 1px solid {cfg.DIVIDER_COLOR};
                padding: 4px 8px; font-size: 12px;
            }}
        """)
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        bar.addWidget(self._filter_input, 1)
        bar.addWidget(self._sort_combo)
        layout.addWidget(bar_widget)

        # tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setIconSize(QPixmap(22, 22).size())
        self._tree.setSelectionMode(QTreeWidget.SingleSelection)
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 13px; outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 4px 6px 2px; border-bottom: 1px solid rgba(80,80,80,0.05);
            }}
            QTreeWidget::item:hover {{
                background-color: {cfg.SECONDARY_BG_COLOR};
            }}
        """ + _SCROLLBAR_STYLE)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self._tree, 1)

    # -- public methods --

    def clear_selection(self):
        self._tree.clearSelection()

    def clear_filter(self):
        self._filter_input.clear()

    def populate_tree(self):
        self._tree.clear()
        self._items_by_path.clear()

        if self._norm_root and os.path.isdir(self._norm_root):
            self._add_dir_children(self._tree, self._norm_root)
            root_path = os.path.normpath(self._norm_root)
            self.folder_selected.emit(root_path)
        else:
            self._populate_drives()

        if self._start_path and os.path.isdir(self._start_path):
            self.navigate_to(self._start_path)

    def navigate_to(self, path):
        np_key = _norm_path(path)
        item = self._items_by_path.get(np_key)
        if item:
            self._tree.setCurrentItem(item)
            self._tree.scrollToItem(item)
            self._expand_parents(item)
            display_path = item.data(0, Qt.UserRole) or path
            self.folder_selected.emit(display_path)
            return

        if self._norm_root:
            root_key = _norm_path(self._norm_root)
        else:
            root_key = _norm_path(os.path.splitdrive(os.path.normpath(path))[0] + os.sep)

        current_item = self._items_by_path.get(root_key)
        if not current_item:
            return

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
                self.folder_selected.emit(display_path)
            else:
                break

        if current_item:
            self._expand_parents(current_item)

    def _style_sort_combo(self, accent):
        self._sort_combo.setStyleSheet(f"""
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
        view = self._sort_combo.view()
        if view:
            view.setFrameShape(QFrame.NoFrame)
            view.setFrameShadow(QFrame.Plain)

    def apply_accent_color(self, accent: str):
        self._style_sort_combo(accent)

        self._filter_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TEXT_COLOR};
                border: none; border-bottom: 1px solid {cfg.DIVIDER_COLOR};
                padding: 4px 8px; font-size: 12px;
            }}
            QLineEdit:focus {{ border: none; border-bottom: 1px solid {accent}; }}
        """)

        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {cfg.BG_COLOR}; color: {cfg.TERTIARY_TEXT_COLOR}; border: none;
                font-size: 13px; outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 4px 6px 2px; border-bottom: 1px solid {cfg.DIVIDER_ITEM_COLOR};
            }}
            QTreeWidget::item:hover {{
                background-color: {cfg.DIVIDER_ITEM_COLOR};
            }}
            QTreeWidget::item:selected {{
                background-color: {accent}; color: {cfg.BG_COLOR};
            }}
        {_SCROLLBAR_STYLE}""")

    # -- tree population --

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

        last_drive = None
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
            last_drive = drive

        if last_drive:
            self.folder_selected.emit(last_drive)

    def _is_inside_root(self, path):
        if self._norm_root is None:
            return True
        return _path_startswith(path, self._norm_root)

    def _add_dir_children(self, parent, dir_path):
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
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            items.append(item)
            self._items_by_path[_norm_path(child_path)] = item

        if items:
            items.sort(key=self._sort_key_for_item, reverse=self._sort_mode == "name_desc")
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItems(items)
            else:
                for item in items:
                    parent.addChild(item)

    def _sort_key_for_item(self, item):
        if self._sort_mode == "date":
            return item.data(0, Qt.UserRole + 1) or 0
        return item.text(0).strip(" ").lower()

    def _on_sort_changed(self, index):
        self._sort_mode = self._sort_combo.currentData()
        self._resort_tree()

    def _resort_tree(self):
        root = self._tree.invisibleRootItem()
        items = [root.child(i) for i in range(root.childCount())]
        items.sort(key=self._sort_key_for_item, reverse=self._sort_mode == "name_desc")
        for item in items:
            root.removeChild(item)
        for item in items:
            root.addChild(item)

    def _populate_subdirs(self, item):
        if item.childCount() > 0:
            return
        dir_path = item.data(0, Qt.UserRole)
        if not dir_path or not os.path.isdir(dir_path):
            return
        self._add_dir_children(item, dir_path)

    def _expand_parents(self, item):
        parents = []
        p = item.parent()
        while p:
            parents.append(p)
            p = p.parent()
        for p in reversed(parents):
            self._populate_subdirs(p)
            p.setExpanded(True)

    # -- event handlers --

    def _on_filter_text_changed(self, text):
        t = text.strip().lower()
        self._apply_filter(t)

    def _apply_filter(self, filter_text):
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

    def _on_item_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self.folder_selected.emit(path)

    def _on_item_double_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self.folder_activated.emit(path)

    def _on_item_expanded(self, item):
        self._populate_subdirs(item)
