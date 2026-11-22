"""Background jobs: long operations never run on the GUI thread.

``run_async(fn, on_result=..., on_error=..., on_progress=...)`` executes ``fn`` in Qt's
global thread pool. ``fn`` receives a ``Job`` it can use to report progress and check
for cancellation. Results/errors come back to the GUI thread through Qt signals.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class Cancelled(Exception):
    """Raised inside a job when the user pressed "Anuluj"."""


class _Signals(QObject):
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(object, str)  # exception, formatted traceback
    finished = Signal()


class Job(QRunnable):
    def __init__(self, fn: Callable[[Job], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self._cancel = threading.Event()
        self.done = threading.Event()
        self.setAutoDelete(False)

    # --- API for the job function ------------------------------------------------------
    def report(self, percent: int, message: str = "") -> None:
        self.signals.progress.emit(max(0, min(100, int(percent))), message)

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # --- API for the GUI ---------------------------------------------------------------
    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:  # executed in a worker thread
        try:
            value = self.fn(self)
        except Exception as exc:
            self.signals.error.emit(exc, traceback.format_exc())
        else:
            self.signals.result.emit(value)
        finally:
            self.done.set()
            self.signals.finished.emit()


_ACTIVE: set[Job] = set()  # keep Python wrappers alive until the job is finished


def run_async(
    fn: Callable[[Job], Any],
    *,
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[BaseException, str], None] | None = None,
    on_progress: Callable[[int, str], None] | None = None,
    on_finished: Callable[[], None] | None = None,
) -> Job:
    job = Job(fn)
    if on_result:
        job.signals.result.connect(on_result)
    if on_error:
        job.signals.error.connect(on_error)
    if on_progress:
        job.signals.progress.connect(on_progress)
    if on_finished:
        job.signals.finished.connect(on_finished)
    _ACTIVE.add(job)
    job.signals.finished.connect(lambda: _ACTIVE.discard(job))
    QThreadPool.globalInstance().start(job)
    return job
