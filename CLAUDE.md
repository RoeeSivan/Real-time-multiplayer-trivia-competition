# Exercise 2 — Real-time Multiplayer Trivia

## Context

Build real-time multiplayer trivia per Assignment #3, Exercise 2. Question DB already exists at `trivia.db` (266 rows, schema: `Question, Option_1..4, Correct_Answer, Difficulty 1-10`). Two play modes:

- **vs Computer** — solo + 1-3 bots, instant start.
- **vs Friends** — host generates a QR code; players scan, pick name, host starts when ready.

Backend: Python + FastAPI + `python-socketio` + SQLite. Frontend: Next.js + React (later phase). LLM "call-a-friend" via PydanticAI → OpenAI (`gpt-4o-mini`).

Plan focuses on backend first, per user direction.

---

## Decisions (locked)

| Topic | Choice |
|---|---|
| Friends mode start | Host clicks Start (no 30s timer) |
| vs-Computer start | Instant, 1-3 bots auto-fill |
| LLM | OpenAI via PydanticAI |
| Persistence | Game history only (rooms, players, final scores) |
| Questions per game | 10 |
| Question time | 15s (configurable) |
| Scoring | Faster = more; correct only; 0 if wrong |
| Helps per player | 50/50, Call-a-Friend, Double-Score (one of each) |
| Adaptive difficulty | Based on aggregate human accuracy on prev question |
| Chat | Text + emoji during game |

---

## Tech Stack

- **Server**: FastAPI + `python-socketio` (ASGI mount) on uvicorn
- **DB**: SQLite (existing `trivia.db` for questions; add tables for game history)
- **LLM**: `pydantic-ai` + `openai`
- **QR**: frontend generates QR for join URL (no server lib needed); backend exposes `room_code`
- **Tunnel**: pinggy or ngrok for friends-over-internet play
- **Frontend** (later): Next.js 14 (app router), React, `socket.io-client`, `qrcode.react`

---

## Backend Layout

```
backend/
  main.py                # FastAPI app + socketio ASGI mount + CORS
  socket_handlers.py     # @sio.event handlers (connect, join, start, answer, help, chat...)
  config.py              # constants (Q_TIME, GAME_QS, BOT_NAMES, etc.)
  db.py                  # connection, get_random_question(difficulty), save_game()
  schema.sql             # extra tables (games, game_players)
  game/
    room.py              # Room class — state machine, players, current_q, timers
    player.py            # Player / BotPlayer classes
    scoring.py           # time-to-points formula
    bots.py              # bot answer scheduler (delay + accuracy by difficulty)
    adaptive.py          # next-difficulty selector
  llm.py                 # PydanticAI agent for call-a-friend
  models.py              # pydantic event payloads
  requirements.txt
  .env.example           # OPENAI_API_KEY
```

Single-process in-memory `rooms: dict[str, Room]`. No Redis (one host machine, ngrok exposure is enough for the assignment).

---

## Game State Machine (per Room)

```
LOBBY ──host_start──► COUNTDOWN(3s) ──► QUESTION(15s) ──► REVEAL(4s) ──► (next q | END)
                                            ▲                              │
                                            └─────────── 9 more times ─────┘
END ──► leaderboard broadcast, persist game
```

Each phase emits a socket event with phase-specific payload. Server is source of truth for timers (clients display, server enforces).

---

## Socket Events (contract)

**Client → Server**
- `create_room` `{mode: "friends"|"cpu", host_name}` → `room_created {room_code}`
- `join_room` `{room_code, name}` → `joined {player_id}` + `lobby_update` to room
- `start_game` (host only)
- `submit_answer` `{question_idx, option_idx, client_ts}`
- `use_help` `{type: "fifty"|"friend"|"double"}` → response `help_result`
- `chat` `{text}` (emoji = unicode in text)

**Server → Room**
- `lobby_update {players[]}`
- `game_starting {countdown_seconds}`
- `question {idx, text, options[4], time_limit, difficulty}` (Correct_Answer NOT sent)
- `answer_received {player_id}` (no reveal of correctness)
- `reveal {correct_idx, scores[], per_player_results}`
- `game_over {leaderboard, winner}`
- `chat_msg {player_id, name, text, ts}`
- `error {code, message}`

---

## Scoring

```
points = 0                                  if wrong / timeout
       = round(500 + 500 * (1 - elapsed/time_limit))   if correct
       = doubled if "double-score" used and correct
```
Server timestamps `submit_answer` arrival; ignores `client_ts` for fairness.

---

## Bots

- Single human → fill to N=3 with bots from a name pool.
- Per question, schedule each bot's answer at `random.uniform(3, time_limit-1)` seconds.
- Correctness probability = `clamp(1.05 - difficulty/10, 0.25, 0.95)` (harder Q → bot more likely to err).
- Bots cannot use helps (simpler).

---

## Adaptive Difficulty

After each question, compute `human_correct_pct`. Next question difficulty:
- `correct_pct >= 0.6` → bump difficulty `+1` (cap 10)
- `correct_pct <= 0.3` → drop `-1` (floor 1)
- else → keep
Pick a random unused question with `Difficulty == target` (fallback ±1).

---

## DB Extensions

`schema.sql` (run once on startup if tables missing):
```sql
CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_code TEXT,
  mode TEXT,
  started_at TEXT,
  ended_at TEXT,
  winner_name TEXT
);
CREATE TABLE IF NOT EXISTS game_players (
  game_id INTEGER REFERENCES games(id),
  name TEXT,
  is_bot INTEGER,
  final_score INTEGER
);
```

---

## Step-by-Step Implementation Plan (baby steps)

Each step is one focused commit. Backend first; frontend after step 11.

### Phase 0 — Repo
1. Create private GitHub repo (manual by user), invite `dk8827`. Push current files.
2. Add `.gitignore` (venv, __pycache__, .env, .next, node_modules).

### Phase 1 — Backend skeleton
3. `backend/` venv + `requirements.txt` (fastapi, uvicorn[standard], python-socketio, python-dotenv, pydantic-ai, openai). `pip install`.
4. `main.py`: FastAPI app, mount socketio ASGI, `/health` endpoint, CORS open. Run `uvicorn main:app --reload` → confirm 200 on `/health`.
5. Wire socket.io basic `connect`/`disconnect` handlers, log only. Test via a tiny `socket.io-client` script or curl polling.

### Phase 2 — DB layer
6. `db.py`: open `trivia.db` (read-only for questions); helper `get_random_question(target_difficulty, exclude_ids)`. Add an in-memory `id` (rowid) since table has no PK.
7. Run `schema.sql` on startup to create `games`, `game_players`. Add `save_game(room)` stub.

### Phase 3 — Game engine (no sockets)
8. `game/player.py`, `game/room.py`: `Room` class with `add_player`, `start_game`, `next_question`, `submit_answer`, `compute_scores`. Drive it in a unit test (`tests/test_room.py`) — 10-question loop end-to-end with stub players.
9. `game/scoring.py`, `game/adaptive.py`, `game/bots.py` — pure functions, unit-tested.

### Phase 4 — Socket layer
10. `socket_handlers.py`: implement events from contract above. Use `asyncio` tasks for question timers (`asyncio.create_task(question_timer(room))`). On timeout → emit reveal.
11. Friends-mode flow: `create_room` → `join_room` → `start_game`. Test with two `socket.io-client` Node scripts.
12. CPU-mode flow: `create_room mode=cpu` → server auto-spawns bots → instant start. Bots are dummy player objects in room; their answers scheduled via tasks.

### Phase 5 — Helps
13. `use_help fifty` → server returns 2 wrong indices to remove. Mark help as used per player.
14. `use_help double` → flag on player for current question; applied during scoring.
15. `llm.py`: PydanticAI agent. `use_help friend` → call agent with `{question, options}`, return advice string. Cache per-question per-player to avoid double-billing.

### Phase 6 — Chat + persistence
16. `chat` event → broadcast to room. Optional rate-limit (1/sec).
17. On `game_over`, write to `games` + `game_players`. Verify with `sqlite3` CLI.

### Phase 7 — Frontend (Next.js)
18. Scaffold `frontend/` with `create-next-app`. Pages: `/` (mode picker), `/host` (QR + lobby), `/join/[code]` (name input), `/play/[code]` (game).
19. Wire `socket.io-client`. Mode picker → vs-Computer routes straight into `/play`. vs-Friends → `/host` shows QR (`qrcode.react`) of `https://<host>/join/<code>`.
20. Game UI: question card, 4 option buttons, timer ring, scoreboard sidebar, chat panel.
21. Helps UI: 3 buttons. 50/50 dims removed options. Call-a-friend shows modal with LLM text. Double-score toggles indicator.
22. Leaderboard screen on `game_over`.

### Phase 8 — Polish & extras (≥2 required by PDF)
23. **Extra 1**: animated timer + answer reveal animations (Framer Motion).
24. **Extra 2**: post-game share card (export PNG of leaderboard) — or — global Hall of Fame page reading from `games` table.
25. (Optional) sound FX, keyboard 1-4 to answer.
26. ngrok/pinggy tunnel; play with friends.

---

## Critical Files to Create

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI + socketio ASGI bootstrap |
| `backend/socket_handlers.py` | All `@sio.event` handlers |
| `backend/game/room.py` | Room state machine |
| `backend/game/bots.py` | Bot answer scheduling |
| `backend/game/adaptive.py` | Difficulty selector |
| `backend/db.py` | Question fetch + game persistence |
| `backend/llm.py` | PydanticAI call-a-friend agent |
| `backend/schema.sql` | `games`, `game_players` tables |
| `backend/tests/test_room.py` | End-to-end game loop unit test |
| `frontend/` | Next.js app (phase 7) |

## Reused Existing Assets

- `trivia.db` — questions table (266 rows, ready)
- `final_267.csv` — original csv (kept for reference)
- `csv_to_sqlite.py`, `detect_duplicates.py` — dataset prep, not needed at runtime

---

## Verification

- **Phase 1**: `curl localhost:8000/health` → `{"ok":true}`.
- **Phase 3**: `pytest backend/tests/` → green; full 10-Q game runs in test.
- **Phase 4**: two terminal node clients connect, join, play, finish.
- **Phase 5**: each help triggers expected payload; OpenAI call returns advice.
- **Phase 6**: after game, `sqlite3 trivia.db "SELECT * FROM games;"` shows row.
- **End-to-end**: open 2 browsers, host scans own QR with phone, both play a full 10-Q game, leaderboard correct, chat works, helps work.

---

## Code Quality & Organization

Non-negotiable, applied every commit:

- **Separation of concerns** — folder structure already enforces it: `game/` is pure logic (no sockets, no DB), `socket_handlers.py` is transport only, `db.py` is persistence only, `llm.py` is the only file that talks to OpenAI. Easy to test, easy to swap.
- **One responsibility per file** — `room.py` owns state machine, `bots.py` owns bot scheduling, `scoring.py` owns the points formula, `adaptive.py` owns difficulty selection. No god-files.
- **Typed everything** — Pydantic models for every socket event payload (`models.py`). Type hints on every function signature. `mypy --strict` clean on `backend/`.
- **Pure functions where possible** — `scoring.compute_points()`, `adaptive.next_difficulty()` take inputs, return outputs, no side effects → trivially unit-testable.
- **No magic numbers** — all constants (`QUESTION_TIME=15`, `GAME_QUESTIONS=10`, `BOT_NAME_POOL=[...]`, `MIN_BOT_DELAY=3`) live in `config.py`.
- **Async correctness** — every `asyncio.create_task` stored on the Room so we can cancel on disconnect/cleanup. No fire-and-forget tasks.
- **Error boundaries** — socket handlers wrap logic in try/except, emit `error` event instead of crashing. LLM failures degrade to canned fallback.
- **Linting/formatting** — `ruff` + `black` configured via `pyproject.toml`. CI-style local check before each commit.
- **Tests live alongside code** — `backend/tests/` mirrors `backend/` layout. `test_room.py`, `test_scoring.py`, `test_adaptive.py`, `test_bots.py`. Pure-logic modules get unit tests; socket layer gets one end-to-end integration test.
- **Frontend** — same discipline: `components/` (presentational), `hooks/` (`useSocket`, `useGameState`), `lib/` (socket client singleton, types shared with backend events), `app/` (routes only). No business logic in page components.
- **Shared event types** — define socket event payload shapes once. Backend: pydantic models. Frontend: matching TypeScript types in `frontend/lib/events.ts`. Keep them in sync manually (small surface).
- **Commits** — small, focused, conventional-commits style (`feat(game): add adaptive difficulty selector`). Every commit leaves the project runnable.
- **No dead code** — if a step's experiment doesn't pan out, delete it; don't leave commented-out blocks.
- **Docstrings only where non-obvious** — public Room methods get one-line docstrings explaining invariants (e.g. "called only from QUESTION phase"). Trivial helpers get nothing.

## Open Risks / Notes

- Server-authoritative timing means clock drift on client is cosmetic only — fine.
- Single-process in-memory rooms = no horizontal scaling. Acceptable for assignment.
- OpenAI key required for call-a-friend; provide `.env.example`. If key missing, fall back to canned witty response (don't crash).
- `trivia.db` has no PK — use `rowid` as identifier when filtering used questions.
- After plan approval, copy this plan into project `CLAUDE.md` so it persists in repo.
