from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class AsyncWorker(QThread):

    finished_with_result = pyqtSignal(object)
    finished_with_error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled:
                return
            result = self._func(*self._args, **self._kwargs)
            if not self._is_cancelled:
                self.finished_with_result.emit(result)
        except Exception as e:
            if not self._is_cancelled:
                self.finished_with_error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True

    def __del__(self):

        try:
            self._is_cancelled = True
        except Exception:
            pass
