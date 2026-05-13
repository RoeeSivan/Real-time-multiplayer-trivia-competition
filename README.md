# Real-time Multiplayer Trivia

Real-time multiplayer trivia for Assignment #3, Exercise 2. Two modes (vs Computer / vs Friends), 10 questions × 15s, server-authoritative timing, adaptive difficulty, three helps (50/50, Call-a-Friend via PydanticAI/OpenAI, Double-Score), live chat with emojis, final leaderboard.

## Play it

- **Play**: https://trivia-frontend-laro.onrender.com
- **Host friends game**: https://trivia-frontend-laro.onrender.com/host
- **Backend (Socket.IO + FastAPI)**: https://trivia-backend-ze83.onrender.com

Both services are pinged every 10 min by cron-job.org → always warm, no cold-start delay.

### Friends game

1. Open https://trivia-frontend-laro.onrender.com/host on your machine.
2. Pick a name → QR code + room code appear.
3. Friends scan the QR (or open `/join/<CODE>`), pick a name, join.
4. Host clicks **Start** → 3-2-1 → 10 questions → leaderboard.

Solo? https://trivia-frontend-laro.onrender.com/cpu — instant game with 3 bots.

## Stack

- **Backend**: FastAPI + `python-socketio` (ASGI), uvicorn
- **Frontend**: Next.js 14 + React + TypeScript strict + Tailwind + Framer Motion + qrcode.react + socket.io-client
- **DB**: SQLite — 266 questions in `trivia.db`, plus `games` + `game_players` history tables
- **LLM**: PydanticAI → OpenAI (`gpt-4o-mini`) for Call-a-Friend
- **Deploy**: Render (two web services) + cron-job.org keep-alive

## Run locally

```bash
./run.sh           # dev (uvicorn --reload + next dev)
./run.sh --prod    # uvicorn + next build && next start
```

First run auto-creates `.venv`, installs deps, copies `.env` / `.env.local` from examples.

**LAN play (phone QR scan, same Wi-Fi):** set `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://<host-LAN-IP>:8000
```
Open `http://<host-LAN-IP>:3000/host` on the host. QR encodes that IP so phones can scan + join.

**Tunnel play (any network):** run pinggy/ngrok against ports 8000 and 3000, set the public backend URL in `frontend/.env.local`. Or just use the Render deploy above.

## Layout

```
backend/
  main.py              # FastAPI + Socket.IO bootstrap, /health
  manager.py           # GameManager — room/runner/sid registry
  socket_handlers.py   # Socket.IO events (transport only)
  llm.py               # PydanticAI call-a-friend agent (graceful fallback)
  models.py            # Pydantic schemas
  db.py, schema.sql    # questions + persistence
  config.py            # tunable constants
  game/                # pure logic: room, runner, player, scoring, adaptive, bots
  tests/               # 22 tests

frontend/
  app/                 # page.tsx, cpu/, host/, join/[code]/
  hooks/useGameSocket.ts
  lib/socket.ts, lib/types.ts
  components/          # Lobby, QRPanel, Countdown, Timer, QuestionView,
                       # PersonalResult, Helps, FriendModal, Chat,
                       # FinalLeaderboard, NameForm, Game
```

## Game flow

```
LOBBY → COUNTDOWN(3s) → QUESTION(15s) → [private answer_result]
                            └── ×10 ──┘ → ENDED → game_over (public leaderboard)
```

- Each question runs the **full 15s** — no early exit when all answered.
- After 15s the server emits, **per sid**, `answer_result` (own correctness + points + correct idx + own running score), then broadcasts public `round_end` (no scores).
- `game_over` is the only **public** reveal — full leaderboard + winner.

## Socket contract

**Client → Server**
- `create_room {mode, name}` → ack `{room_code, player_id, is_host, players}`
- `join_room {room_code, name}` → same ack
- `start_game` (host only)
- `submit_answer {question_idx, option_idx}`
- `use_help {type: "fifty"|"friend"|"double"}` → ack with help payload
- `chat {text}` (emoji as unicode in text)

**Server → Room (broadcast)**
- `lobby_update {players, host_id}`
- `game_starting {countdown_seconds}`
- `question {idx, text, options[4], time_limit, difficulty}`
- `answer_received {player_id}` (social cue only)
- `round_end {idx}` (no scores)
- `chat_msg {player_id, name, text}`
- `game_over {leaderboard, winner}`
- `error {message}`

**Server → single sid (private)**
- `answer_result {question_idx, your_choice, correct, correct_idx, doubled, points, your_score}`

## Scoring

```
points = 0                                       if wrong / timeout
       = round(500 + 500 * (1 - elapsed / 15))   if correct
       = doubled if Double-Score armed before answering
```
Server timestamps arrival; `client_ts` is ignored for fairness.

## Bots

- Solo human (any mode) → fill to 3 bots from `BOT_NAME_POOL`.
- Per question: `random.uniform(BOT_MIN_DELAY=3, QUESTION_TIME-1)` seconds.
- Correctness: `clamp(1.05 - difficulty/10, 0.25, 0.95)` — harder Q, more misses.
- Bots cannot use helps.

## Adaptive difficulty

Per round, `human_correct_pct`:
- `>= 0.6` → +1 (cap 10)
- `<= 0.3` → -1 (floor 1)
- else → keep

DB widens ±1 if no exact-difficulty unused question remains.

## Persistence (`trivia.db`)

- `questions` (read-only, 266 rows): `Question, Option_1..4, Correct_Answer, Difficulty`
- `games`: `id, room_code, mode, started_at, ended_at, winner_name`
- `game_players`: `game_id, name, is_bot, final_score`

Written on `game_over`:
```bash
sqlite3 trivia.db "SELECT * FROM games ORDER BY id DESC LIMIT 5;"
```

## Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests/ -v
```

22 tests across scoring, adaptive, bots, room state machine, and one full Socket.IO integration via uvicorn in a thread.

## Requirements coverage

| Requirement | Status |
|---|---|
| 250+ Qs, difficulty 1-10, csv → SQLite | ✅ 266 in `trivia.db` |
| Multiplayer (python + socket.io) | ✅ |
| Frontend | ✅ Next.js + React |
| Matchmaking | ⚠️ replaced — host-start friends; instant CPU |
| 10 questions per game | ✅ |
| 4 options, 1 correct | ✅ |
| Timed question | ✅ 15s (`config.QUESTION_TIME`) |
| Faster correct → more points | ✅ |
| Final leaderboard + winner | ✅ |
| 1-3 bots when single human | ✅ |
| Bots delayed + sometimes wrong | ✅ |
| 3 helps | ✅ 50/50, Call-a-Friend (PydanticAI), Double-Score |
| Chat / emojis | ✅ text + quick emoji bar |
| Adaptive difficulty | ✅ |
| SQLite | ✅ game history |
| Friends-anywhere tunnel | ✅ Render deploy (pinggy/ngrok also supported) |
| ≥ 2 extra features | ✅ QR-code multiplayer, Framer Motion, WebAudio, mobile-first, private reveal, always-on Render deploy |

## Deploy (Render)

Two web services.

**Backend** — root `backend/`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`, env `OPENAI_API_KEY`.

**Frontend** — root `frontend/`, build `npm ci && npm run build`, start `npm start`, env `NEXT_PUBLIC_API_URL=https://trivia-backend-ze83.onrender.com`.

CORS on the backend allows the frontend origin so the Socket.IO handshake succeeds across both domains.

**Keep-alive**: cron-job.org pings `/health` and frontend root every 10 min. Render free tier sleeps after 15 min idle, so this keeps both services warm 24/7 within the 750 hr/mo free quota.
