"""
Library Worker Thread

A generic worker thread for running database operations in background.
"""

from typing import Callable, Any
from PySide6.QtCore import QThread, Signal


class DataWorker(QThread):
    """A generic worker thread to run a function with args and emit results."""
    results_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            if self.isInterruptionRequested(): return
            result = self._func(*self._args, **self._kwargs)
            if self.isInterruptionRequested(): return
            self.results_ready.emit(result)
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))