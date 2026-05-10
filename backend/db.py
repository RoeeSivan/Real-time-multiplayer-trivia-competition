"""SQLite access layer.

Owns the single connection lifecycle and exposes high-level helpers for
question selection and game persistence. Game logic must not import sqlite3
directly — go through this module.
"""
from __future__ import annotations

import logging
import random
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator

from backend import config

log = logging.getLogger("trivia.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = _connect()
    try:
        yield conn.cursor()
    finally:
        conn.close()


# --- Schema ---

def init_schema() -> None:
    """Create persistence tables if missing. Idempotent."""
    sql = config.SCHEMA_PATH.read_text(encoding="utf-8")
    with cursor() as cur:
        cur.executescript(sql)


def count_questions() -> int:
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM questions")
        return int(cur.fetchone()["n"])


# --- Questions ---

def get_random_question(
    target_difficulty: int,
    exclude_rowids: Iterable[int] = (),
) -> sqlite3.Row | None:
    """Return one random unused question close to `target_difficulty`.

    Searches at exact difficulty first; widens the band by ±1 until a match
    is found or the entire 1-10 range is exhausted.
    """
    excluded = list(exclude_rowids)
    # Empty IN-list with NULL evaluates to NULL/false in SQL — sentinel -1
    # keeps the clause valid without filtering anything.
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        params_excl: list[int] = excluded
    else:
        placeholders = "?"
        params_excl = [-1]

    with cursor() as cur:
        for delta in range(0, config.DIFFICULTY_MAX):
            lo = max(config.DIFFICULTY_MIN, target_difficulty - delta)
            hi = min(config.DIFFICULTY_MAX, target_difficulty + delta)
            cur.execute(
                f"""
                SELECT rowid, Question, Option_1, Option_2, Option_3, Option_4,
                       Correct_Answer, Difficulty
                  FROM questions
                 WHERE Difficulty BETWEEN ? AND ?
                   AND rowid NOT IN ({placeholders})
                """,
                [lo, hi, *params_excl],
            )
            rows = cur.fetchall()
            if rows:
                return random.choice(rows)
    return None


# --- Game persistence ---

def save_game(
    *,
    room_code: str,
    mode: str,
    started_at: str,
    ended_at: str,
    winner_name: str | None,
    players: list[dict],
) -> int:
    """Insert a finished game and its players. Returns new game id."""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO games (room_code, mode, started_at, ended_at, winner_name)"
            " VALUES (?, ?, ?, ?, ?)",
            (room_code, mode, started_at, ended_at, winner_name),
        )
        game_id = int(cur.lastrowid)
        cur.executemany(
            "INSERT INTO game_players (game_id, name, is_bot, final_score)"
            " VALUES (?, ?, ?, ?)",
            [
                (game_id, p["name"], 1 if p["is_bot"] else 0, int(p["final_score"]))
                for p in players
            ],
        )
        log.info("Saved game id=%d players=%d", game_id, len(players))
        return game_id
