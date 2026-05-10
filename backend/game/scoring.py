"""Pure scoring functions. No I/O, no side effects."""
from __future__ import annotations

from backend import config


def compute_points(*, correct: bool, elapsed: float, time_limit: float, doubled: bool) -> int:
    """Return points awarded for an answer.

    Wrong / timed-out → 0.
    Correct → BASE_POINTS + linearly-decaying bonus based on response speed.
    Doubled → final value × 2.
    """
    if not correct:
        return 0
    fraction_left = max(0.0, 1.0 - (elapsed / time_limit))
    points = config.BASE_POINTS + round(config.MAX_BONUS * fraction_left)
    if doubled:
        points *= 2
    return points
