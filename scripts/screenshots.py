"""Save PNG screenshots of every page into docs/screenshots (offscreen, no display needed).

Usage:  uv run python scripts/screenshots.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from invaders.core.config import Difficulty
from invaders.core.highscores import HighScoreTable
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from invaders_gui.main_window import MainWindow

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> None:
    app = QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    win = MainWindow(data_dir=Path(tempfile.mkdtemp()), splash_seconds=0.6)
    win.warn = win.info = lambda *a: None
    win.resize(1100, 760)
    win.show()

    def shot(name: str, ms: int = 250) -> None:
        wait(ms)
        win.grab().save(str(OUT / f"{name}.png"))

    shot("00_loading", 120)
    while not win.ready:
        wait(50)
    table = HighScoreTable()
    for i, (n, s) in enumerate([("ACE", 4210), ("ZED", 2980), ("KOT", 1750), ("MAX", 940)]):
        table.add(n, s, 4 - i, "normal")
    win.highscores = table
    win.last_rank = 2
    shot("01_menu")
    for key, name in [
        ("new", "02_new_game"),
        ("ranking", "05_ranking"),
        ("settings", "07_settings"),
        ("help", "08_help"),
        ("about", "09_about"),
    ]:
        win.open_page(key)
        shot(name)
    win.open_page("analysis")
    page = win.pages["analysis"]
    page.games.setValue(3)
    page.seconds.setValue(120)
    page.run()
    shot("06a_analysis_running", 300)
    while win.current_job is not None:
        wait(100)
    shot("06_analysis")
    win.start_game(Difficulty.NORMAL)
    game = win.game
    shot("03a_wave", 400)
    game.engine.state.transition_timer = 0.0
    from invaders.core.commands import Command

    for i in range(150):
        game.engine.step(
            1 / 60, {Command.FIRE, Command.MOVE_LEFT if i < 60 else Command.MOVE_RIGHT}
        )
    shot("03_game", 300)
    game.pause()
    shot("04_pause")
    game.resume()
    game.timer.stop()
    from invaders_gui.game_page import GameOverDialog

    game.engine.state.score = 3333
    dlg = GameOverDialog(win, game.engine.state)
    dlg.show()
    wait(250)
    dlg.grab().save(str(OUT / "04b_game_over.png"))
    dlg.close()
    win.close()
    app.quit()
    print("saved to", OUT)


if __name__ == "__main__":
    main()
