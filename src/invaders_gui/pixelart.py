"""Turns the console sprite strings from ``invaders.core.sprites`` into pixel-art images.

Each Unicode quadrant block character (▘▝▖▗▀▄▌▐▚▞▛▜▙▟█) encodes a 2×2 pixel mask, so a
4×2-character console alien becomes an 8×4-pixel bitmap. The core data is reused as is.
QImage (unlike QPixmap) is safe to create in worker threads.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from invaders.core.entities import AlienKind, ExplosionKind
from invaders.core.sprites import UNICODE, SpriteSet
from PySide6.QtGui import QColor, QImage

from .theme import GuiPalette

TL, TR, BL, BR = 1, 2, 4, 8
QUADRANTS: dict[str, int] = {
    " ": 0,
    "▘": TL,
    "▝": TR,
    "▖": BL,
    "▗": BR,
    "▀": TL | TR,
    "▄": BL | BR,
    "▌": TL | BL,
    "▐": TR | BR,
    "▚": TL | BR,
    "▞": TR | BL,
    "▛": TL | TR | BL,
    "▜": TL | TR | BR,
    "▙": TL | BL | BR,
    "▟": TR | BL | BR,
    "█": TL | TR | BL | BR,
}
SHADES = {"░": 0.35, "▒": 0.6, "▓": 0.85}


def char_mask(ch: str) -> tuple[int, float]:
    """(2×2 bit mask, alpha) for one sprite character."""
    if ch in QUADRANTS:
        return QUADRANTS[ch], 1.0
    if ch in SHADES:
        return TL | TR | BL | BR, SHADES[ch]
    if ch == "·":
        return BR, 0.8
    return TL | TR | BL | BR, 1.0  # any other glyph -> solid block


def sprite_image(lines: tuple[str, ...], color: str) -> QImage:
    width = max((len(line) for line in lines), default=0) * 2
    height = len(lines) * 2
    image = QImage(max(1, width), max(1, height), QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    base = QColor(color)
    for cy, line in enumerate(lines):
        for cx, ch in enumerate(line):
            mask, alpha = char_mask(ch)
            if not mask:
                continue
            c = QColor(base)
            c.setAlphaF(alpha)
            for bit, (dx, dy) in ((TL, (0, 0)), (TR, (1, 0)), (BL, (0, 1)), (BR, (1, 1))):
                if mask & bit:
                    image.setPixelColor(cx * 2 + dx, cy * 2 + dy, c)
    return image


@dataclass
class SpriteAtlas:
    aliens: dict[tuple[AlienKind, int], QImage] = field(default_factory=dict)
    player: QImage | None = None
    ufo: QImage | None = None
    explosions: dict[tuple[ExplosionKind, int], QImage] = field(default_factory=dict)
    palette_key: str = ""


def build_atlas(
    palette: GuiPalette,
    sprites: SpriteSet = UNICODE,
    progress: Callable[[int, str], None] | None = None,
) -> SpriteAtlas:
    atlas = SpriteAtlas(palette_key=palette.key)
    jobs: list[tuple[str, Callable[[], None]]] = []

    for kind, frames in sprites.aliens.items():
        for i, frame in enumerate(frames):
            jobs.append(
                (
                    f"kosmita {kind.name.lower()} #{i + 1}",
                    lambda k=kind, i=i, f=frame: atlas.aliens.__setitem__(
                        (k, i), sprite_image(f, palette.aliens[k])
                    ),
                )
            )
    jobs.append(
        ("statek", lambda: setattr(atlas, "player", sprite_image(sprites.player, palette.player)))
    )
    jobs.append(("UFO", lambda: setattr(atlas, "ufo", sprite_image(sprites.ufo, palette.ufo))))
    for kind, frames in sprites.explosions.items():
        for i, frame in enumerate(frames):
            color = palette.explosion[min(i, len(palette.explosion) - 1)]
            jobs.append(
                (
                    f"wybuch {kind.name.lower()} #{i + 1}",
                    lambda k=kind, i=i, f=frame, c=color: atlas.explosions.__setitem__(
                        (k, i), sprite_image(f, c)
                    ),
                )
            )
    for n, (label, job) in enumerate(jobs, start=1):
        job()
        if progress is not None:
            progress(round(100 * n / len(jobs)), label)
    return atlas
