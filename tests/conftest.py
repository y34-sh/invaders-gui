from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":  # the offscreen platform does not find system fonts by itself
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from pathlib import Path

import pytest

from invaders_gui.main_window import MainWindow
from invaders_gui.nav import KeyboardNavigator


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("INVADERS_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def messages() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def window(qtbot, qapp, data_dir: Path, messages) -> MainWindow:
    nav = KeyboardNavigator(qapp)
    qapp.installEventFilter(nav)
    win = MainWindow(data_dir=data_dir, splash_seconds=0.0)
    # dialogs would block the test – record them instead
    win.warn = lambda t, m: messages.append((t, m))
    win.info = lambda t, m: messages.append((t, m))
    win.confirm = lambda t, m: True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitUntil(lambda: win.ready, timeout=10_000)
    yield win
    win.game.stop()
    qapp.removeEventFilter(nav)
