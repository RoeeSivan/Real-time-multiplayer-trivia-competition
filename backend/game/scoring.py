"""Pure scoring functions. No I/O, no side effects."""
from __future__ import annotations

from backend import config


_STREAK_TABLE: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0)


def streak_multiplier(streak: int) -> float:
    """Multiplier for the upcoming question given the player's *current* streak.

    `streak` = number of consecutive corrects so far (this round NOT yet counted).
    0 → 1.0, 1 → 1.25, 2 → 1.5, 3+ → 2.0.
    """
    if streak < 0:
        streak = 0
    return _STREAK_TABLE[min(streak, len(_STREAK_TABLE) - 1)]


def compute_points(
    *,
    correct: bool,
    elapsed: float,
    time_limit: float,
    doubled: bool,
    streak_multiplier: float = 1.0,
) -> int:
    """Return points awarded for an answer.

    Wrong / timed-out → 0.
    Correct → BASE_POINTS + linearly-decaying bonus based on response speed.
    Doubled → final value × 2.
    Streak multiplier applied on top of doubled (stacks multiplicatively).
    """
    if not correct:
        return 0
    fraction_left = max(0.0, 1.0 - (elapsed / time_limit))
    points = config.BASE_POINTS + round(config.MAX_BONUS * fraction_left)
    if doubled:
        points *= 2
    return round(points * streak_multiplier)
