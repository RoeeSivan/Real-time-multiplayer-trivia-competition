"""Bot behaviour helpers. Pure (deterministic given an RNG)."""
from __future__ import annotations

import random

from backend import config


def pick_bot_names(count: int, *, taken: set[str]) -> list[str]:
    """Choose `count` distinct bot names not already in `taken`."""
    available = [n for n in config.BOT_NAME_POOL if n not in taken]
    random.shuffle(available)
    return available[:count]


def bot_answer_delay(time_limit: float, rng: random.Random | None = None) -> float:
    """Random delay (seconds) before a bot submits — between MIN and limit-gap."""
    r = rng or random
    upper = max(config.BOT_MIN_DELAY + 0.1, time_limit - config.BOT_MAX_DELAY_GAP)
    return r.uniform(config.BOT_MIN_DELAY, upper)


def bot_correctness_probability(difficulty: int) -> float:
    """Probability that a bot answers correctly. Harder Q → lower.

    Mapped so difficulty 1 → 0.95, difficulty 10 → 0.25, linear in between.
    """
    raw = 1.05 - (difficulty / 10.0)
    return max(0.25, min(0.95, raw))


def bot_pick_option(
    *,
    correct_idx: int,
    available_indices: list[int],
    difficulty: int,
    rng: random.Random | None = None,
) -> int:
    """Pick an answer index given current available options after 50/50.

    For bots there's no 50/50 — `available_indices` is normally [0,1,2,3] but
    callers can shrink it. We bias toward correctness using the difficulty
    probability.
    """
    r = rng or random
    p_correct = bot_correctness_probability(difficulty)
    if correct_idx in available_indices and r.random() < p_correct:
        return correct_idx
    wrongs = [i for i in available_indices if i != correct_idx]
    if not wrongs:
        return correct_idx
    return r.choice(wrongs)
