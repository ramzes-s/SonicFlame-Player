import os

from PySide6.QtWidgets import QHBoxLayout, QWidget

from musicplayer import config as cfg
from musicplayer.ui.widgets.frameless_dialog import FramelessDialog
from .key_folders_widget import KeyFoldersWidget
from .folder_tree_widget import FolderTreeWidget
from .bottom_bar_widget import BottomBarWidget


class FolderBrowseDialog(FramelessDialog):

    def __init__(self, parent=None, title="\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443",
                 start_path="", root_path=None):
        super().__init__(parent)
        self._norm_root = os.path.normpath(root_path) if root_path else None
        self._start_path = start_path
        self._selected_path = None

        self.setWindowTitle(title)
        self.setMinimumSize(640, 500)
        self.resize(800, 720)

        self._build_ui(title)
        self.apply_accent_color()

    @property
    def selected_path(self) -> str:
        return self._selected_path

    def _build_ui(self, title_text: str):
        inner = self._setup_ui()
        title_bar = self._build_title_bar(title_text)
        inner.addWidget(title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._key_widget = KeyFoldersWidget(norm_root=self._norm_root, parent=self)
        body.addWidget(self._key_widget)

        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: rgba(80,80,80,0.2);")
        body.addWidget(sep)

        self._tree_widget = FolderTreeWidget(
            norm_root=self._norm_root, start_path=self._start_path, parent=self
        )
        body.addWidget(self._tree_widget, 1)

        inner.addLayout(body, 1)

        self._bottom_bar = BottomBarWidget(parent=self)
        inner.addWidget(self._bottom_bar)

        # connect signals AFTER widgets created but BEFORE populate_tree
        self._key_widget.folder_selected.connect(self._on_key_folder_selected)
        self._tree_widget.folder_selected.connect(self._on_tree_folder_selected)
        self._tree_widget.folder_activated.connect(self._accept_current)
        self._bottom_bar.select_requested.connect(self._accept_current)

        # now safe to populate (signals are connected)
        self._tree_widget.populate_tree()
        if self._norm_root and os.path.isdir(self._norm_root):
            root_name = os.path.basename(self._norm_root) or self._norm_root
            self._key_widget.prepend_root_to_key_list(root_name)
        self._key_widget.load_key_folders()

    def _on_key_folder_selected(self, path, is_root):
        self._tree_widget.clear_selection()
        self._tree_widget.clear_filter()
        self._selected_path = path
        self._bottom_bar.set_selected_path(path)
        if not is_root:
            self._tree_widget.navigate_to(path)

    def _on_tree_folder_selected(self, path):
        self._key_widget.clear_selection()
        self._selected_path = path
        self._bottom_bar.set_selected_path(path)

    def _accept_current(self):
        if self._selected_path and os.path.isdir(self._selected_path):
            self.accept()

    def apply_accent_color(self):
        super().apply_accent_color()
        accent = cfg.get_accent_color()
        self._key_widget.apply_accent_color(accent)
        self._tree_widget.apply_accent_color(accent)
        self._bottom_bar.apply_accent_color(accent)
        self.update()

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
