"""Keyboard-only comfort: arrow keys move focus between buttons, Enter activates them."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QPushButton,
    QRadioButton,
    QWidget,
)


class KeyboardNavigator(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        widget = QApplication.focusWidget()
        if obj is not widget or not isinstance(widget, QAbstractButton):
            return False
        if isinstance(widget, QRadioButton):
            return False  # radio groups already use arrows to change the choice
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and isinstance(
            widget, (QPushButton, QCheckBox)
        ):
            widget.animateClick()
            return True
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            return move_focus(widget, forward=True)
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            return move_focus(widget, forward=False)
        return False


def move_focus(widget: QWidget, forward: bool) -> bool:
    """Focus the next/previous tab-focusable widget in the same window."""
    window = widget.window()
    current = widget
    for _ in range(500):
        current = current.nextInFocusChain() if forward else current.previousInFocusChain()
        if current is None or current is widget:
            return False
        if (
            current.window() is window
            and current.isVisible()
            and current.isEnabled()
            and current.focusPolicy() & Qt.FocusPolicy.TabFocus
        ):
            current.setFocus(Qt.FocusReason.TabFocusReason)
            return True
    return False
