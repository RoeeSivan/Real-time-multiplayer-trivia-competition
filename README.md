# Real-time Multiplayer Trivia

Real-time multiplayer trivia game built for Assignment #3, Exercise 2. Two play modes (vs Computer / vs Friends), 10 questions per game, 15s each, server-authoritative timing, adaptive difficulty, three helps (50/50, Call-a-Friend via PydanticAI/OpenAI, Double-Score), live chat with emojis, and a final leaderboard.

## Live demo

- **Play**: https://trivia-frontend-laro.onrender.com
- **Host a friends game**: https://trivia-frontend-laro.onrender.com/host
- **Backend (Socket.IO + FastAPI)**: https://trivia-backend-ze83.onrender.com

> Hosted on Render free tier — first request after idle wakes the service (~50s cold start), then it's snappy.

### How to play with friends

1. Open https://trivia-frontend-laro.onrender.com/host on your machine.
2. Pick a name → a QR code + room code appear.
3. Friends scan the QR (or open `https://trivia-frontend-laro.onrender.com/join/<CODE>`), pick a name, join.
4. Host clicks **Start** → 3-2-1 → 10 questions → leaderboard.

For solo, hit https://trivia-frontend-laro.onrender.com/cpu — instant game with 3 bots.

## Stack

- **Backend**: FastAPI + `python-socketio` (ASGI), uvicorn
- **Frontend**: Next.js 14 (App Router) + React + TypeScript strict + Tailwind + Framer Motion + qrcode.react + socket.io-client
- **DB**: SQLite — 266 questions in `trivia.db`, `games` + `game_players` tables for history
- **LLM**: PydanticAI → OpenAI (`gpt-4o-mini`) for Call-a-Friend
- **Deploy**: Render (two services — backend web service + frontend web service)

## Run locally

```bash
./run.sh           # dev (uvicorn --reload + next dev)
./run.sh --prod    # uvicorn + next build && next start
```

First run auto-creates `.venv`, installs Python + npm deps, copies `.env` / `.env.local` from examples.

### LAN play (phone scans QR on same Wi-Fi)

Set `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://<host-LAN-IP>:8000
```

Open `http://<host-LAN-IP>:3000/host` on the host machine — QR encodes that IP so phones on the same Wi-Fi can scan and join.

### Tunnel play (any network)

Run pinggy/ngrok against ports 8000 and 3000, set the public backend URL in `frontend/.env.local`, host opens the public frontend URL. Or just use the Render deploy above.

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

## Game flow

```
LOBBY ──host_start──► COUNTDOWN(3s) ──► QUESTION(15s) ──► [private answer_result]
                                            │                       │
                                            └──── 9 more times ────►│
                                                                    │
                                                                ENDED ► game_over (public leaderboard)
```

- Each `QUESTION` runs the **full 15 seconds** — no early exit when all answered.
- After 15s the server emits, **per sid**, `answer_result` (own correctness + points + correct option index + own running score), then broadcasts a public `round_end` (no scores).
- The final `game_over` is the only **public** reveal — full ranked leaderboard + winner.

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

Server timestamps arrival; `client_ts` is ignored for fairness.

## Bots

- Whenever a single human is in a room (any mode) → fill to 3 bots from `BOT_NAME_POOL`.
- Per question, scheduled at `random.uniform(BOT_MIN_DELAY=3, QUESTION_TIME-1)` seconds.
- Correctness probability `clamp(1.05 - difficulty/10, 0.25, 0.95)` — harder Q, more misses.
- Bots cannot use helps.

## Adaptive difficulty

After each question, server computes `human_correct_pct`:

- `>= 0.6` → `+1` difficulty (cap 10)
- `<= 0.3` → `-1` (floor 1)
- else → keep

DB query widens the band ±1 if no exact-difficulty unused question is left.

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
| Matchmaking before game | ⚠️ replaced — host-start in friends mode; instant CPU |
| 10 questions per game | ✅ |
| 4 options, choose correct | ✅ |
| Question shown for "a couple of seconds" | ✅ 15s (configurable in `config.QUESTION_TIME`) |
| Faster correct → more points; wrong → 0 | ✅ |
| Final leaderboard + winner | ✅ |
| 1-3 bots when single human | ✅ 3 bots whenever 1 human is in the room |
| Bots delayed and sometimes wrong | ✅ |
| 3 helps: 50/50, Call-a-Friend (PydanticAI), Double-Score | ✅ |
| Chat / emojis | ✅ both — text input + quick emoji bar |
| Adaptive difficulty | ✅ aggregate human accuracy, ±1 |
| SQLite for some data | ✅ game history persisted |
| Tunnel for friends to play | ✅ deployed on Render (also supports manual pinggy/ngrok) |
| ≥ 2 extra features | ✅ QR-code multiplayer, Framer Motion animations, WebAudio feedback tones, mobile-first responsive layout, private per-player reveal, public Render deploy |

## Deploy notes (Render)

Two web services on Render — one for backend, one for frontend.

**Backend service**
- Root: `backend/`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Env: `OPENAI_API_KEY`

**Frontend service**
- Root: `frontend/`
- Build: `npm ci && npm run build`
- Start: `npm start`
- Env: `NEXT_PUBLIC_API_URL=https://trivia-backend-ze83.onrender.com`

CORS on the backend allows the frontend origin so the Socket.IO handshake succeeds across the two domains.
