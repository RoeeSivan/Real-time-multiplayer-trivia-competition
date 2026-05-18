from backend import config
from backend.game.scoring import compute_points, streak_multiplier


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


def test_streak_multiplier_table():
    assert streak_multiplier(0) == 1.0
    assert streak_multiplier(1) == 1.25
    assert streak_multiplier(2) == 1.5
    assert streak_multiplier(3) == 2.0
    assert streak_multiplier(4) == 2.0  # cap
    assert streak_multiplier(99) == 2.0
    # Defensive: negative shouldn't crash.
    assert streak_multiplier(-1) == 1.0


def test_streak_zero_no_change():
    base = compute_points(correct=True, elapsed=5.0, time_limit=15.0, doubled=False)
    with_streak = compute_points(
        correct=True, elapsed=5.0, time_limit=15.0, doubled=False, streak_multiplier=1.0
    )
    assert base == with_streak


def test_streak_multiplies_points():
    base = compute_points(correct=True, elapsed=5.0, time_limit=15.0, doubled=False)
    boosted = compute_points(
        correct=True, elapsed=5.0, time_limit=15.0, doubled=False, streak_multiplier=1.5
    )
    assert boosted == round(base * 1.5)


def test_streak_stacks_with_double():
    base = compute_points(correct=True, elapsed=5.0, time_limit=15.0, doubled=False)
    stacked = compute_points(
        correct=True, elapsed=5.0, time_limit=15.0, doubled=True, streak_multiplier=2.0
    )
    # double ×2, streak ×2 → ×4
    assert stacked == round(base * 4)


def test_streak_wrong_still_zero():
    assert (
        compute_points(
            correct=False, elapsed=0.0, time_limit=15.0, doubled=True, streak_multiplier=2.0
        )
        == 0
    )
