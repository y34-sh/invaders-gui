"""GUI settings persisted with the core's safe JSON helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from invaders.core.config import Difficulty
from invaders.core.storage import default_data_dir, read_json, write_json_atomic

from .theme import PALETTES

FILE_NAME = "gui-settings.json"


@dataclass(frozen=True)
class GuiSettings:
    palette: str = "classic"
    stars: bool = True
    difficulty: str = Difficulty.NORMAL.value
    fullscreen: bool = False
    show_fps: bool = False

    @property
    def difficulty_enum(self) -> Difficulty:
        try:
            return Difficulty(self.difficulty)
        except ValueError:
            return Difficulty.NORMAL

    def with_changes(self, **changes: Any) -> GuiSettings:
        return replace(self, **changes)

    @classmethod
    def from_dict(cls, raw: Any) -> tuple[GuiSettings, bool]:
        d = cls()
        if not isinstance(raw, dict):
            return d, True
        bad = False

        def get(name: str, ok: bool) -> Any:
            nonlocal bad
            if name not in raw:
                return getattr(d, name)
            if not ok:
                bad = True
                return getattr(d, name)
            return raw[name]

        return (
            cls(
                palette=get("palette", raw.get("palette") in PALETTES),
                stars=get("stars", isinstance(raw.get("stars"), bool)),
                difficulty=get(
                    "difficulty", raw.get("difficulty") in {x.value for x in Difficulty}
                ),
                fullscreen=get("fullscreen", isinstance(raw.get("fullscreen"), bool)),
                show_fps=get("show_fps", isinstance(raw.get("show_fps"), bool)),
            ),
            bad,
        )


class GuiSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_data_dir() / FILE_NAME

    def load(self) -> tuple[GuiSettings, str | None]:
        data, warning = read_json(self.path)
        if data is None:
            return GuiSettings(), warning
        settings, bad = GuiSettings.from_dict(data)
        if bad and not warning:
            warning = "Część ustawień była nieprawidłowa – przywrócono wartości domyślne."
        return settings, warning

    def save(self, settings: GuiSettings) -> None:
        write_json_atomic(self.path, asdict(settings))
