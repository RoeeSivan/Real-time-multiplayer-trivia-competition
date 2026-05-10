from backend import config
from backend.game.scoring import compute_points


def test_wrong_is_zero():
    assert compute_points(correct=False, elapsed=0.0, time_limit=15.0, doubled=False) == 0
    assert compute_points(correct=False, elapsed=0.0, time_limit=15.0, doubled=True) == 0


def test_instant_correct_is_max():
    pts = compute_points(correct=True, elapsed=0.0, time_limit=15.0, doubled=False)
    assert pts == config.BASE_POINTS + config.MAX_BONUS


def test_full_time_correct_is_base():
    pts = compute_points(correct=True, elapsed=15.0, time_limit=15.0, doubled=False)
    assert pts == config.BASE_POINTS


def test_double_doubles():
    base = compute_points(correct=True, elapsed=5.0, time_limit=15.0, doubled=False)
    doubled = compute_points(correct=True, elapsed=5.0, time_limit=15.0, doubled=True)
    assert doubled == base * 2


def test_overtime_clamped_to_base():
    pts = compute_points(correct=True, elapsed=99.0, time_limit=15.0, doubled=False)
    assert pts == config.BASE_POINTS
