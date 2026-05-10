"""Adaptive difficulty selector. Pure functions."""
from __future__ import annotations

from backend import config


def next_difficulty(current: int, human_correct_pct: float | None) -> int:
    """Compute the difficulty for the *next* question.

    `human_correct_pct` is the fraction of human players who answered the
    just-finished question correctly. None on the very first question.
    """
    if human_correct_pct is None:
        return _clamp(current)

    if human_correct_pct >= config.DIFFICULTY_UP_THRESHOLD:
        return _clamp(current + 1)
    if human_correct_pct <= config.DIFFICULTY_DOWN_THRESHOLD:
        return _clamp(current - 1)
    return _clamp(current)


def _clamp(value: int) -> int:
    return max(config.DIFFICULTY_MIN, min(config.DIFFICULTY_MAX, value))
