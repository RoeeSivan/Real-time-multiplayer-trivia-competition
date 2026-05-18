"""Async game runner. Drives a Room through its phases and emits events.

Owns *all* timers and bot answer tasks. The socket layer creates a runner
when a game starts; runner.run() is the long-lived coroutine that walks
the room from countdown → 10 questions → ended. Submitting an answer
or fully filling all answers can short-circuit the question phase.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend import config, db
from backend.game import bots
from backend.game.room import ActiveQuestion, Room, RoomError

if TYPE_CHECKING:
    import socketio  # type: ignore

log = logging.getLogger("trivia.runner")


class GameRunner:
    def __init__(self, sio: "socketio.AsyncServer", room: Room) -> None:
        self.sio = sio
        self.room = room
        self._main_task: asyncio.Task | None = None
        self._bot_tasks: list[asyncio.Task] = []

    # --- Public ----------------------------------------------------------

    def start(self) -> None:
        if self._main_task is not None:
            return
        self._main_task = asyncio.create_task(self._run(), name=f"runner-{self.room.code}")

    def cancel(self) -> None:
        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
        for t in self._bot_tasks:
            t.cancel()

    # --- Loop ------------------------------------------------------------

    async def _run(self) -> None:
        try:
            await self._countdown()
            for _ in range(config.GAME_QUESTIONS):
                q = self.room.begin_question()
                await self._broadcast_question(q)
                await self._question_phase(q)
                summary = self.room.finalize_question()
                await self._send_private_results(summary)
                await self._broadcast_round_end()
                await asyncio.sleep(config.REVEAL_TIME)
                more = self.room.advance()
                if not more:
                    break
            await self._finish()
        except asyncio.CancelledError:
            log.info("[%s] runner cancelled", self.room.code)
            raise
        except Exception:
            log.exception("[%s] runner crashed", self.room.code)
            await self._emit_error("Game error")

    async def _countdown(self) -> None:
        await self._emit("game_starting", {"countdown_seconds": config.START_COUNTDOWN})
        await asyncio.sleep(config.START_COUNTDOWN)

    async def _question_phase(self, q: ActiveQuestion) -> None:
        """Runs the question for the full QUESTION_TIME — no early exit."""
        self._cancel_bot_tasks()
        for bot in self.room.bots():
            self._bot_tasks.append(
                asyncio.create_task(self._bot_answer(bot.id, q), name=f"bot-{bot.id}")
            )
        try:
            await asyncio.sleep(config.QUESTION_TIME)
        finally:
            self._cancel_bot_tasks()

    def _cancel_bot_tasks(self) -> None:
        for t in self._bot_tasks:
            if not t.done():
                t.cancel()
        self._bot_tasks.clear()

    async def _bot_answer(self, bot_id: str, q: ActiveQuestion) -> None:
        try:
            delay = bots.bot_answer_delay(float(config.QUESTION_TIME))
            await asyncio.sleep(delay)
            choice = bots.bot_pick_option(
                correct_idx=q.correct_idx,
                available_indices=[0, 1, 2, 3],
                difficulty=q.difficulty,
            )
            try:
                self.room.submit_answer(player_id=bot_id, option_idx=choice)
            except RoomError as e:
                log.debug("[%s] bot %s submit ignored: %s", self.room.code, bot_id, e)
                return
            await self._emit("answer_received", {"player_id": bot_id})
        except asyncio.CancelledError:
            pass

    # --- Broadcasts ------------------------------------------------------

    async def _broadcast_question(self, q: ActiveQuestion) -> None:
        await self._emit(
            "question",
            {
                "idx": self.room.questions_asked - 1,
                "text": q.text,
                "options": q.options,
                "time_limit": config.QUESTION_TIME,
                "difficulty": q.difficulty,
            },
        )

    async def _send_private_results(self, summary) -> None:  # type: ignore[no-untyped-def]
        """Emit each player's own result only to that player's sid."""
        for player in self.room.players.values():
            if player.is_bot or not player.sid:
                continue
            ans = summary.answers.get(player.id)
            if ans is None:
                continue
            await self.sio.emit(
                "answer_result",
                {
                    "question_idx": self.room.questions_asked - 1,
                    "your_choice": ans.option_idx,
                    "correct": ans.correct,
                    "correct_idx": summary.correct_idx,
                    "doubled": ans.doubled,
                    "points": ans.points,
                    "your_score": player.score,
                    # streak = post-round counter (0 if just missed); multiplier
                    # is what was actually applied to this round's score.
                    "streak": player.streak,
                    "streak_multiplier": ans.streak_multiplier,
                },
                to=player.sid,
            )

    async def _broadcast_round_end(self) -> None:
        """Public marker that the round closed. No correctness or scores."""
        await self._emit(
            "round_end",
            {"idx": self.room.questions_asked - 1},
        )

    async def _finish(self) -> None:
        winner = self.room.winner_name()
        leaderboard = self.room.leaderboard()
        await self._emit("game_over", {
            "leaderboard": leaderboard,
            "winner": winner,
        })
        # Persist.
        try:
            assert self.room.started_at is not None
            db.save_game(
                room_code=self.room.code,
                mode=self.room.mode,
                started_at=self.room.started_at.isoformat(),
                ended_at=(self.room.ended_at or datetime.now(timezone.utc)).isoformat(),
                winner_name=winner,
                players=[
                    {"name": p.name, "is_bot": p.is_bot, "final_score": p.score}
                    for p in self.room.players.values()
                ],
            )
        except Exception:
            log.exception("[%s] failed to persist game", self.room.code)

    # --- Helpers ---------------------------------------------------------

    async def _emit(self, event: str, payload: dict) -> None:
        await self.sio.emit(event, payload, room=self.room.code)

    async def _emit_error(self, message: str) -> None:
        await self.sio.emit("error", {"message": message}, room=self.room.code)


# --- Standalone helper used by socket handlers -------------------------------

def random_seed_jitter() -> None:
    """Re-seed the global RNG so room codes / shuffles are unpredictable
    across processes that import the module at the same boot moment."""
    random.seed()
