# Exercise 2 — Real-time Multiplayer Trivia

Live status of the project. Updated as we ship.

## What it is

Real-time multiplayer trivia per Assignment #3, Exercise 2. Two play modes:

- **vs Computer** — solo + 3 bots, instant start.
- **vs Friends** — host generates a QR code; players scan, pick name, host starts when ready.

10 questions per game, 15s each, server-authoritative timing. Adaptive difficulty.
3 helps per player (50/50, Call-a-Friend via PydanticAI/OpenAI, Double-Score). Chat
with quick emoji bar. Final leaderboard at the end. Per-question correctness is
**private** — only the answering player sees their own ✓/✗ and points.

## Run it

One command:

```bash
./run.sh           # dev (uvicorn --reload + next dev)
./run.sh --prod    # uvicorn + next build && next start
```

First run auto-creates `.venv`, installs Python + npm deps, copies `.env` /
`.env.local` from examples.

LAN play (iPhone scanning the QR): set `frontend/.env.local`

```
NEXT_PUBLIC_API_URL=http://<host-LAN-IP>:8000
```

then open `http://<host-LAN-IP>:3000/host` on the host machine — the QR will
encode that IP so phones on the same Wi-Fi can scan and join.

Tunnel play: run pinggy/ngrok against ports 8000 and 3000, set the public
backend URL in `.env.local`, host opens the public frontend URL.

## Stack

- **Server**: FastAPI + `python-socketio` (ASGI), uvicorn
- **DB**: SQLite (existing `trivia.db` for questions; `games` + `game_players` tables for history)
- **LLM**: `pydantic-ai` → OpenAI (`gpt-4o-mini` by default; set in `backend/.env`)
- **Frontend**: Next.js 14 (App Router) + React + TypeScript strict + Tailwind + Framer Motion + qrcode.react + socket.io-client
- **Tunnel**: pinggy/ngrok (manual, optional)

## Layout

```
backend/
  main.py                # FastAPI + Socket.IO ASGI bootstrap, /health
  manager.py             # GameManager — room/runner/sid registry
  socket_handlers.py     # Socket.IO events; pure transport
  llm.py                 # PydanticAI call-a-friend agent (graceful fallback)
  models.py              # Pydantic schemas for inbound events
  db.py                  # questions reader + game persistence
  schema.sql             # games, game_players
  config.py              # all tunable constants
  game/
    room.py              # Room state machine (lobby→countdown→question→…→ended)
    runner.py            # async game loop, bot tasks, emits
    player.py            # Player (humans + bots, same class)
    scoring.py           # pure points formula
    adaptive.py          # next-difficulty selector
    bots.py              # bot delay + correctness probability
  tests/                 # 22 tests (engine + 1 socket integration)

frontend/
  app/
    page.tsx             # mode picker
    cpu/page.tsx         # name → instant CPU game
    host/page.tsx        # name → QR + lobby → start
    join/[code]/page.tsx # scan-target page
  hooks/useGameSocket.ts # connection + game state machine
  lib/socket.ts          # singleton client
  lib/types.ts           # shared event payload types (mirrors backend)
  components/            # Lobby, QRPanel, Countdown, Timer, QuestionView,
                         # PersonalResult, Helps, FriendModal, Chat,
                         # FinalLeaderboard, NameForm, Game (phase router)
```

## Game flow (per room)

```
LOBBY ──host_start──► COUNTDOWN(3s) ──► QUESTION(15s) ──► [private answer_result]
                                            │                       │
                                            └──── 9 more times ────►│
                                                                    │
                                                                ENDED ► game_over (public leaderboard)
```

- `QUESTION` always runs the **full 15 seconds** — no early exit when all answered.
- After 15s server emits, **per sid**, `answer_result` (own correctness + points + correct option index + own running score). Then it broadcasts a public `round_end` (no scores).
- Final `game_over` is the only **public** reveal — full ranked leaderboard + winner.

## Socket contract

**Client → Server**
- `create_room` `{mode: "cpu"|"friends", name}` → ack with `room_code, player_id, is_host, players`
- `join_room` `{room_code, name}` → same ack shape
- `start_game` (host only)
- `submit_answer` `{question_idx, option_idx}`
- `use_help` `{type: "fifty"|"friend"|"double"}` → ack carries help payload
- `chat` `{text}` (emoji is unicode in text)

**Server → Room (broadcast)**
- `lobby_update {players, host_id}`
- `game_starting {countdown_seconds}`
- `question {idx, text, options[4], time_limit, difficulty}` (no correct answer)
- `answer_received {player_id}` — social cue only, no correctness
- `round_end {idx}` — round closed, no scores
- `chat_msg {player_id, name, text}`
- `game_over {leaderboard, winner}`
- `error {message}`

**Server → single sid (private)**
- `answer_result {question_idx, your_choice, correct, correct_idx, doubled, points, your_score}`

## Scoring

```
points = 0                                                  if wrong / timeout
       = round(500 + 500 * (1 - elapsed / 15))              if correct
       = doubled if Double-Score was armed before answering
```
Server timestamps arrival; `client_ts` ignored for fairness.

## Bots

- Solo human (any mode) → fill to 3 bots from `BOT_NAME_POOL`.
- Per question, scheduled at `random.uniform(BOT_MIN_DELAY=3, QUESTION_TIME-1)` seconds.
- Correctness probability `clamp(1.05 - difficulty/10, 0.25, 0.95)` — harder Q, more misses.
- Bots cannot use helps.

## Adaptive difficulty

After each question, server computes `human_correct_pct`:
- `>= 0.6` → `+1` difficulty (cap 10)
- `<= 0.3` → `-1` (floor 1)
- else → keep
DB query widens band ±1 if no exact-difficulty unused question is left.

## Persistence (`trivia.db`)

- `questions` (read-only, 266 rows): `Question, Option_1..4, Correct_Answer, Difficulty`.
- `games`: `id, room_code, mode, started_at, ended_at, winner_name`.
- `game_players`: `game_id, name, is_bot, final_score`.

Written on `game_over`. Inspect:
```
sqlite3 trivia.db "SELECT * FROM games ORDER BY id DESC LIMIT 5;"
```

## Tests

```
source .venv/bin/activate
python -m pytest backend/tests/ -v
```

22 tests:
- `test_scoring.py` — 5 cases for the points formula
- `test_adaptive.py` — 6 cases for difficulty selector
- `test_bots.py` — 4 cases for bot delay / pick / probability
- `test_room.py` — 6 cases including a full 10-question game loop
- `test_integration_socket.py` — full game over real Socket.IO via uvicorn in a thread

## PDF requirements — coverage

| Requirement | Status |
|---|---|
| 250+ trivia Qs, difficulty 1-10, 3 wrong + 1 correct, csv → SQLite | ✅ 266 questions in `trivia.db` |
| Multiplayer server with python + socket.io | ✅ |
| Frontend (any) | ✅ Next.js + React |
| Matchmaking before game | ⚠️ replaced — host-start in friends mode (your spec); instant CPU |
| 10 questions per game | ✅ |
| 4 options, choose correct | ✅ |
| Question shown for "a couple of seconds" | ✅ 15s (configurable in `config.QUESTION_TIME`) |
| Faster correct → more points; wrong → 0 | ✅ |
| Final leaderboard + winner | ✅ |
| 1-3 bots when single human | ✅ 3 bots whenever 1 human is in the room (any mode) |
| Bots delayed and sometimes wrong | ✅ |
| 3 helps: 50/50, Call-a-Friend (PydanticAI), Double-Score | ✅ |
| Chat / emojis | ✅ both — text input + quick emoji bar |
| Adaptive difficulty | ✅ aggregate human accuracy, ±1 |
| SQLite for some data | ✅ game history persisted |
| Tunnel for friends to play (pinggy/ngrok) | ⚠️ supported, manual |
| ≥ 2 extra features | ✅ QR-code multiplayer, Framer Motion animations, WebAudio feedback tones, mobile-first responsive layout, private per-player reveal |

## Code quality

- Separation of concerns enforced by folders. `game/` is pure logic. `socket_handlers.py` is transport. `db.py` is persistence. `llm.py` is the only OpenAI caller.
- Type hints on every public Python function. TypeScript strict on the frontend.
- Pure scoring + adaptive functions, unit tested.
- `asyncio.create_task`s tracked on the runner for cancellation on disconnect.
- Socket handlers wrap logic in try/except → emit `error` event instead of crashing. LLM failures degrade to a canned witty fallback.
- Constants live in `config.py` / `tailwind.config.ts`. No magic numbers in logic files.
- No dead code (Scoreboard / RevealPanel removed when their feature was dropped).

## Open / nice-to-haves

- Hall-of-Fame `/api/games` endpoint reading from `games` table.
- Confetti on win.
- Restart-room button on the leaderboard screen (currently navigate to `/`).
