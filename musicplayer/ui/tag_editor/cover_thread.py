from PySide6.QtCore import QThread, Signal
from .api import _search_itunes_covers_static, _search_deezer_covers_static


class _CoverSearchThread(QThread):
    finished_covers = Signal(list)

    def __init__(self, artist, album):
        super().__init__()
        self.artist = artist
        self.album = album

    def run(self):
        covers = []
        seen_hashes = set()

        itunes_covers = _search_itunes_covers_static(self.artist, self.album)
        for label, data in itunes_covers:
            h = hash(data)
            if h not in seen_hashes:
                seen_hashes.add(h)
                covers.append((label, data))

        deezer_covers = _search_deezer_covers_static(self.artist, self.album)
        for label, data in deezer_covers:
            h = hash(data)
            if h not in seen_hashes:
                seen_hashes.add(h)
                covers.append((label, data))

        self.finished_covers.emit(covers[:6])