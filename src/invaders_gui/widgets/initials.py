"""Initials picker usable with mouse only (▲/▼ buttons) or keyboard only (arrows/letters)."""

from __future__ import annotations

from invaders.core.highscores import INITIALS_ALPHABET
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QWidget

SLOTS = 3


class InitialsPicker(QWidget):
    submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._idx = [0] * SLOTS
        self.position = 0
        grid = QGridLayout(self)
        grid.setHorizontalSpacing(14)
        self._labels: list[QLabel] = []
        for i in range(SLOTS):
            up = QPushButton("▲")
            up.setObjectName("Small")
            up.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            up.setToolTip("Następna litera (↑)")
            up.clicked.connect(lambda _=False, i=i: self._change(i, 1))
            down = QPushButton("▼")
            down.setObjectName("Small")
            down.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            down.setToolTip("Poprzednia litera (↓)")
            down.clicked.connect(lambda _=False, i=i: self._change(i, -1))
            label = QLabel("A")
            label.setObjectName("InitialLetter")
            label.setMinimumHeight(64)
            label.mousePressEvent = lambda _e, i=i: self._select(i)  # type: ignore[method-assign]
            grid.addWidget(up, 0, i, alignment=Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 1, i)
            grid.addWidget(down, 2, i, alignment=Qt.AlignmentFlag.AlignCenter)
            self._labels.append(label)
        self._refresh()

    @property
    def value(self) -> str:
        return "".join(INITIALS_ALPHABET[i] for i in self._idx)

    def _select(self, slot: int) -> None:
        self.position = slot
        self.setFocus()
        self._refresh()

    def _change(self, slot: int, delta: int) -> None:
        self.position = slot
        self._idx[slot] = (self._idx[slot] + delta) % len(INITIALS_ALPHABET)
        self._refresh()

    def _refresh(self) -> None:
        for i, label in enumerate(self._labels):
            label.setText(INITIALS_ALPHABET[self._idx[i]])
            label.setProperty("current", "true" if i == self.position else "false")
            label.style().unpolish(label)
            label.style().polish(label)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        text = event.text().upper()
        if key == Qt.Key.Key_Up:
            self._change(self.position, 1)
        elif key == Qt.Key.Key_Down:
            self._change(self.position, -1)
        elif key == Qt.Key.Key_Left:
            self._select((self.position - 1) % SLOTS)
        elif key == Qt.Key.Key_Right:
            self._select((self.position + 1) % SLOTS)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submitted.emit(self.value)
        elif len(text) == 1 and text in INITIALS_ALPHABET:  # typing also works
            self._idx[self.position] = INITIALS_ALPHABET.index(text)
            self._select(min(self.position + 1, SLOTS - 1))
        else:
            super().keyPressEvent(event)
            return
        event.accept()
