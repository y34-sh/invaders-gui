"""All non-game pages. Each one is fully usable with the mouse or the keyboard alone."""

from __future__ import annotations

import csv
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from typing import TYPE_CHECKING

from invaders import __version__ as core_version
from invaders.core.config import Difficulty
from invaders.core.entities import AlienKind
from invaders.core.highscores import HighScoreTable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .bot import GameResult, simulate_game
from .theme import PALETTES
from .widgets.chart import BarChart

if TYPE_CHECKING:
    from .main_window import MainWindow

DIFF_ORDER = (Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD)


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(32, 28, 32, 28)
    layout.setSpacing(14)
    return frame, layout


def label(text: str, name: str | None = None) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def button(text: str, name: str | None = None, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def scaled(image, pixel: int) -> QPixmap:
    """Scale pixel art by an integer factor (``pixel`` screen px per sprite pixel)."""
    pix = QPixmap.fromImage(image)
    return pix.scaled(
        image.width() * pixel,
        image.height() * pixel,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def stepper(spin: QSpinBox) -> QWidget:
    """Spin box with big −/+ buttons (mouse-friendly; keyboard uses ↑↓ in the field)."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    minus = button("−", "Small", "Zmniejsz")
    plus = button("+", "Small", "Zwiększ")
    for b in (minus, plus):
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setAutoRepeat(True)
    minus.clicked.connect(spin.stepDown)
    plus.clicked.connect(spin.stepUp)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
    spin.setMinimumWidth(140)
    row.addWidget(minus)
    row.addWidget(spin, 1)
    row.addWidget(plus)
    return box


class Page(QWidget):
    """Base page: centred card, Esc = back."""

    back = Signal()

    def __init__(self, win: MainWindow, width: int = 760) -> None:
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.card, self.body = card()
        self.card.setMaximumWidth(width)
        self.card.setMinimumWidth(min(width, 680))
        row.addWidget(self.card, 3)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def shortcut(self, keys: str, slot) -> QShortcut:
        sc = QShortcut(QKeySequence(keys), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(slot)
        return sc

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.back.emit()
            return
        super().keyPressEvent(event)

    def on_show(self) -> None:
        """Called by the window whenever the page becomes current."""

    def refresh_look(self) -> None:
        """Called after the palette changed."""


# ======================================================================================
class MenuPage(Page):
    ITEMS = (
        ("new", "▶   Nowa gra", "N"),
        ("ranking", "★   Ranking", "R"),
        ("analysis", "▤   Analiza trudności", "A"),
        ("settings", "⚙   Ustawienia", "S"),
        ("help", "?   Jak grać", "F1"),
        ("about", "☺   Autorzy", "O"),
        ("quit", "⏻   Wyjście", "Q"),
    )
    chosen = Signal(str)

    def __init__(self, win: MainWindow) -> None:
        super().__init__(win, width=520)
        self.aliens_row = QHBoxLayout()
        self.aliens_row.setSpacing(18)
        self.aliens_row.addStretch(1)
        self._alien_labels = [QLabel() for _ in range(3)]
        for lab in self._alien_labels:
            self.aliens_row.addWidget(lab)
        self.aliens_row.addStretch(1)
        self.body.addLayout(self.aliens_row)
        title = label("INVADERS", "Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(title)
        sub = label("obrona Ziemi – wersja graficzna", "Subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(sub)
        self.body.addSpacing(10)
        self.buttons: dict[str, QPushButton] = {}
        for key, text, hotkey in self.ITEMS:
            b = button(f"{text}", "MenuButton", f"Skrót: {hotkey}")
            b.setText(f"{text}")
            hint = QLabel(hotkey)
            hint.setObjectName("Hint")
            row = QHBoxLayout()
            row.addWidget(b, 1)
            row.addWidget(hint)
            self.body.addLayout(row)
            b.clicked.connect(lambda _=False, k=key: self.chosen.emit(k))
            self.buttons[key] = b
            self.shortcut(hotkey, lambda k=key: self.chosen.emit(k))
        hint = label("↑↓ / Tab – wybór · Enter – zatwierdź · lub kliknij myszą", "Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(hint)
        self._frame = 0

    def tick_animation(self) -> None:
        atlas = self.win.atlas
        if atlas is None:
            return
        self._frame ^= 1
        for lab, kind in zip(self._alien_labels, AlienKind, strict=False):
            img = atlas.aliens.get((kind, self._frame))
            if img is not None:
                lab.setPixmap(scaled(img, 8))

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.chosen.emit("quit")
            return
        super().keyPressEvent(event)

    def on_show(self) -> None:
        self.tick_animation()
        self.buttons["new"].setFocus()


# ======================================================================================
class NewGamePage(Page):
    start = Signal(object)

    def __init__(self, win: MainWindow) -> None:
        super().__init__(win, width=760)
        self.body.addWidget(label("NOWA GRA", "PageTitle"))
        cols = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(label("Poziom trudności", "HudLabel"))
        self.group = QButtonGroup(self)
        descriptions = {
            Difficulty.EASY: "5 żyć · wolniejsi kosmici · 2 pociski naraz",
            Difficulty.NORMAL: "3 życia · klasyczne tempo · 1 pocisk naraz",
            Difficulty.HARD: "3 życia · szybcy, celni kosmici · punkty ×1,5",
        }
        self.radios: dict[Difficulty, QRadioButton] = {}
        for i, diff in enumerate(DIFF_ORDER):
            r = QRadioButton(diff.label)
            r.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(r, i)
            left.addWidget(r)
            desc = label(descriptions[diff], "Hint")
            desc.setContentsMargins(34, 0, 0, 6)
            left.addWidget(desc)
            self.radios[diff] = r
        left.addStretch(1)
        cols.addLayout(left, 3)
        self.legend = QGridLayout()
        self.legend.setHorizontalSpacing(14)
        legend_box = QVBoxLayout()
        legend_box.addWidget(label("Tabela punktów", "HudLabel"))
        legend_box.addLayout(self.legend)
        legend_box.addStretch(1)
        cols.addLayout(legend_box, 2)
        self.body.addLayout(cols)
        row = QHBoxLayout()
        row.addStretch(1)
        self.start_button = button("▶  Start  (Enter)", "Primary")
        self.back_button = button("Wstecz  (Esc)")
        row.addWidget(self.start_button)
        row.addWidget(self.back_button)
        self.body.addLayout(row)
        self.body.addWidget(
            label("↑↓ – poziom · Enter – start · 1/2/3 – szybki wybór · Esc – wstecz", "Hint")
        )
        self.start_button.clicked.connect(self._start)
        self.back_button.clicked.connect(self.back.emit)
        for i, diff in enumerate(DIFF_ORDER, start=1):
            self.shortcut(str(i), lambda d=diff: self.radios[d].setChecked(True))
        for r in self.radios.values():
            r.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # Enter on a radio = start
        if event.type() == event.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._start()
            return True
        return False

    def selected(self) -> Difficulty:
        for diff, r in self.radios.items():
            if r.isChecked():
                return diff
        return Difficulty.NORMAL

    def _start(self) -> None:
        if self.isVisible():
            self.start.emit(self.selected())

    def _fill_legend(self) -> None:
        while self.legend.count():
            item = self.legend.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        atlas = self.win.atlas
        if atlas is None:
            return
        rows = [(atlas.ufo, "???", self.win.palette.ufo)]
        for kind in (AlienKind.SQUID, AlienKind.CRAB, AlienKind.OCTOPUS):
            rows.append((atlas.aliens[(kind, 0)], str(kind.points), self.win.palette.aliens[kind]))
        for i, (img, pts, color) in enumerate(rows):
            pic = QLabel()
            pic.setPixmap(scaled(img, 6))
            text = QLabel(f"= {pts} pkt")
            text.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 18px;")
            self.legend.addWidget(pic, i, 0)
            self.legend.addWidget(text, i, 1)

    def on_show(self) -> None:
        self.radios[self.win.settings.difficulty_enum].setChecked(True)
        self._fill_legend()
        self.radios[self.selected()].setFocus()

    def refresh_look(self) -> None:
        self._fill_legend()


# ======================================================================================
class HighscoresPage(Page):
    COLUMNS = ("#", "Inicjały", "Wynik", "Fala", "Poziom", "Data")

    def __init__(self, win: MainWindow) -> None:
        super().__init__(win, width=860)
        self.body.addWidget(label("★  RANKING  ★", "PageTitle"))
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(330)
        self.body.addWidget(self.table)
        self.empty = label("Brak wyników – zagraj pierwszą grę!", "Hint")
        self.body.addWidget(self.empty)
        row = QHBoxLayout()
        self.refresh_button = button("⟳  Odśwież (F5)", tip="Wczytaj ranking z dysku (w tle)")
        self.export_button = button("⇩  CSV (Ctrl+E)", tip="Eksportuj ranking do pliku CSV")
        self.clear_button = button("✖  Wyczyść (Del)", "Danger")
        self.back_button = button("Wstecz (Esc)")
        row.setSpacing(10)
        for b in (self.refresh_button, self.export_button, self.clear_button, self.back_button):
            b.setStyleSheet("min-width: 80px; padding: 10px 12px;")
            row.addWidget(b)
        self.body.addLayout(row)
        self.refresh_button.clicked.connect(self.reload)
        self.export_button.clicked.connect(self.export)
        self.clear_button.clicked.connect(self.clear)
        self.back_button.clicked.connect(self.back.emit)
        self.shortcut("F5", self.reload)
        self.shortcut("Ctrl+E", self.export)
        self.shortcut("Delete", self.clear)

    def populate(self) -> None:
        entries = self.win.highscores.entries
        self.table.setRowCount(len(entries))
        names = {d.value: d.label for d in Difficulty}
        for i, e in enumerate(entries):
            values = (
                f"{i + 1}" + (" ◄" if i == self.win.last_rank else ""),
                e.initials,
                str(e.score),
                str(e.wave),
                names.get(e.difficulty, e.difficulty),
                e.date,
            )
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, c, item)
        self.empty.setVisible(not entries)
        self.table.setVisible(bool(entries))
        if entries:
            row = self.win.last_rank if self.win.last_rank is not None else 0
            self.table.selectRow(min(row, len(entries) - 1))
        self.export_button.setEnabled(bool(entries))
        self.clear_button.setEnabled(bool(entries))

    def on_show(self) -> None:
        self.populate()
        (self.table if self.table.isVisible() else self.back_button).setFocus()

    def reload(self) -> None:
        store = self.win.highscore_store

        def done(result) -> None:
            table, warning = result
            self.win.highscores = table
            self.populate()
            if warning:
                self.win.warn("Ranking", warning)

        self.win.run_long("Wczytywanie rankingu…", lambda job: store.load(), done)

    def export(self) -> None:
        entries = self.win.highscores.entries
        if not entries:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Eksportuj ranking", "ranking.csv", "Pliki CSV (*.csv)"
        )
        if not path:
            return

        def write(job) -> str:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(self.COLUMNS)
                for i, e in enumerate(entries, start=1):
                    writer.writerow((i, e.initials, e.score, e.wave, e.difficulty, e.date))
            return path

        self.win.run_long(
            "Eksportowanie…", write, lambda p: self.win.info("Eksport", f"Zapisano: {p}")
        )

    def clear(self) -> None:
        if not self.win.highscores.entries:
            return
        answer = QMessageBox.question(
            self,
            "Wyczyść ranking",
            "Usunąć wszystkie wyniki? Tej operacji nie można cofnąć.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        empty = HighScoreTable()

        def done(_r) -> None:
            self.win.highscores = empty
            self.win.last_rank = None
            self.populate()
            self.back_button.setFocus()

        self.win.run_long("Zapisywanie…", lambda job: self.win.highscore_store.save(empty), done)


# ======================================================================================
def analyse_in_processes(job, games: int, limit: float) -> dict[Difficulty, list[GameResult]]:
    """CPU-heavy simulation in separate processes – no GIL contention with the GUI.
    The worker thread only waits for results (``wait`` releases the GIL)."""
    tasks = [(d, g) for d in DIFF_ORDER for g in range(games)]
    out: dict[Difficulty, list[GameResult]] = {d: [] for d in DIFF_ORDER}
    workers = max(1, min(4, (os.cpu_count() or 2) - 1))
    pool = ProcessPoolExecutor(max_workers=workers)
    try:
        pending = {pool.submit(simulate_game, d, 1000 + g, limit) for d, g in tasks}
        done_count = 0
        while pending:
            done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            for future in done:
                result: GameResult = future.result()
                out[result.difficulty].append(result)
                done_count += 1
                job.report(
                    100 * done_count / len(tasks),
                    f"{result.difficulty.label}: ukończono {done_count}/{len(tasks)} gier",
                )
            job.check_cancelled()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return out


def analyse_in_thread(job, games: int, limit: float) -> dict[Difficulty, list[GameResult]]:
    out: dict[Difficulty, list[GameResult]] = {d: [] for d in DIFF_ORDER}
    total, n = games * len(DIFF_ORDER), 0
    for diff in DIFF_ORDER:
        for g in range(games):
            job.check_cancelled()
            out[diff].append(simulate_game(diff, 1000 + g, limit, job.check_cancelled))
            n += 1
            job.report(100 * n / total, f"{diff.label}: gra {g + 1}/{games}")
    return out


class AnalysisPage(Page):
    """Long operation demo: bot plays many headless games per difficulty (worker thread)."""

    def __init__(self, win: MainWindow) -> None:
        super().__init__(win, width=900)
        self.body.addWidget(label("▤  ANALIZA TRUDNOŚCI", "PageTitle"))
        self.body.addWidget(
            label(
                "Autopilot rozgrywa wiele gier na każdym poziomie trudności, korzystając z tego "
                "samego silnika co gra. To długa operacja – działa w tle, a interfejs "
                "pozostaje responsywny (można ją anulować).",
                "Hint",
            )
        )
        form = QFormLayout()
        self.games = QSpinBox()
        self.games.setRange(1, 50)
        self.games.setValue(6)
        self.games.setToolTip("Liczba gier na poziom (1–50)")
        self.seconds = QSpinBox()
        self.seconds.setRange(10, 300)
        self.seconds.setValue(60)
        self.seconds.setSuffix(" s")
        self.seconds.setToolTip("Maksymalny czas jednej gry (10–300 s)")
        form.addRow("Gier na poziom:", stepper(self.games))
        form.addRow("Limit czasu gry:", stepper(self.seconds))
        self.body.addLayout(form)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ("Poziom", "Śr. wynik", "Śr. fala", "Śr. celność", "Śr. przeżycie")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(150)
        self.body.addWidget(self.table)
        self.chart = BarChart(win.palette)
        self.body.addWidget(self.chart)
        row = QHBoxLayout()
        self.run_button = button("▶  Uruchom analizę (Ctrl+R)", "Primary")
        self.back_button = button("Wstecz (Esc)")
        row.addStretch(1)
        row.addWidget(self.run_button)
        row.addWidget(self.back_button)
        self.body.addLayout(row)
        self.run_button.clicked.connect(self.run)
        self.back_button.clicked.connect(self.back.emit)
        self.shortcut("Ctrl+R", self.run)

    def on_show(self) -> None:
        self.run_button.setFocus()

    def refresh_look(self) -> None:
        self.chart.palette_ = self.win.palette
        self.chart.update()

    def run(self) -> None:
        games, limit = self.games.value(), float(self.seconds.value())

        def work(job) -> dict[Difficulty, list[GameResult]]:
            try:
                return analyse_in_processes(job, games, limit)
            except (OSError, BrokenProcessPool):
                return analyse_in_thread(job, games, limit)  # fallback, still off the GUI

        self.win.run_long("Analizowanie gier…", work, self.show_results, cancellable=True)

    def show_results(self, results: dict[Difficulty, list[GameResult]]) -> None:
        self.table.setRowCount(len(results))
        bars = []
        colors = [
            self.win.palette.aliens[k] for k in (AlienKind.OCTOPUS, AlienKind.CRAB, AlienKind.SQUID)
        ]
        for i, (diff, items) in enumerate(results.items()):
            n = max(1, len(items))
            avg_score = sum(r.score for r in items) / n
            values = (
                diff.label,
                f"{avg_score:.0f}",
                f"{sum(r.wave for r in items) / n:.1f}",
                f"{sum(r.accuracy for r in items) / n:.0f}%",
                f"{sum(r.survived_seconds for r in items) / n:.0f} s",
            )
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, c, item)
            bars.append((diff.label, avg_score, colors[i % 3]))
        self.chart.set_data("Średni wynik autopilota", bars)


# ======================================================================================
class SettingsPage(Page):
    def __init__(self, win: MainWindow) -> None:
        super().__init__(win, width=640)
        self.body.addWidget(label("⚙  USTAWIENIA", "PageTitle"))
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.palette_box = QComboBox()
        for key, pal in PALETTES.items():
            self.palette_box.addItem(pal.label, key)
        self.difficulty_box = QComboBox()
        for d in DIFF_ORDER:
            self.difficulty_box.addItem(d.label, d.value)
        self.stars = QCheckBox("Migające gwiazdy w tle")
        self.fullscreen = QCheckBox("Pełny ekran (F11)")
        self.fps = QCheckBox("Pokazuj licznik FPS")
        form.addRow("Motyw kolorystyczny:", self.palette_box)
        form.addRow("Domyślny poziom:", self.difficulty_box)
        form.addRow("", self.stars)
        form.addRow("", self.fullscreen)
        form.addRow("", self.fps)
        self.body.addLayout(form)
        self.body.addWidget(
            label(
                "Zmiany są stosowane i zapisywane od razu. Zmiana motywu przerysowuje "
                "grafikę w tle (ekran ładowania).",
                "Hint",
            )
        )
        row = QHBoxLayout()
        self.defaults_button = button("Przywróć domyślne")
        self.back_button = button("Wstecz (Esc)", "Primary")
        row.addStretch(1)
        row.addWidget(self.defaults_button)
        row.addWidget(self.back_button)
        self.body.addLayout(row)
        self._loading = False
        self.palette_box.currentIndexChanged.connect(self._changed)
        self.difficulty_box.currentIndexChanged.connect(self._changed)
        for cb in (self.stars, self.fullscreen, self.fps):
            cb.toggled.connect(self._changed)
        self.defaults_button.clicked.connect(self._defaults)
        self.back_button.clicked.connect(self.back.emit)

    def on_show(self) -> None:
        s = self.win.settings
        self._loading = True
        self.palette_box.setCurrentIndex(max(0, self.palette_box.findData(s.palette)))
        self.difficulty_box.setCurrentIndex(max(0, self.difficulty_box.findData(s.difficulty)))
        self.stars.setChecked(s.stars)
        self.fullscreen.setChecked(s.fullscreen)
        self.fps.setChecked(s.show_fps)
        self._loading = False
        self.palette_box.setFocus()

    def _changed(self, *_args) -> None:
        if self._loading:
            return
        self.win.update_settings(
            palette=self.palette_box.currentData(),
            difficulty=self.difficulty_box.currentData(),
            stars=self.stars.isChecked(),
            fullscreen=self.fullscreen.isChecked(),
            show_fps=self.fps.isChecked(),
        )

    def _defaults(self) -> None:
        from .settings import GuiSettings

        d = GuiSettings()
        self.win.update_settings(**d.__dict__)
        self.on_show()


# ======================================================================================
HELP_HTML = """
<h2>Cel gry</h2>
<p>Zestrzel wszystkich kosmitów, zanim wylądują. Każda kolejna fala startuje niżej
i jest szybsza. UFO u góry daje 50–300 pkt.</p>
<h2>Sterowanie</h2>
<table cellpadding="5">
<tr><td><b>← → / A D</b></td><td>ruch statku</td></tr>
<tr><td><b>Spacja / ↑ / W</b></td><td>strzał (przytrzymaj = seria)</td></tr>
<tr><td><b>Mysz</b></td><td>statek podąża za kursorem, <b>lewy przycisk</b> – strzał</td></tr>
<tr><td><b>Esc / P / prawy przycisk</b></td><td>pauza</td></tr>
<tr><td><b>F11</b></td><td>pełny ekran</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>wyjście (z potwierdzeniem w trakcie gry)</td></tr>
</table>
<h2>Menu</h2>
<p>Wszystko działa samą myszą lub samą klawiaturą: <b>Tab / strzałki</b> – przejście,
<b>Enter / Spacja</b> – wybór, <b>Esc</b> – powrót. Skróty są podpisane na przyciskach.</p>
<h2>Punkty</h2>
<p>Górny rząd 30 · środkowe 20 · dolne 10 pkt. Poziom <i>Trudny</i> ×1,5.
Osłony zmieniają kolor przy uszkodzeniu. Po progu punktowym – dodatkowe życie.</p>
"""


class TextPage(Page):
    def __init__(self, win: MainWindow, title: str, html: str) -> None:
        super().__init__(win, width=760)
        self.body.addWidget(label(title, "PageTitle"))
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(html)
        self.browser.setMinimumHeight(360)
        self.body.addWidget(self.browser)
        self.back_button = button("Wstecz (Esc)", "Primary")
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.back_button)
        self.body.addLayout(row)
        self.back_button.clicked.connect(self.back.emit)

    def on_show(self) -> None:
        self.browser.setFocus()


def help_page(win: MainWindow) -> TextPage:
    return TextPage(win, "?  JAK GRAĆ", HELP_HTML)


def about_page(win: MainWindow) -> TextPage:
    html = f"""
    <p align="center" style="font-size:20px"><b>Imię Nazwisko</b><br/>nr albumu: 000000</p>
    <p align="center">Komunikacja człowiek–komputer · projekt 2 (aplikacja graficzna)</p>
    <p align="center">Silnik gry: pakiet <code>invaders.core</code> v{core_version}
    z projektu konsolowego – <b>użyty bez żadnych zmian</b>.<br/>
    Interfejs: Python + Qt (PySide6) · wersja GUI {__version__}</p>
    <p align="center"><i>Grafika pikselowa generowana z tych samych danych sprite'ów
    co w wersji konsolowej.</i></p>
    """
    return TextPage(win, "☺  AUTORZY", html)
