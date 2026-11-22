"""Loading overlay: spinning arc + message + optional progress and Cancel button.

Shown on start-up and during every long operation. The spinner keeps rotating because
the work itself runs in a worker thread (see ``workers.py``).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from ..theme import GuiPalette


class LoadingOverlay(QWidget):
    cancelRequested = Signal()

    def __init__(self, parent: QWidget, palette: GuiPalette) -> None:
        super().__init__(parent)
        self.palette_ = palette
        self.angle = 0
        self.message = "Ładowanie…"
        self.detail = ""
        self.percent: int | None = None
        self.opaque = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._spin)
        self.cancel_button = QPushButton("Anuluj  (Esc)", self)
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.cancel_button.hide()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    def set_palette(self, palette: GuiPalette) -> None:
        self.palette_ = palette
        self.update()

    # --- control -----------------------------------------------------------------------
    def start(self, message: str, *, cancellable: bool = False, opaque: bool = False) -> None:
        self.message = message
        self.detail = ""
        self.percent = None
        self.opaque = opaque
        self.cancel_button.setVisible(cancellable)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.setFocus()
        self._timer.start()

    def progress(self, percent: int, detail: str = "") -> None:
        self.percent = percent
        self.detail = detail
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    @property
    def active(self) -> bool:
        return self.isVisible()

    # --- events ------------------------------------------------------------------------
    def _spin(self) -> None:
        self.angle = (self.angle + 6) % 360
        self.update()

    def resizeEvent(self, event) -> None:
        w = 180
        self.cancel_button.setGeometry((self.width() - w) // 2, self.height() // 2 + 110, w, 44)
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        # Swallow everything while busy, except Esc = cancel.
        if event.key() == Qt.Key.Key_Escape and self.cancel_button.isVisible():
            self.cancelRequested.emit()
        event.accept()

    def mousePressEvent(self, event) -> None:
        event.accept()  # block clicks to the page underneath

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette_
        bg = QColor(pal.bg_bottom)
        bg.setAlpha(255 if self.opaque else 200)
        p.fillRect(self.rect(), bg)
        cx, cy = self.width() / 2, self.height() / 2 - 20
        r = 42
        track = QPen(QColor(pal.panel_border), 8)
        p.setPen(track)
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        arc = QPen(QColor(pal.accent), 8)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc)
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), -self.angle * 16, 100 * 16)
        arc2 = QPen(QColor(pal.accent2), 8)
        arc2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc2)
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), (-self.angle + 180) * 16, 60 * 16)
        p.setPen(QColor(pal.text))
        font = QFont(self.font())
        font.setPointSize(16)
        font.setBold(True)
        p.setFont(font)
        dots = "." * (1 + (self.angle // 60) % 3)
        p.drawText(
            QRectF(0, cy + r + 18, self.width(), 30),
            Qt.AlignmentFlag.AlignCenter,
            self.message.rstrip(".…") + dots,
        )
        font.setPointSize(11)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor(pal.muted))
        info = self.detail
        if self.percent is not None:
            info = f"{self.percent}%  {info}".strip()
        if info:
            p.drawText(QRectF(0, cy + r + 50, self.width(), 24), Qt.AlignmentFlag.AlignCenter, info)
        if self.percent is not None:
            bw = 320
            x = cx - bw / 2
            y = cy + r + 80
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.panel_border))
            p.drawRoundedRect(QRectF(x, y, bw, 8), 4, 4)
            p.setBrush(QColor(pal.accent))
            p.drawRoundedRect(QRectF(x, y, bw * self.percent / 100, 8), 4, 4)
        p.end()
