from __future__ import annotations

import json
import random
import time
from pathlib import Path

import invaders.core.engine as core_engine
import pytest
from invaders.core.config import Difficulty
from invaders.core.engine import GameEngine
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication

from invaders_gui.game_page import GameOverDialog
from invaders_gui.main_window import MainWindow
from invaders_gui.pixelart import QUADRANTS, char_mask, sprite_image
from invaders_gui.workers import run_async


# --------------------------------------------------------------------- reuse of the core
def test_gui_uses_unchanged_console_engine(window: MainWindow) -> None:
    window.start_game(Difficulty.NORMAL)
    assert isinstance(window.game.engine, GameEngine)
    # the engine module comes from the console project, not from this package
    assert "invaders-gui" not in Path(core_engine.__file__).as_posix()
    assert Path(core_engine.__file__).parts[-3:] == ("invaders", "core", "engine.py")


# --------------------------------------------------------------------- startup / loading
def test_startup_shows_menu_after_loading(window: MainWindow) -> None:
    assert window.ready
    assert window.atlas is not None
    assert not window.overlay.isVisible()
    assert window.stack.currentWidget() is window.menu


def test_corrupted_files_give_warnings(qtbot, data_dir: Path, messages) -> None:
    (data_dir / "gui-settings.json").write_text("{oops", encoding="utf-8")
    (data_dir / "highscores.json").write_text("[[[", encoding="utf-8")
    win = MainWindow(data_dir=data_dir, splash_seconds=0.0)
    win.warn = lambda t, m: messages.append((t, m))
    qtbot.addWidget(win)
    assert win.overlay.isVisible() or not win.ready  # loading screen while starting
    qtbot.waitUntil(lambda: win.ready, timeout=10_000)
    assert len(messages) == 2
    assert win.settings.palette == "classic"


# --------------------------------------------------------------------- keyboard only
def test_keyboard_only_menu_navigation(qtbot, window: MainWindow) -> None:
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)  # Ranking
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: window.stack.currentWidget() is window.pages["ranking"])
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert window.stack.currentWidget() is window.menu
    qtbot.keyClick(window.menu, Qt.Key.Key_S)  # shortcut -> settings
    assert window.stack.currentWidget() is window.pages["settings"]


def test_keyboard_only_game(qtbot, window: MainWindow) -> None:
    window.open_page("new")
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)  # Enter on radio = start
    game = window.game
    assert window.stack.currentWidget() is game
    game.engine.state.transition_timer = 0.0
    x0 = game.engine.state.player.x
    qtbot.keyPress(game.view, Qt.Key.Key_Right)
    qtbot.wait(300)
    qtbot.keyRelease(game.view, Qt.Key.Key_Right)
    assert game.engine.state.player.x > x0
    qtbot.keyClick(game.view, Qt.Key.Key_Space)
    qtbot.wait(100)
    assert game.engine.state.stats.shots_fired >= 1
    qtbot.keyClick(game.view, Qt.Key.Key_Escape)
    assert game.paused and game.overlay.isVisible()
    frozen = game.engine.state.time
    qtbot.wait(200)
    assert game.engine.state.time == frozen
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert not game.paused
    qtbot.wait(100)
    assert game.engine.state.time > frozen


# --------------------------------------------------------------------- mouse only
def test_mouse_only_game(qtbot, window: MainWindow) -> None:
    menu_new = window.menu.buttons["new"]
    qtbot.mouseClick(menu_new, Qt.MouseButton.LeftButton)
    page = window.pages["new"]
    qtbot.mouseClick(page.radios[Difficulty.EASY], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.start_button, Qt.MouseButton.LeftButton)
    game = window.game
    assert game.difficulty is Difficulty.EASY
    game.engine.state.transition_timer = 0.0
    view = game.view
    target = QPoint(int(view.width() * 0.2), int(view.height() * 0.5))
    qtbot.mouseMove(view, target)
    qtbot.wait(1500)
    assert abs(game.engine.state.player.center_x - view.world_x(target.x())) < 1.5
    qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=target)
    qtbot.wait(100)
    assert game.engine.state.stats.shots_fired >= 1
    qtbot.mouseClick(game.pause_button, Qt.MouseButton.LeftButton)
    assert game.paused
    qtbot.mouseClick(game.menu_button, Qt.MouseButton.LeftButton)  # confirm patched -> yes
    assert window.stack.currentWidget() is window.menu


# --------------------------------------------------------------------- long operations
def test_analysis_runs_async_and_ui_stays_responsive(qtbot, window: MainWindow) -> None:
    page = window.pages["analysis"]
    window.open_page("analysis")
    page.games.setValue(5)
    page.seconds.setValue(300)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start(20)
    t0 = time.monotonic()
    page.run()
    assert window.overlay.isVisible()  # loading spinner during the operation
    qtbot.waitUntil(lambda: window.current_job is None, timeout=120_000)
    timer.stop()
    duration = time.monotonic() - t0
    assert duration > 0.3, "operation should be long enough to be meaningful"
    assert page.table.rowCount() == 3
    assert len(page.chart.bars) == 3
    # the event loop kept running smoothly during the computation (20 ms timer)
    assert len(ticks) >= 0.4 * duration / 0.02, (len(ticks), duration)
    assert not window.overlay.isVisible()


def test_analysis_can_be_cancelled(qtbot, window: MainWindow) -> None:
    page = window.pages["analysis"]
    window.open_page("analysis")
    page.games.setValue(50)
    page.run()
    qtbot.wait(100)
    qtbot.keyClick(window.overlay, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: window.current_job is None, timeout=20_000)
    assert page.table.rowCount() == 0


def test_worker_error_is_reported_not_raised(qtbot, window: MainWindow, messages) -> None:
    def boom(job):
        raise ValueError("zły plik")

    window.run_long("Test…", boom)
    qtbot.waitUntil(lambda: window.current_job is None, timeout=5000)
    assert any("zły plik" in m for _, m in messages)


def test_second_long_operation_is_refused_while_busy(qtbot, window: MainWindow) -> None:
    job = window.run_long("A…", lambda j: time.sleep(0.3))
    assert job is not None
    assert window.run_long("B…", lambda j: None) is None
    qtbot.waitUntil(lambda: window.current_job is None, timeout=5000)


def test_palette_change_rebuilds_graphics_async(qtbot, window: MainWindow, data_dir) -> None:
    old = window.atlas
    window.update_settings(palette="neon")
    qtbot.waitUntil(lambda: window.atlas is not old, timeout=10_000)
    assert window.atlas.palette_key == "neon"
    qtbot.waitUntil(lambda: (data_dir / "gui-settings.json").exists(), timeout=5000)
    assert json.loads((data_dir / "gui-settings.json").read_text())["palette"] == "neon"


# --------------------------------------------------------------------- game over
def test_game_over_dialog_saves_initials(qtbot, window: MainWindow, data_dir: Path) -> None:
    window.start_game(Difficulty.NORMAL)
    state = window.game.engine.state
    state.score = 1200

    def interact() -> None:
        dlg = QApplication.activeModalWidget()
        assert isinstance(dlg, GameOverDialog)
        for key in (Qt.Key.Key_Up, Qt.Key.Key_Right, Qt.Key.Key_Z, Qt.Key.Key_Return):
            qtbot.keyClick(dlg.picker, key)
        qtbot.waitUntil(lambda: (data_dir / "highscores.json").exists(), timeout=5000)
        qtbot.mouseClick(dlg.menu, Qt.MouseButton.LeftButton)

    QTimer.singleShot(50, interact)
    dialog = GameOverDialog(window, state)
    assert dialog.exec_and_result() == "menu"
    saved = json.loads((data_dir / "highscores.json").read_text(encoding="utf-8"))
    assert saved["entries"][0]["initials"] == "BZA"
    assert window.last_rank == 0


# --------------------------------------------------------------------- robustness
@pytest.mark.parametrize("seed", [1, 2])
def test_monkey_keys_and_clicks(qtbot, window: MainWindow, seed: int) -> None:
    rng = random.Random(seed)
    keys = [
        Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Space,
        Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_P, Qt.Key.Key_Tab, Qt.Key.Key_A,
        Qt.Key.Key_N, Qt.Key.Key_R, Qt.Key.Key_X, Qt.Key.Key_1, Qt.Key.Key_F5, Qt.Key.Key_Delete,
    ]  # fmt: skip
    window.start_game(Difficulty.HARD)
    for _ in range(400):
        target = QApplication.focusWidget() or window
        if QApplication.activeModalWidget() is not None:
            QApplication.activeModalWidget().reject()
            continue
        if window.current_job is not None:
            window.cancel_job()
        roll = rng.random()
        if roll < 0.75:
            qtbot.keyClick(target, rng.choice(keys))
        else:
            w = window.centralWidget()
            pos = QPoint(rng.randrange(max(1, w.width())), rng.randrange(max(1, w.height())))
            child = w.childAt(pos) or w
            qtbot.mouseClick(child, Qt.MouseButton.LeftButton, pos=child.mapFrom(w, pos))
        if rng.random() < 0.02:
            window.resize(rng.randrange(720, 1400), rng.randrange(560, 1000))
    qtbot.waitUntil(lambda: window.current_job is None, timeout=30_000)


def test_focus_loss_pauses_game(qtbot, window: MainWindow) -> None:
    window.start_game(Difficulty.NORMAL)
    from PySide6.QtCore import QEvent

    window.isActiveWindow = lambda: False  # simulate deactivation
    window.changeEvent(QEvent(QEvent.Type.ActivationChange))
    assert window.game.paused


# --------------------------------------------------------------------- pixel art
def test_quadrant_characters_map_to_pixels() -> None:
    assert char_mask("█") == (15, 1.0)
    assert char_mask("▚")[0] == QUADRANTS["▘"] | QUADRANTS["▗"]
    img = sprite_image(("▗▛▜▖", "▘▚▞▝"), "#FF0000")
    assert (img.width(), img.height()) == (8, 4)
    assert img.pixelColor(1, 1).alpha() == 255  # ▗ bottom-right pixel
    assert img.pixelColor(0, 0).alpha() == 0


def test_run_async_delivers_result(qtbot) -> None:
    got = []
    run_async(lambda job: 6 * 7, on_result=got.append)
    qtbot.waitUntil(lambda: got == [42], timeout=5000)
