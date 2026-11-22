"""A simple autopilot that plays the core engine headlessly – used by the long-running
"Analiza trudności" (difficulty analysis) operation. Uses only the public engine API."""

from __future__ import annotations

import random
from dataclasses import dataclass

from invaders.core.commands import Command, GameCommand, MoveToX
from invaders.core.config import Difficulty
from invaders.core.engine import GameEngine

SIM_DT = 1 / 30


@dataclass(frozen=True)
class GameResult:
    difficulty: Difficulty
    score: int
    wave: int
    aliens_killed: int
    accuracy: float
    survived_seconds: float


def bot_commands(engine: GameEngine, rng: random.Random) -> set[GameCommand]:
    s = engine.state
    p = s.player
    px = p.center_x
    # dodge: an alien bullet close above the ship -> step aside
    for b in s.bullets:
        if not b.from_player and p.y - 6 < b.y < p.y and abs(b.x - px) < 3:
            return {Command.MOVE_LEFT if b.x >= px else Command.MOVE_RIGHT}
    shooters = s.formation.shooters()
    if s.ufo is not None and rng.random() < 0.3:
        target = s.ufo.x + s.ufo.w / 2
    elif shooters:
        target = min(shooters, key=lambda a: abs(a.x + a.w / 2 - px)).x + 2
    else:
        target = px
    commands: set[GameCommand] = {MoveToX(target)}
    if abs(target - px) < 1.5:
        commands.add(Command.FIRE)
    return commands


def simulate_game(
    difficulty: Difficulty, seed: int, max_seconds: float = 90.0, check=None
) -> GameResult:
    rng = random.Random(seed)
    engine = GameEngine(difficulty, random.Random(seed), intro=False)
    t = 0.0
    steps = 0
    while not engine.state.is_over and t < max_seconds:
        engine.step(SIM_DT, bot_commands(engine, rng))
        t += SIM_DT
        steps += 1
        if check is not None and steps % 60 == 0:
            check()
    s = engine.state
    return GameResult(
        difficulty, s.score, s.wave, s.stats.aliens_killed, s.stats.accuracy, round(t, 1)
    )
