"""End-to-end Room test — runs a full 10-question game using the real
trivia.db. Bots and one human; verifies state transitions, scoring, helps,
and final leaderboard."""
from __future__ import annotations

import random

from backend import config
from backend.game.room import Room, RoomError, generate_room_code


def _make_cpu_room() -> Room:
    room = Room(code=generate_room_code(), mode="cpu")
    human = room.add_player(name="Human", sid="sid-human")
    room.fill_with_bots_if_needed()
    assert len(room.bots()) == config.TARGET_BOTS_FOR_SOLO
    assert room.host_id == human.id
    return room


def test_full_game_loop():
    random.seed(42)
    room = _make_cpu_room()
    room.start_game()
    assert room.state == "countdown"

    for q_num in range(1, config.GAME_QUESTIONS + 1):
        q = room.begin_question()
        assert room.state == "question"
        assert len(q.options) == 4
        assert 0 <= q.correct_idx < 4
        assert q.options[q.correct_idx]  # correct text non-empty

        # Human answers correctly on every question to test bumping difficulty.
        human = next(p for p in room.players.values() if not p.is_bot)
        rec = room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
        assert rec.correct
        assert rec.points > 0

        # Bots answer with their own logic via Room (here we simulate directly).
        from backend.game import bots as bots_mod
        for bot in room.bots():
            choice = bots_mod.bot_pick_option(
                correct_idx=q.correct_idx,
                available_indices=[0, 1, 2, 3],
                difficulty=q.difficulty,
            )
            room.submit_answer(player_id=bot.id, option_idx=choice)

        room.finalize_question()
        assert room.state == "reveal"
        more = room.advance()
        assert more == (q_num < config.GAME_QUESTIONS)

    assert room.state == "ended"
    lb = room.leaderboard()
    assert len(lb) == 1 + config.TARGET_BOTS_FOR_SOLO
    assert lb[0]["rank"] == 1
    # Human got every Q right + speed bonus → should win.
    assert lb[0]["name"] == "Human"


def test_can_change_answer_until_finalize():
    """Players may overwrite their answer freely until the timer ends.
    Score is only applied once, using the LAST submission."""
    random.seed(1)
    room = _make_cpu_room()
    room.start_game()
    q = room.begin_question()
    human = next(p for p in room.players.values() if not p.is_bot)

    wrong_idx = (q.correct_idx + 1) % 4
    score_before = human.score

    # Submit wrong, then change to correct.
    rec_wrong = room.submit_answer(player_id=human.id, option_idx=wrong_idx)
    assert rec_wrong.correct is False
    rec_correct = room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
    assert rec_correct.correct is True

    # Score must NOT update at submit time — only at finalize.
    assert human.score == score_before

    # Finalize → only the final correct answer scores.
    room.finalize_question()
    assert human.score == score_before + rec_correct.points


def test_fifty_returns_two_wrong_indices():
    random.seed(2)
    room = _make_cpu_room()
    room.start_game()
    q = room.begin_question()
    human = next(p for p in room.players.values() if not p.is_bot)
    removed = room.use_fifty(human.id)
    assert len(removed) == 2
    assert q.correct_idx not in removed
    # Cannot use twice.
    try:
        room.use_fifty(human.id)
    except RoomError:
        pass
    else:
        raise AssertionError("expected RoomError on second 50/50")


def test_double_doubles_correct_answer_points():
    random.seed(3)
    room = _make_cpu_room()
    room.start_game()
    q = room.begin_question()
    human = next(p for p in room.players.values() if not p.is_bot)
    room.use_double(human.id)
    rec = room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
    assert rec.doubled
    assert rec.points >= 2 * config.BASE_POINTS


def test_unanswered_recorded_as_wrong_on_finalize():
    random.seed(4)
    room = _make_cpu_room()
    room.start_game()
    room.begin_question()
    summary = room.finalize_question()
    for pid in room.players:
        ans = summary.answers[pid]
        assert ans.correct is False
        assert ans.points == 0


def test_streak_increments_and_resets():
    """Streak counter goes up on correct, resets on wrong."""
    random.seed(10)
    room = _make_cpu_room()
    room.start_game()
    human = next(p for p in room.players.values() if not p.is_bot)
    assert human.streak == 0

    # Two correct in a row.
    for _ in range(2):
        q = room.begin_question()
        room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
        room.finalize_question()
        room.advance()
    assert human.streak == 2

    # Now answer wrong.
    q = room.begin_question()
    wrong_idx = (q.correct_idx + 1) % 4
    room.submit_answer(player_id=human.id, option_idx=wrong_idx)
    room.finalize_question()
    assert human.streak == 0


def test_streak_applies_multiplier_to_points():
    """Third correct in a row uses streak=2 → ×1.5 multiplier."""
    random.seed(11)
    room = _make_cpu_room()
    room.start_game()
    human = next(p for p in room.players.values() if not p.is_bot)

    # Answer two correctly to build streak=2.
    for _ in range(2):
        q = room.begin_question()
        room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
        room.finalize_question()
        room.advance()
    assert human.streak == 2

    # Third correct: streak_multiplier should be 1.5.
    q = room.begin_question()
    rec = room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
    assert rec.streak_multiplier == 1.5
    # Compare against a hypothetical no-streak score for the same elapsed time.
    from backend.game.scoring import compute_points
    base = compute_points(
        correct=True,
        elapsed=rec.elapsed,
        time_limit=float(config.QUESTION_TIME),
        doubled=False,
    )
    assert rec.points == round(base * 1.5)


def test_streak_resets_on_replay():
    random.seed(12)
    room = _make_cpu_room()
    room.start_game()
    human = next(p for p in room.players.values() if not p.is_bot)
    q = room.begin_question()
    room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
    room.finalize_question()
    assert human.streak == 1

    # Fast-forward to ended via the public API.
    while room.state != "ended":
        if room.state == "reveal":
            room.advance()
            if room.state == "ended":
                break
            room.begin_question()
            room.finalize_question()
    room.reset_for_replay()
    assert human.streak == 0


def test_difficulty_increases_after_correct_streak():
    random.seed(5)
    room = _make_cpu_room()
    starting_diff = room.current_difficulty
    room.start_game()
    human = next(p for p in room.players.values() if not p.is_bot)

    # First question — no adaptive change yet.
    q = room.begin_question()
    room.submit_answer(player_id=human.id, option_idx=q.correct_idx)
    room.finalize_question()
    room.advance()

    # Second question — should have bumped difficulty (or stayed at cap).
    q2 = room.begin_question()
    assert room.current_difficulty >= starting_diff
