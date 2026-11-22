"""Tiny bar chart (QPainter) for the difficulty analysis results."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ..theme import GuiPalette


class BarChart(QWidget):
    def __init__(self, palette: GuiPalette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.palette_ = palette
        self.bars: list[tuple[str, float, str]] = []  # label, value, colour
        self.title = ""
        self.setMinimumHeight(200)

    def set_data(self, title: str, bars: list[tuple[str, float, str]]) -> None:
        self.title, self.bars = title, bars
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette_
        p.setPen(QColor(pal.muted))
        font = QFont(self.font())
        font.setPointSize(11)
        p.setFont(font)
        p.drawText(QRectF(0, 0, self.width(), 22), Qt.AlignmentFlag.AlignCenter, self.title)
        if not self.bars:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Brak danych – uruchom analizę")
            p.end()
            return
        top, bottom = 30, self.height() - 28
        maximum = max((v for _, v, _ in self.bars), default=1) or 1
        slot = self.width() / len(self.bars)
        for i, (label, value, color) in enumerate(self.bars):
            h = (bottom - top) * value / maximum
            x = i * slot + slot * 0.2
            r = QRectF(x, bottom - h, slot * 0.6, h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor(pal.text))
            p.drawText(
                QRectF(x, bottom - h - 22, slot * 0.6, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"{value:.0f}",
            )
            p.drawText(QRectF(i * slot, bottom + 4, slot, 22), Qt.AlignmentFlag.AlignCenter, label)
        p.end()
