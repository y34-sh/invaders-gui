"""Game canvas: paints ``engine.state`` with QPainter and turns keyboard/mouse into commands.

Qt delivers real key-release events, so held keys are tracked exactly (auto-repeat
events are ignored). The mouse steers with ``MoveToX``; whichever was used last wins.
"""

from __future__ import annotations

import math
import random

from invaders.core import config
from invaders.core.commands import Command, GameCommand, MoveToX
from invaders.core.engine import GameEngine, GameStatus
from invaders.core.entities import BulletKind, ExplosionKind
from invaders.core.sprites import UNICODE
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..pixelart import SpriteAtlas
from ..theme import GuiPalette

LEFT_KEYS = {Qt.Key.Key_Left, Qt.Key.Key_A}
RIGHT_KEYS = {Qt.Key.Key_Right, Qt.Key.Key_D}
FIRE_KEYS = {Qt.Key.Key_Space, Qt.Key.Key_W, Qt.Key.Key_Up}


class GameView(QWidget):
    pauseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.engine: GameEngine | None = None
        self.atlas: SpriteAtlas | None = None
        self.palette_: GuiPalette | None = None
        self.show_stars = True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 160)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._held: set[int] = set()
        self._fire_once = False
        self._mouse_fire = False
        self._mouse_x: float | None = None
        self._mode = "keyboard"
        rng = random.Random(77)
        self._stars = [
            (
                rng.uniform(0, config.WORLD_WIDTH),
                rng.uniform(0, config.WORLD_HEIGHT - 3),
                rng.randrange(3),
                rng.uniform(0, 6.28),
            )
            for _ in range(70)
        ]

    # --- setup -------------------------------------------------------------------------
    def set_look(self, palette: GuiPalette, atlas: SpriteAtlas, stars: bool) -> None:
        self.palette_, self.atlas, self.show_stars = palette, atlas, stars
        self.update()

    def set_engine(self, engine: GameEngine) -> None:
        self.engine = engine
        self.reset_input()
        self.update()

    def reset_input(self) -> None:
        self._held.clear()
        self._fire_once = self._mouse_fire = False

    # --- geometry ----------------------------------------------------------------------
    def _layout(self) -> tuple[float, float, float]:
        cell = min(self.width() / config.WORLD_WIDTH, self.height() / config.WORLD_HEIGHT)
        cell = max(cell, 1.0)
        ox = (self.width() - config.WORLD_WIDTH * cell) / 2
        oy = (self.height() - config.WORLD_HEIGHT * cell) / 2
        return cell, ox, oy

    def world_x(self, px: float) -> float:
        cell, ox, _ = self._layout()
        return max(0.0, min(config.WORLD_WIDTH, (px - ox) / cell))

    # --- input -------------------------------------------------------------------------
    def commands(self) -> set[GameCommand]:
        cmds: set[GameCommand] = set()
        left = bool(self._held & LEFT_KEYS)
        right = bool(self._held & RIGHT_KEYS)
        if self._mode == "keyboard":
            if left and not right:
                cmds.add(Command.MOVE_LEFT)
            elif right and not left:
                cmds.add(Command.MOVE_RIGHT)
        elif self._mouse_x is not None:
            cmds.add(MoveToX(self._mouse_x))
        if self._fire_once or self._mouse_fire or self._held & FIRE_KEYS:
            cmds.add(Command.FIRE)
            self._fire_once = False
        return cmds

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_P):
            self.pauseRequested.emit()
            return
        if key in LEFT_KEYS | RIGHT_KEYS | FIRE_KEYS:
            if not event.isAutoRepeat():
                self._held.add(key)
                if key in FIRE_KEYS:
                    self._fire_once = True
            if key in LEFT_KEYS | RIGHT_KEYS:
                self._mode = "keyboard"
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if not event.isAutoRepeat():
            self._held.discard(event.key())
        event.accept()

    def focusOutEvent(self, event) -> None:
        self.reset_input()  # never keep "stuck" keys after focus moves away
        super().focusOutEvent(event)

    def mouseMoveEvent(self, event) -> None:
        x = self.world_x(event.position().x())
        if self._mouse_x is None or abs(x - self._mouse_x) > 1e-3:
            self._mouse_x = x
            self._mode = "mouse"

    def mousePressEvent(self, event) -> None:
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_x = self.world_x(event.position().x())
            self._mode = "mouse"
            self._fire_once = True
            self._mouse_fire = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.pauseRequested.emit()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_fire = False

    # --- painting ----------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p: QPainter) -> None:
        pal = self.palette_
        if pal is None:
            p.fillRect(self.rect(), QColor("black"))
            return
        cell, ox, oy = self._layout()
        W, H = config.WORLD_WIDTH, config.WORLD_HEIGHT
        world = QRectF(ox, oy, W * cell, H * cell)
        p.fillRect(self.rect(), QColor(pal.bg_bottom))
        grad = QLinearGradient(world.topLeft(), world.bottomLeft())
        grad.setColorAt(0, QColor(pal.bg_top))
        grad.setColorAt(1, QColor(pal.bg_bottom))
        p.fillRect(world, grad)
        p.setPen(QPen(QColor(pal.panel_border), 1))
        p.drawRect(world)
        engine = self.engine
        t = engine.state.time if engine else 0.0

        if self.show_stars:
            for sx, sy, kind, phase in self._stars:
                tw = math.sin(t * 1.5 + phase)
                if tw < -0.5:
                    continue
                c = QColor(pal.stars[kind if tw > 0.2 else 0])
                size = cell * (0.15 + 0.1 * kind)
                p.fillRect(QRectF(ox + sx * cell, oy + sy * cell, size, size), c)

        if engine is None or self.atlas is None:
            return
        s = engine.state
        at = self.atlas
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        def rect(x: float, y: float, w: float, h: float) -> QRectF:
            return QRectF(ox + x * cell, oy + y * cell, w * cell, h * cell)

        # ground line
        p.fillRect(rect(0, H - 0.08, W, 0.08), QColor(pal.player))
        # bunkers: colour by remaining hp
        p.setPen(Qt.PenStyle.NoPen)
        for bunker in s.bunkers:
            for (dx, dy), hp in bunker.cells.items():
                p.setBrush(QColor(pal.bunker.get(hp, pal.bunker[1])))
                p.drawRect(rect(bunker.x + dx, bunker.y + dy, 1.02, 1.02))
        # aliens
        for alien in s.formation.alive:
            img = at.aliens.get((alien.kind, s.formation.frame))
            if img is not None:
                p.drawImage(rect(alien.x, alien.y, alien.w, alien.h), img)
        # UFO
        if s.ufo is not None and at.ufo is not None:
            p.drawImage(rect(s.ufo.x, s.ufo.y, s.ufo.w, s.ufo.h), at.ufo)
        # player
        pl = s.player
        if pl.visible and not s.player_blinking and not s.is_over and at.player is not None:
            p.drawImage(rect(pl.x, pl.y, pl.w, pl.h), at.player)
        # bullets
        for b in s.bullets:
            bx, by = b.cell
            if b.kind is BulletKind.PLAYER:
                p.fillRect(rect(bx + 0.38, by, 0.24, 1.0), QColor(pal.player_bullet))
            elif b.kind is BulletKind.SLOW:
                off = 0.15 if int(b.age * 12) % 2 else -0.15
                p.setPen(QPen(QColor(pal.slow_bullet), max(1.5, cell * 0.2)))
                p.drawLine(
                    QPointF(ox + (bx + 0.5 - off) * cell, oy + by * cell),
                    QPointF(ox + (bx + 0.5 + off) * cell, oy + (by + 1) * cell),
                )
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.fillRect(rect(bx + 0.33, by - 0.3, 0.34, 1.3), QColor(pal.fast_bullet))
        # explosions
        for e in s.explosions:
            frames = len(UNICODE.explosions[e.kind])
            idx = e.frame_index(frames)
            img = at.explosions.get((e.kind, idx))
            if img is not None:
                w = img.width() / 2
                h = img.height() / 2
                p.drawImage(rect(e.x, e.y, w, h), img)
            if e.kind is ExplosionKind.UFO and e.points and e.age > e.duration / 3:
                self._text(p, rect(e.x - 2, e.y, 10, 1), str(e.points), pal.player_bullet, cell)
        # banners
        if s.status is GameStatus.WAVE_TRANSITION:
            self._text(p, rect(0, 14.5, W, 2.5), f"FALA {s.wave}", pal.accent, cell * 2.2)
            self._text(p, rect(0, 17.2, W, 2), str(s.countdown), pal.accent2, cell * 1.6)
        elif s.is_over:
            self._text(p, rect(0, 12, W, 3), "KONIEC GRY", pal.danger, cell * 2.6)

    @staticmethod
    def _text(p: QPainter, r: QRectF, text: str, color: str, size: float) -> None:
        font = QFont("Consolas")
        font.setPixelSize(max(8, int(size)))
        font.setBold(True)
        p.setFont(font)
        shadow = QColor("black")
        shadow.setAlpha(160)
        p.setPen(shadow)
        p.drawText(r.translated(2, 2), Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(QColor(color))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
