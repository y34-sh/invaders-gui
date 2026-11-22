"""Game page (HUD + canvas + pause overlay) and the game-over dialog."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from invaders.core import config
from invaders.core.config import Difficulty
from invaders.core.engine import GameEngine, GameState
from invaders.core.events import ExtraLife, GameOver, UfoKilled, WaveCleared
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .pages import button, label
from .widgets.game_view import GameView
from .widgets.initials import InitialsPicker

if TYPE_CHECKING:
    from .main_window import MainWindow

FRAME_MS = 16
GAME_OVER_DELAY_MS = 1500


class GamePage(QWidget):
    toMenu = Signal()

    def __init__(self, win: MainWindow) -> None:
        super().__init__()
        self.win = win
        self.engine: GameEngine | None = None
        self.difficulty = Difficulty.NORMAL
        self.paused = False
        self._last = time.monotonic()
        self._hud_cache: tuple | None = None
        self._game_over_pending = False
        self._fps_frames = 0
        self._fps_time = time.monotonic()
        self._fps = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        hud = QFrame()
        hud.setObjectName("Hud")
        h = QHBoxLayout(hud)
        h.setContentsMargins(18, 8, 18, 8)
        self.values: dict[str, QLabel] = {}
        for key, title, style in (
            ("score", "WYNIK", "HudValue"),
            ("best", "REKORD", "HudAccent"),
            ("wave", "FALA", "HudValue"),
            ("lives", "ŻYCIA", "Lives"),
            ("level", "POZIOM", "HudAccent"),
            ("fps", "FPS", "HudValue"),
        ):
            t = QLabel(title)
            t.setObjectName("HudLabel")
            v = QLabel("–")
            v.setObjectName(style)
            h.addWidget(t)
            h.addWidget(v)
            h.addSpacing(18)
            self.values[key] = v
            if key == "fps":
                self._fps_title = t
        h.addStretch(1)
        self.pause_button = QPushButton("‖  Pauza (Esc)")
        self.pause_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep focus on the game
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.clicked.connect(lambda _checked=False: self.pause())
        h.addWidget(self.pause_button)
        root.addWidget(hud)

        self.view = GameView()
        self.view.pauseRequested.connect(self.toggle_pause)
        root.addWidget(self.view, 1)

        # pause overlay
        self.overlay = QFrame(self)
        self.overlay.setObjectName("Card")
        ov = QVBoxLayout(self.overlay)
        ov.setContentsMargins(36, 28, 36, 28)
        ov.addWidget(label("‖  PAUZA", "PageTitle"), alignment=Qt.AlignmentFlag.AlignCenter)
        self.overlay_reason = label("", "Hint")
        self.overlay_reason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ov.addWidget(self.overlay_reason)
        self.resume_button = button("▶  Wznów (Esc)", "Primary")
        self.restart_button = button("↻  Restart (R)")
        self.menu_button = button("⌂  Menu główne (M)")
        for b in (self.resume_button, self.restart_button, self.menu_button):
            ov.addWidget(b)
        self.resume_button.clicked.connect(self.resume)
        self.restart_button.clicked.connect(self.confirm_restart)
        self.menu_button.clicked.connect(self.confirm_menu)
        self.overlay.hide()
        self.overlay.installEventFilter(self)

        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self._frame)

    # ------------------------------------------------------------------ lifecycle -------
    def new_game(self, difficulty: Difficulty) -> None:
        self.difficulty = difficulty
        self.engine = GameEngine(difficulty)
        self._game_over_pending = False
        self._hud_cache = None
        self.view.set_engine(self.engine)
        self.apply_look()
        self.overlay.hide()
        self.paused = False
        self._last = time.monotonic()
        self.timer.start()
        self.view.setFocus()
        self._update_hud()

    def apply_look(self) -> None:
        s = self.win.settings
        if self.win.atlas is not None:
            self.view.set_look(self.win.palette, self.win.atlas, s.stars)
        self.values["fps"].setVisible(s.show_fps)
        self._fps_title.setVisible(s.show_fps)
        self._hud_cache = None

    def stop(self) -> None:
        self.timer.stop()
        self.overlay.hide()
        self.paused = False

    @property
    def running(self) -> bool:
        return (
            self.engine is not None
            and self.timer.isActive()
            and not self.paused
            and not self.engine.state.is_over
        )

    @property
    def in_progress(self) -> bool:
        return self.engine is not None and self.timer.isActive() and not self.engine.state.is_over

    # ------------------------------------------------------------------ loop ------------
    def _frame(self) -> None:
        now = time.monotonic()
        dt, self._last = now - self._last, now
        if self.paused or self.engine is None:
            return
        try:
            events = self.engine.step(min(dt, config.MAX_FRAME_DT), self.view.commands())
            for ev in events:
                if isinstance(ev, GameOver) and not self._game_over_pending:
                    self._game_over_pending = True
                    QTimer.singleShot(GAME_OVER_DELAY_MS, self._show_game_over)
                elif isinstance(ev, ExtraLife):
                    self.win.toast("Dodatkowe życie!")
                elif isinstance(ev, UfoKilled):
                    self.win.toast(f"UFO zestrzelone! +{ev.points}")
                elif isinstance(ev, WaveCleared):
                    self.win.toast(f"Fala {ev.wave} pokonana!")
            self.view.update()
            self._update_hud()
        except Exception:
            # Last line of defence – stop the loop and report instead of crashing.
            self.timer.stop()
            raise

    def _update_hud(self) -> None:
        if self.engine is None:
            return
        self._fps_frames += 1
        now = time.monotonic()
        if now - self._fps_time >= 1.0:
            self._fps = round(self._fps_frames / (now - self._fps_time))
            self._fps_frames, self._fps_time = 0, now
        s = self.engine.state
        best = max(self.win.highscores.best, s.score)
        values = (s.score, best, s.wave, s.lives, self.difficulty.label, self._fps)
        if values == self._hud_cache:
            return
        self._hud_cache = values
        self.values["score"].setText(f"{s.score:06d}")
        self.values["best"].setText(f"{best:06d}")
        self.values["wave"].setText(str(s.wave))
        self.values["lives"].setText("▲ " * s.lives or "–")
        self.values["level"].setText(self.difficulty.label)
        self.values["fps"].setText(str(self._fps))

    # ------------------------------------------------------------------ pause -----------
    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def pause(self, reason: str = "") -> None:
        if self.engine is None or self.engine.state.is_over or self.paused:
            return
        self.paused = True
        self.view.reset_input()
        self.overlay_reason.setText(reason)
        self.overlay_reason.setVisible(bool(reason))
        self._place_overlay()
        self.overlay.show()
        self.overlay.raise_()
        self.resume_button.setFocus()

    def resume(self) -> None:
        if not self.paused:
            return
        self.paused = False
        self._last = time.monotonic()  # no dt accumulated while paused
        self.overlay.hide()
        self.view.setFocus()

    def confirm_restart(self) -> None:
        if self.win.confirm("Restart", "Zacząć od nowa? Bieżąca gra zostanie utracona."):
            self.new_game(self.difficulty)

    def confirm_menu(self) -> None:
        if self.win.confirm("Menu główne", "Wyjść do menu? Bieżąca gra zostanie utracona."):
            self.stop()
            self.toMenu.emit()

    def eventFilter(self, obj, event) -> bool:  # keyboard on the pause overlay
        if obj is self.overlay and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Escape, Qt.Key.Key_P):
                self.resume()
                return True
            if key == Qt.Key.Key_R:
                self.confirm_restart()
                return True
            if key == Qt.Key.Key_M:
                self.confirm_menu()
                return True
        return False

    def keyPressEvent(self, event) -> None:
        if self.paused and event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_P):
            self.resume()
        elif self.paused and event.key() == Qt.Key.Key_R:
            self.confirm_restart()
        elif self.paused and event.key() == Qt.Key.Key_M:
            self.confirm_menu()
        else:
            super().keyPressEvent(event)

    def _place_overlay(self) -> None:
        w, h = 380, 330
        self.overlay.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def resizeEvent(self, event) -> None:
        self._place_overlay()
        super().resizeEvent(event)

    # ------------------------------------------------------------------ game over -------
    def _show_game_over(self) -> None:
        if self.engine is None or not self.isVisible():
            return
        self.timer.stop()
        dialog = GameOverDialog(self.win, self.engine.state)
        result = dialog.exec_and_result()
        if result == "again":
            self.new_game(self.difficulty)
        elif result == "ranking":
            self.toMenu.emit()
            self.win.open_page("ranking")
        else:
            self.toMenu.emit()


class GameOverDialog(QDialog):
    def __init__(self, win: MainWindow, state: GameState) -> None:
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Koniec gry")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.state = state
        self.choice = "menu"
        self.saved = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        title = label("KONIEC GRY", "PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        reason = state.game_over_reason.value if state.game_over_reason else ""
        info = label(
            f"<p align='center'><i>{reason}</i><br/><br/>"
            f"Wynik: <b style='font-size:22px'>{state.score}</b><br/>"
            f"Fala: <b>{state.wave}</b> · Zabici kosmici: <b>{state.stats.aliens_killed}</b> · "
            f"Celność: <b>{state.stats.accuracy:.0f}%</b></p>"
        )
        lay.addWidget(info)
        self.qualifies = win.highscores.qualifies(state.score)
        self.picker: InitialsPicker | None = None
        if self.qualifies:
            lay.addWidget(label("★ Nowy rekord w TOP 10! Wybierz inicjały:", "HudLabel"))
            self.picker = InitialsPicker()
            self.picker.submitted.connect(self._save)
            lay.addWidget(self.picker, alignment=Qt.AlignmentFlag.AlignCenter)
            self.save_button = button("Zapisz wynik (Enter)", "Primary")
            self.save_button.setAutoDefault(False)
            self.save_button.clicked.connect(lambda: self._save(self.picker.value))
            lay.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(label("↑↓ litera · ←→ pozycja · możesz też pisać · mysz: ▲▼", "Hint"))
        self.status = label("", "Hint")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.again = button("↻ Zagraj ponownie")
        self.ranking = button("★ Ranking")
        self.menu = button("⌂ Menu (Esc)")
        for b, key in ((self.again, "again"), (self.ranking, "ranking"), (self.menu, "menu")):
            b.clicked.connect(lambda _=False, k=key: self._finish(k))
            b.setAutoDefault(False)
            row.addWidget(b)
        lay.addLayout(row)
        if self.picker is not None:
            self.picker.setFocus()
        else:
            self.again.setFocus()

    def _save(self, initials: str) -> None:
        if self.saved:
            return
        self.saved = True
        self.save_button.setEnabled(False)
        self.picker.setEnabled(False)
        self.status.setText("Zapisywanie…")

        def done(rank) -> None:
            self.status.setText(
                f"Zapisano: {initials} – miejsce {rank + 1}!" if rank is not None else "Zapisano."
            )
            self.again.setFocus()

        self.win.save_highscore(initials, self.state, done)

    def _finish(self, choice: str) -> None:
        self.choice = choice
        self.accept()

    def reject(self) -> None:  # Esc / window close = back to menu
        self.choice = "menu"
        super().reject()

    def exec_and_result(self) -> str:
        self.exec()
        return self.choice
