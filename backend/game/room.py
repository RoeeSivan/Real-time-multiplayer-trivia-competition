"""Room — pure game state machine.

No sockets, no DB writes here (DB *reads* for question selection are
acceptable since they have no side effects on game state). The socket
layer drives Room and broadcasts the resulting payloads.

Lifecycle:
    LOBBY -> COUNTDOWN -> QUESTION -> REVEAL -> ... -> ENDED

`begin_question` advances LOBBY/REVEAL into QUESTION; `finalize_question`
moves QUESTION -> REVEAL and computes scoring; `advance` moves REVEAL into
the next QUESTION or ENDED.
"""
from __future__ import annotations

import logging
import random
import string
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from backend import config, db
from backend.game import adaptive, bots
from backend.game.player import Player
from backend.game.scoring import compute_points

log = logging.getLogger("trivia.room")

State = Literal["lobby", "countdown", "question", "reveal", "ended"]
Mode = Literal["cpu", "friends"]


@dataclass
class ActiveQuestion:
    rowid: int
    text: str
    options: list[str]      # length 4, shuffled
    correct_idx: int
    difficulty: int
    started_monotonic: float = 0.0


@dataclass
class AnswerRecord:
    player_id: str
    option_idx: int
    elapsed: float
    correct: bool
    doubled: bool
    points: int


@dataclass
class QuestionSummary:
    """Per-question result, kept for adaptive difficulty + reveal payload."""
    rowid: int
    correct_idx: int
    answers: dict[str, AnswerRecord] = field(default_factory=dict)


def generate_room_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=config.ROOM_CODE_LENGTH))


class Room:
    def __init__(self, *, code: str, mode: Mode, host_id: str | None = None) -> None:
        self.code = code
        self.mode: Mode = mode
        self.host_id: str | None = host_id
        self.players: dict[str, Player] = {}
        self.state: State = "lobby"
        self.used_rowids: set[int] = set()
        self.current_question: ActiveQuestion | None = None
        self.current_summary: QuestionSummary | None = None
        self.questions_asked: int = 0
        self.current_difficulty: int = config.DEFAULT_START_DIFFICULTY
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.history: list[QuestionSummary] = []

    # --- Player management ------------------------------------------------

    def add_player(self, *, name: str, sid: str | None = None, is_bot: bool = False) -> Player:
        if self.state != "lobby":
            raise RoomError("Game already started")
        p = Player(name=name, sid=sid, is_bot=is_bot)
        self.players[p.id] = p
        if self.host_id is None and not is_bot:
            self.host_id = p.id
        log.info("[%s] +player %s (%s)%s", self.code, p.name, p.id, " bot" if is_bot else "")
        return p

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)

    def humans(self) -> list[Player]:
        return [p for p in self.players.values() if not p.is_bot]

    def bots(self) -> list[Player]:
        return [p for p in self.players.values() if p.is_bot]

    def fill_with_bots_if_needed(self) -> list[Player]:
        """For CPU mode: pad to TARGET_BOTS_FOR_SOLO when only humans 1."""
        if len(self.humans()) != 1:
            return []
        needed = config.TARGET_BOTS_FOR_SOLO - len(self.bots())
        if needed <= 0:
            return []
        taken = {p.name for p in self.players.values()}
        names = bots.pick_bot_names(needed, taken=taken)
        added = [self.add_player(name=n, is_bot=True) for n in names]
        return added

    # --- Game flow --------------------------------------------------------

    def start_game(self) -> None:
        if self.state != "lobby":
            raise RoomError("Cannot start: not in lobby")
        if not self.players:
            raise RoomError("Cannot start: no players")
        self.state = "countdown"
        self.started_at = datetime.now(timezone.utc)
        log.info("[%s] starting game with %d players", self.code, len(self.players))

    def reset_for_replay(self) -> None:
        """Wipe game state so the same room can run another match.

        Only valid after a game has ended. Keeps human players + host, drops
        bots so `fill_with_bots_if_needed` repopulates with a fresh pool.
        """
        if self.state != "ended":
            raise RoomError("Can only restart after a game ends")
        bot_ids = [pid for pid, p in self.players.items() if p.is_bot]
        for pid in bot_ids:
            self.players.pop(pid, None)
        for p in self.players.values():
            p.score = 0
            p.help_fifty_used = False
            p.help_friend_used = False
            p.help_double_used = False
            p.double_armed = False
        self.state = "lobby"
        self.used_rowids.clear()
        self.current_question = None
        self.current_summary = None
        self.questions_asked = 0
        self.current_difficulty = config.DEFAULT_START_DIFFICULTY
        self.started_at = None
        self.ended_at = None
        self.history.clear()
        log.info("[%s] reset for replay", self.code)

    def begin_question(self) -> ActiveQuestion:
        """Load the next question and transition to QUESTION state."""
        if self.state not in ("countdown", "reveal"):
            raise RoomError(f"Cannot begin question from state {self.state}")
        if self.questions_asked >= config.GAME_QUESTIONS:
            raise RoomError("All questions answered already")

        # Adaptive: use last summary if any.
        if self.history:
            pct = self._human_correct_pct(self.history[-1])
            self.current_difficulty = adaptive.next_difficulty(self.current_difficulty, pct)

        row = db.get_random_question(self.current_difficulty, self.used_rowids)
        if row is None:
            raise RoomError("Out of questions")
        self.used_rowids.add(int(row["rowid"]))

        # Shuffle options; track which index is the correct one.
        options = [row["Option_1"], row["Option_2"], row["Option_3"], row["Option_4"]]
        order = list(range(4))
        random.shuffle(order)
        shuffled = [options[i] for i in order]
        correct_text = row["Correct_Answer"]
        correct_idx = shuffled.index(correct_text)

        # Reset per-question player state.
        for p in self.players.values():
            p.double_armed = False

        q = ActiveQuestion(
            rowid=int(row["rowid"]),
            text=row["Question"],
            options=shuffled,
            correct_idx=correct_idx,
            difficulty=int(row["Difficulty"]),
            started_monotonic=time.monotonic(),
        )
        self.current_question = q
        self.current_summary = QuestionSummary(rowid=q.rowid, correct_idx=correct_idx)
        self.state = "question"
        self.questions_asked += 1
        log.info(
            "[%s] Q%d/%d diff=%d rowid=%d",
            self.code, self.questions_asked, config.GAME_QUESTIONS, q.difficulty, q.rowid,
        )
        return q

    def submit_answer(self, *, player_id: str, option_idx: int) -> AnswerRecord:
        """Record (or overwrite) a player's choice for the current question.

        Players may change their answer freely until the timer ends. The
        score is NOT applied to player.score here — it is applied once in
        `finalize_question` so re-submissions don't double-count.
        """
        if self.state != "question":
            raise RoomError("Not accepting answers right now")
        if self.current_question is None or self.current_summary is None:
            raise RoomError("No active question")
        if player_id not in self.players:
            raise RoomError("Unknown player")
        if not (0 <= option_idx < 4):
            raise RoomError("Invalid option index")

        elapsed = time.monotonic() - self.current_question.started_monotonic
        elapsed = max(0.0, min(float(config.QUESTION_TIME), elapsed))
        correct = option_idx == self.current_question.correct_idx
        player = self.players[player_id]
        doubled = correct and player.double_armed
        points = compute_points(
            correct=correct,
            elapsed=elapsed,
            time_limit=float(config.QUESTION_TIME),
            doubled=doubled,
        )

        rec = AnswerRecord(
            player_id=player_id,
            option_idx=option_idx,
            elapsed=elapsed,
            correct=correct,
            doubled=doubled,
            points=points,
        )
        self.current_summary.answers[player_id] = rec  # overwrite OK
        return rec

    def finalize_question(self) -> QuestionSummary:
        """Apply scores from the final answer of each player, mark unanswered
        as wrong, and transition to REVEAL."""
        if self.state != "question":
            raise RoomError("Not in question state")
        assert self.current_question is not None
        assert self.current_summary is not None

        for pid in self.players:
            if pid in self.current_summary.answers:
                continue
            self.current_summary.answers[pid] = AnswerRecord(
                player_id=pid,
                option_idx=-1,
                elapsed=float(config.QUESTION_TIME),
                correct=False,
                doubled=False,
                points=0,
            )
        # Apply scores once, using each player's *final* answer.
        for pid, ans in self.current_summary.answers.items():
            self.players[pid].score += ans.points
        self.state = "reveal"
        self.history.append(self.current_summary)
        return self.current_summary

    def advance(self) -> bool:
        """After REVEAL: returns True if more questions remain."""
        if self.state != "reveal":
            raise RoomError("Not in reveal state")
        if self.questions_asked >= config.GAME_QUESTIONS:
            self.state = "ended"
            self.ended_at = datetime.now(timezone.utc)
            log.info("[%s] game ended", self.code)
            return False
        # Stay in REVEAL until begin_question is called.
        return True

    # --- Helps ------------------------------------------------------------

    def use_fifty(self, player_id: str) -> list[int]:
        """Return two wrong-answer indices to remove. Marks help as used."""
        p = self._require_player(player_id)
        if p.help_fifty_used:
            raise RoomError("50/50 already used")
        if self.state != "question" or self.current_question is None:
            raise RoomError("50/50 only during a question")
        wrongs = [i for i in range(4) if i != self.current_question.correct_idx]
        random.shuffle(wrongs)
        p.help_fifty_used = True
        return sorted(wrongs[:2])

    def use_double(self, player_id: str) -> None:
        p = self._require_player(player_id)
        if p.help_double_used:
            raise RoomError("Double already used")
        if self.state != "question":
            raise RoomError("Double only during a question")
        p.help_double_used = True
        p.double_armed = True
        # If the player already submitted, retro-apply doubling to the stored
        # record so finalize_question awards 2× when correct.
        if self.current_summary is not None:
            existing = self.current_summary.answers.get(player_id)
            if existing is not None and existing.correct and not existing.doubled:
                existing.doubled = True
                existing.points = compute_points(
                    correct=True,
                    elapsed=existing.elapsed,
                    time_limit=float(config.QUESTION_TIME),
                    doubled=True,
                )

    def mark_friend_used(self, player_id: str) -> None:
        p = self._require_player(player_id)
        if p.help_friend_used:
            raise RoomError("Call-a-friend already used")
        if self.state != "question":
            raise RoomError("Call-a-friend only during a question")
        p.help_friend_used = True

    # --- Helpers ----------------------------------------------------------

    def leaderboard(self) -> list[dict[str, object]]:
        ranked = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        return [{**p.to_public(), "rank": i + 1} for i, p in enumerate(ranked)]

    def winner_name(self) -> str | None:
        ranked = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        return ranked[0].name if ranked else None

    def _human_correct_pct(self, summary: QuestionSummary) -> float | None:
        humans = self.humans()
        if not humans:
            return None
        relevant = [summary.answers[p.id] for p in humans if p.id in summary.answers]
        if not relevant:
            return None
        return sum(1 for a in relevant if a.correct) / len(relevant)

    def _require_player(self, player_id: str) -> Player:
        p = self.players.get(player_id)
        if p is None:
            raise RoomError("Unknown player")
        return p


class RoomError(Exception):
    """Raised on invalid Room operations. Socket layer turns these into errors."""
