"""Main window: page stack, loading overlay, settings/highscores, async helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from invaders.core.errors import InvadersError
from invaders.core.highscores import FILE_NAME as HS_FILE
from invaders.core.highscores import HighScoreStore, HighScoreTable
from invaders.core.storage import default_data_dir
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from .errors import log_error
from .game_page import GamePage
from .pages import (
    AnalysisPage,
    HighscoresPage,
    MenuPage,
    NewGamePage,
    Page,
    SettingsPage,
    about_page,
    help_page,
)
from .pixelart import SpriteAtlas, build_atlas
from .settings import FILE_NAME as SETTINGS_FILE
from .settings import GuiSettings, GuiSettingsStore
from .theme import GuiPalette, get_palette, stylesheet
from .workers import Cancelled, Job, run_async

MIN_SPLASH_SECONDS = 1.2


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path | None = None, *, splash_seconds: float = MIN_SPLASH_SECONDS):
        super().__init__()
        self.data_dir = data_dir or default_data_dir()
        self.settings_store = GuiSettingsStore(self.data_dir / SETTINGS_FILE)
        # Same file as the console version -> one shared ranking.
        self.highscore_store = HighScoreStore(self.data_dir / HS_FILE)
        self.settings = GuiSettings()
        self.highscores = HighScoreTable()
        self.last_rank: int | None = None
        self.atlas: SpriteAtlas | None = None
        self.current_job: Job | None = None
        self.ready = False
        self.splash_seconds = splash_seconds

        self.setWindowTitle("Invaders")
        self.resize(1100, 760)
        self.setMinimumSize(720, 560)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        self.stack = QStackedWidget(root)
        from PySide6.QtWidgets import QVBoxLayout

        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)

        from .widgets.loading import LoadingOverlay

        self.overlay = LoadingOverlay(root, self.palette)
        self.overlay.cancelRequested.connect(self.cancel_job)
        self.toast_label = QLabel(root)
        self.toast_label.setObjectName("Card")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()
        self._toast_timer = QTimer(self, singleShot=True, interval=1800)
        self._toast_timer.timeout.connect(self.toast_label.hide)

        self.pages: dict[str, QWidget] = {}
        self.menu = MenuPage(self)
        self.menu.chosen.connect(self.menu_choice)
        self.game = GamePage(self)
        self.game.toMenu.connect(lambda: self.open_page("menu"))
        self._add("menu", self.menu)
        self._add("new", NewGamePage(self))
        self._add("game", self.game)
        self._add("ranking", HighscoresPage(self))
        self._add("analysis", AnalysisPage(self))
        self._add("settings", SettingsPage(self))
        self._add("help", help_page(self))
        self._add("about", about_page(self))
        self.pages["new"].start.connect(self.start_game)

        self._menu_anim = QTimer(self, interval=500)
        self._menu_anim.timeout.connect(self.menu.tick_animation)
        self._menu_anim.start()

        for keys, slot in (
            ("Ctrl+Q", self.close),
            ("F11", self.toggle_fullscreen),
            ("F1", lambda: self.open_page("help")),
        ):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(slot)

        self.apply_style()
        QTimer.singleShot(0, self.startup)

    # ------------------------------------------------------------------ look ------------
    @property
    def palette(self) -> GuiPalette:
        return get_palette(self.settings.palette)

    def apply_style(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet(self.palette))
        self.overlay.set_palette(self.palette)

    def _add(self, key: str, page: QWidget) -> None:
        self.pages[key] = page
        self.stack.addWidget(page)
        if isinstance(page, Page):
            page.back.connect(lambda: self.open_page("menu"))

    # ------------------------------------------------------------------ startup ---------
    def startup(self) -> None:
        self.overlay.start("Uruchamianie gry…", opaque=True)
        settings_store, hs_store = self.settings_store, self.highscore_store
        min_time = self.splash_seconds

        def work(job: Job) -> dict[str, Any]:
            t0 = time.monotonic()
            job.report(5, "Wczytywanie ustawień")
            settings, s_warn = settings_store.load()
            job.report(15, "Wczytywanie rankingu")
            table, h_warn = hs_store.load()
            atlas = build_atlas(
                get_palette(settings.palette),
                progress=lambda pct, what: job.report(20 + pct * 0.75, f"Grafika: {what}"),
            )
            job.report(100, "Gotowe")
            rest = min_time - (time.monotonic() - t0)
            if rest > 0:  # keep the splash readable on fast machines
                time.sleep(rest)
            return {
                "settings": settings,
                "table": table,
                "atlas": atlas,
                "warnings": [w for w in (s_warn, h_warn) if w],
            }

        self.run_long("Uruchamianie gry…", work, self._started, opaque=True)

    def _started(self, data: dict[str, Any]) -> None:
        self.settings = data["settings"]
        self.highscores = data["table"]
        self.atlas = data["atlas"]
        self.apply_style()
        if self.settings.fullscreen:
            self.showFullScreen()
        self.ready = True
        self.open_page("menu")
        for w in data["warnings"]:
            self.warn("Pliki zapisu", w)

    # ------------------------------------------------------------------ async helper ----
    def run_long(
        self,
        message: str,
        fn: Callable[[Job], Any],
        on_result: Callable[[Any], None] | None = None,
        *,
        cancellable: bool = False,
        opaque: bool = False,
    ) -> Job | None:
        """Run ``fn`` in a worker thread with the loading overlay on top of the UI."""
        if self.current_job is not None:
            self.toast("Poczekaj na zakończenie bieżącej operacji")
            return None
        focus = QApplication.focusWidget()
        self.overlay.start(message, cancellable=cancellable, opaque=opaque)

        def finished() -> None:
            self.current_job = None
            self.overlay.stop()
            if focus is not None and focus.isVisible():
                focus.setFocus()

        def failed(exc: BaseException, tb: str) -> None:
            if isinstance(exc, Cancelled):
                self.toast("Operację anulowano")
            elif isinstance(exc, (InvadersError, OSError)):
                self.warn("Operacja nie powiodła się", str(exc))
            else:
                path = log_error(tb, self.data_dir)
                self.warn("Wystąpił błąd", f"{type(exc).__name__}: {exc}\nLog: {path}")

        def succeeded(value: Any) -> None:
            if on_result is not None:
                try:
                    on_result(value)
                except InvadersError as exc:
                    self.warn("Uwaga", exc.message)

        self.current_job = run_async(
            fn,
            on_result=succeeded,
            on_error=failed,
            on_progress=self.overlay.progress,
            on_finished=finished,
        )
        return self.current_job

    def cancel_job(self) -> None:
        if self.current_job is not None:
            self.current_job.cancel()
            self.overlay.message = "Anulowanie…"

    # ------------------------------------------------------------------ navigation ------
    def open_page(self, key: str) -> None:
        if not self.ready or key not in self.pages:
            return
        if key != "game" and self.stack.currentWidget() is self.game:
            self.game.stop()
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_show"):
            page.on_show()

    def menu_choice(self, key: str) -> None:
        if key == "quit":
            self.close()
        else:
            self.open_page(key)

    def start_game(self, difficulty) -> None:
        if self.settings.difficulty != difficulty.value:
            self.update_settings(difficulty=difficulty.value)
        self.last_rank = None
        self.stack.setCurrentWidget(self.game)
        self.game.new_game(difficulty)

    # ------------------------------------------------------------------ settings --------
    def update_settings(self, **changes: Any) -> None:
        new = self.settings.with_changes(**changes)
        if new == self.settings:
            return
        palette_changed = new.palette != self.settings.palette
        old = self.settings
        self.settings = new
        if new.fullscreen != old.fullscreen:
            self.showFullScreen() if new.fullscreen else self.showNormal()
        store = self.settings_store

        def work(job: Job) -> SpriteAtlas | None:
            store.save(new)  # atomic JSON write (may raise StorageError)
            if palette_changed:
                return build_atlas(
                    get_palette(new.palette),
                    progress=lambda pct, what: job.report(pct, f"Grafika: {what}"),
                )
            return None

        def done(atlas: SpriteAtlas | None) -> None:
            if atlas is not None:
                self.atlas = atlas
            self.apply_style()
            for page in self.pages.values():
                if hasattr(page, "refresh_look"):
                    page.refresh_look()
            self.game.apply_look()
            self.menu.tick_animation()

        if palette_changed:
            self.run_long("Przerysowywanie grafiki…", work, done)
        else:
            # small change: save in the background without blocking the screen
            run_async(work, on_result=done, on_error=lambda e, tb: self.warn("Zapis", str(e)))

    def toggle_fullscreen(self) -> None:
        self.update_settings(fullscreen=not self.settings.fullscreen)

    # ------------------------------------------------------------------ highscores ------
    def save_highscore(self, initials: str, state, on_done: Callable[[int | None], None]) -> None:
        rank = self.highscores.add(initials, state.score, state.wave, state.difficulty.value)
        self.last_rank = rank
        table, store = self.highscores, self.highscore_store
        run_async(
            lambda job: store.save(table),
            on_result=lambda _r: on_done(rank),
            on_error=lambda e, tb: (self.warn("Ranking", str(e)), on_done(rank)),
        )

    # ------------------------------------------------------------------ feedback --------
    def toast(self, text: str) -> None:
        self.toast_label.setText(f"  {text}  ")
        self.toast_label.adjustSize()
        w = self.toast_label.width() + 30
        self.toast_label.setGeometry((self.centralWidget().width() - w) // 2, 70, w, 44)
        self.toast_label.raise_()
        self.toast_label.show()
        self._toast_timer.start()

    def warn(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def info(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)

    def confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------ window events ---
    def resizeEvent(self, event) -> None:
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.centralWidget().rect())
        super().resizeEvent(event)

    def changeEvent(self, event) -> None:
        if (
            event.type() == QEvent.Type.ActivationChange
            and not self.isActiveWindow()
            and self.game.running
            and QApplication.activeModalWidget() is None
        ):
            self.game.pause("Gra wstrzymana – okno straciło fokus.")
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        if self.game.in_progress:
            was_running = self.game.running
            if was_running:
                self.game.pause()
            if not self.confirm("Wyjście", "Gra trwa. Na pewno chcesz wyjść?"):
                event.ignore()
                return
        if self.current_job is not None:
            self.current_job.cancel()
            self.current_job.done.wait(2.0)
        self.game.stop()
        event.accept()
