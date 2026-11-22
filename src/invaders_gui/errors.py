"""Global error handling: unexpected exceptions are logged and shown – never a crash."""

from __future__ import annotations

import contextlib
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from invaders.core.storage import default_data_dir

LOG_NAME = "invaders-gui-error.log"


def log_error(text: str, data_dir: Path | None = None) -> Path | None:
    try:
        directory = data_dir or default_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / LOG_NAME
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n{text}\n")
        return path
    except Exception:
        return None


def install_excepthook(show) -> None:
    """``show(title, message)`` is called on the GUI thread for unexpected errors."""

    def hook(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            from PySide6.QtWidgets import QApplication

            QApplication.quit()
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        path = log_error(text)
        with contextlib.suppress(Exception):
            show(
                "Wystąpił nieoczekiwany błąd",
                f"{exc_type.__name__}: {exc}\n\nAplikacja działa dalej."
                + (f"\nSzczegóły zapisano w:\n{path}" if path else ""),
            )

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        log_error(
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )

    sys.excepthook = hook
    threading.excepthook = thread_hook
