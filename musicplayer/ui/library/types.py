"""
Library Types and Constants

Contains data structures and column definitions for the library view.
"""

from typing import List

COL_TITLE = 0
COL_ARTIST = 1
COL_ALBUM = 2
COL_GENRE = 3
COL_FOLDER = 4
COL_DURATION = 5
COL_BITRATE = 6
COL_PLAY_COUNT = 7
COL_FAVORITE = 8
COL_MOOD = 9
COLUMN_COUNT = 10

HEADERS = ["Название", "Артист", "Альбом", "Жанр", "Папка", "Длительность", "Битрейт", "Топ", "♡", "★"]


class Track:
    """Lightweight data class for tracks displayed in the UI."""
    __slots__ = ('filepath', 'title', 'artist', 'album', 'genre',
                 'duration', 'bitrate', 'folder', 'play_count',
                 'tempo', 'energy', 'mood', 'is_favorite')

    def __init__(self, filepath, title, artist, album, genre,
                 duration, bitrate, folder, play_count,
                 tempo, energy, mood, is_favorite=False):
        self.filepath = filepath
        self.title = title
        self.artist = artist
        self.album = album
        self.genre = genre
        self.duration = duration
        self.bitrate = bitrate
        self.folder = folder
        self.play_count = play_count
        self.tempo = tempo
        self.energy = energy
        self.mood = mood
        self.is_favorite = is_favorite