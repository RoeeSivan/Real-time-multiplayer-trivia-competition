"""Central configuration constants for the trivia server.

All tunable game parameters live here so behaviour can be tweaked without
touching game logic.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths ---
BACKEND_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = BACKEND_DIR.parent
DB_PATH: Path = PROJECT_ROOT / "trivia.db"
SCHEMA_PATH: Path = BACKEND_DIR / "schema.sql"

# --- Game timing (seconds) ---
QUESTION_TIME: int = 15
REVEAL_TIME: int = 4
START_COUNTDOWN: int = 3

# --- Game rules ---
GAME_QUESTIONS: int = 10
MIN_PLAYERS_TO_START: int = 1
TARGET_BOTS_FOR_SOLO: int = 3  # Up to this many bots when alone in CPU mode

# --- Scoring ---
BASE_POINTS: int = 500
MAX_BONUS: int = 500  # Earned for an instant correct answer

# --- Difficulty (matches DB column range) ---
DIFFICULTY_MIN: int = 1
DIFFICULTY_MAX: int = 10
DEFAULT_START_DIFFICULTY: int = 5
DIFFICULTY_UP_THRESHOLD: float = 0.6   # Aggregate human accuracy
DIFFICULTY_DOWN_THRESHOLD: float = 0.3

# --- Bots ---
BOT_MIN_DELAY: float = 3.0       # Earliest a bot will answer
BOT_MAX_DELAY_GAP: float = 1.0   # Latest = QUESTION_TIME - this
BOT_NAME_POOL: tuple[str, ...] = (
    "Buzz", "Quizzy", "Trivio", "Sage", "Brainy",
    "Echo", "Nova", "Pixel", "Kona", "Riff",
)

# --- LLM ---
LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
LLM_TIMEOUT_SECONDS: float = 8.0

# --- Misc ---
ROOM_CODE_LENGTH: int = 5
CHAT_MAX_LEN: int = 200
