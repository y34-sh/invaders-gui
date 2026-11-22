"""Entry point: ``python -m invaders_gui``."""

from __future__ import annotations

import signal
import sys


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .errors import install_excepthook
    from .main_window import MainWindow
    from .nav import KeyboardNavigator

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Invaders")
    window = MainWindow()

    def show_error(title: str, text: str) -> None:
        QMessageBox.critical(window, title, text)

    install_excepthook(show_error)
    navigator = KeyboardNavigator(app)
    app.installEventFilter(navigator)
    # Ctrl+C in the console: close gracefully (Python needs the event loop to wake up)
    signal.signal(signal.SIGINT, lambda *_: window.close())
    pulse = QTimer()
    pulse.start(250)
    pulse.timeout.connect(lambda: None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
