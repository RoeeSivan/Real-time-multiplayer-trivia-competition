from backend import config
from backend.game.adaptive import next_difficulty


def test_first_question_no_change():
    assert next_difficulty(5, None) == 5


def test_high_accuracy_increases():
    assert next_difficulty(5, 0.8) == 6


def test_low_accuracy_decreases():
    assert next_difficulty(5, 0.1) == 4


def test_mid_accuracy_holds():
    assert next_difficulty(5, 0.5) == 5


def test_clamped_at_max():
    assert next_difficulty(config.DIFFICULTY_MAX, 1.0) == config.DIFFICULTY_MAX


def test_clamped_at_min():
    assert next_difficulty(config.DIFFICULTY_MIN, 0.0) == config.DIFFICULTY_MIN
