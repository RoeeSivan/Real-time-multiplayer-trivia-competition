import random

from backend import config
from backend.game import bots


def test_pick_bot_names_unique_and_avoids_taken():
    taken = {config.BOT_NAME_POOL[0]}
    names = bots.pick_bot_names(3, taken=taken)
    assert len(names) == 3
    assert config.BOT_NAME_POOL[0] not in names
    assert len(set(names)) == 3


def test_correctness_probability_bounds():
    assert bots.bot_correctness_probability(1) == 0.95
    assert bots.bot_correctness_probability(10) == 0.25
    # Monotonic non-increasing.
    probs = [bots.bot_correctness_probability(d) for d in range(1, 11)]
    assert probs == sorted(probs, reverse=True)


def test_bot_pick_option_eventually_wrong():
    rng = random.Random(0)
    picks = [
        bots.bot_pick_option(
            correct_idx=2, available_indices=[0, 1, 2, 3], difficulty=10, rng=rng
        )
        for _ in range(200)
    ]
    assert any(p != 2 for p in picks), "hard difficulty must miss sometimes"
    assert any(p == 2 for p in picks), "should sometimes still be correct"


def test_bot_answer_delay_in_window():
    for _ in range(50):
        d = bots.bot_answer_delay(15.0)
        assert config.BOT_MIN_DELAY <= d <= 15.0 - config.BOT_MAX_DELAY_GAP + 0.01
