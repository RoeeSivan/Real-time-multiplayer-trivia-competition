# Exercise 2 — Real-time Multiplayer Trivia

Live status. Updated as we ship.

## What it is

Real-time multiplayer trivia per Assignment #3, Exercise 2. Two modes:
- **vs Computer** — solo + 3 bots, instant.
- **vs Friends** — host shows QR, players scan + join, host starts.

10 questions × 15s, server-authoritative timing, adaptive difficulty. 3 helps per player (50/50, Call-a-Friend via PydanticAI/OpenAI, Double-Score). Chat with emoji bar. Final leaderboard. Per-question correctness is **private** — only the answering player sees their own ✓/✗ + points.

## Live URLs

- **Play**: https://trivia-frontend-laro.onrender.com
- **API**: https://trivia-backend-ze83.onrender.com

Both services kept warm 24/7 by cron-job.org pings every 10 min → no cold-start delay.

## Run locally

```bash
./run.sh           # dev (uvicorn --reload + next dev)
./run.sh --prod    # uvicorn + next build && next start
```

First run auto-creates `.venv`, installs deps, copies `.env` / `.env.local` from examples.

**LAN play (phone QR scan):** set `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://<host-LAN-IP>:8000
```
Open `http://<host-LAN-IP>:3000/host`.

## Stack

- **Backend**: FastAPI + `python-socketio` (ASGI), uvicorn
- **Frontend**: Next.js 14 + React + TypeScript strict + Tailwind + Framer Motion + qrcode.react + socket.io-client
- **DB**: SQLite — 266 questions; `games` + `game_players` tables for history
- **LLM**: PydanticAI → OpenAI `gpt-4o-mini` for Call-a-Friend
- **Deploy**: Render (two web services) + cron-job.org keep-alive

## Layout

```
backend/
  main.py              # FastAPI + Socket.IO ASGI bootstrap, /health
  manager.py           # GameManager — room/runner/sid registry
  socket_handlers.py   # Socket.IO events (pure transport)
  llm.py               # PydanticAI call-a-friend agent (graceful fallback)
  models.py            # Pydantic schemas
  db.py                # questions reader + game persistence
  schema.sql, config.py
  game/                # pure logic: room, runner, player, scoring, adaptive, bots
  tests/               # 22 tests (engine + 1 socket integration)

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

- `QUESTION` runs full 15s, no early exit.
- After 15s, server emits **per sid** `answer_result` (own ✓/✗ + points + correct idx + own running score), then broadcasts public `round_end` (no scores).
- `game_over` is the only **public** reveal — ranked leaderboard + winner.

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
- `question {idx, text, options[4], time_limit, difficulty}` (no answer)
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
Server timestamps arrival; `client_ts` ignored for fairness.

## Bots

- Solo human (any mode) → fill to 3 bots from `BOT_NAME_POOL`.
- Per question: `random.uniform(BOT_MIN_DELAY=3, QUESTION_TIME-1)` seconds.
- Correctness: `clamp(1.05 - difficulty/10, 0.25, 0.95)` — harder Q, more misses.
- Bots cannot use helps.

## Adaptive difficulty

Per round, server computes `human_correct_pct`:
- `>= 0.6` → +1 (cap 10)
- `<= 0.3` → -1 (floor 1)
- else → keep

DB query widens ±1 if no exact-difficulty unused question remains.

## Persistence (`trivia.db`)

- `questions` (read-only, 266 rows): `Question, Option_1..4, Correct_Answer, Difficulty`
- `games`: `id, room_code, mode, started_at, ended_at, winner_name`
- `game_players`: `game_id, name, is_bot, final_score`

Written on `game_over`. Inspect:
```bash
sqlite3 trivia.db "SELECT * FROM games ORDER BY id DESC LIMIT 5;"
```

## Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests/ -v
```

22 tests across scoring, adaptive, bots, room state machine, and one full Socket.IO integration via uvicorn in a thread.

## PDF requirements — coverage

| Requirement | Status |
|---|---|
| 250+ Qs, difficulty 1-10, csv → SQLite | ✅ 266 in `trivia.db` |
| Multiplayer server (python + socket.io) | ✅ |
| Frontend | ✅ Next.js + React |
| Matchmaking | ⚠️ replaced — host-start friends mode; instant CPU |
| 10 questions per game | ✅ |
| 4 options, 1 correct | ✅ |
| Timed question | ✅ 15s (`config.QUESTION_TIME`) |
| Faster correct → more points; wrong → 0 | ✅ |
| Final leaderboard + winner | ✅ |
| 1-3 bots when single human | ✅ |
| Bots delayed + sometimes wrong | ✅ |
| 3 helps (50/50, Call-a-Friend, Double-Score) | ✅ |
| Chat / emojis | ✅ text + quick emoji bar |
| Adaptive difficulty | ✅ |
| SQLite | ✅ game history persisted |
| Friends-anywhere tunnel | ✅ Render deploy (pinggy/ngrok also supported) |
| ≥ 2 extra features | ✅ QR-code multiplayer, Framer Motion, WebAudio, mobile-first, private reveal, always-on Render deploy |

## Code quality

- `game/` is pure logic. `socket_handlers.py` is transport. `db.py` is persistence. `llm.py` is the only OpenAI caller.
- Type hints on every public Python function. TypeScript strict on frontend.
- Pure scoring + adaptive functions, unit tested.
- `asyncio.create_task`s tracked on the runner; cancelled on disconnect.
- Socket handlers wrap logic in try/except → emit `error` event instead of crashing. LLM failures degrade to a canned fallback.
- Constants in `config.py` / `tailwind.config.ts`. No magic numbers in logic files.

## Deploy (Render)

Two web services.

**Backend** — root `backend/`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`, env `OPENAI_API_KEY`.

**Frontend** — root `frontend/`, build `npm ci && npm run build`, start `npm start`, env `NEXT_PUBLIC_API_URL=https://trivia-backend-ze83.onrender.com`.

CORS allows the frontend origin so the Socket.IO handshake works across both domains.

**Keep-alive**: cron-job.org pings `/health` (backend) and `/` (frontend) every 10 min. Render free tier sleeps after 15 min idle, so this keeps both services warm 24/7.

## Manual QA checklist

Before the demo / submission, walk through this on the live URL.

### A. Solo (vs Computer)
- [ ] Home loads — both cards visible.
- [ ] vs Computer → name form. Empty name = Start disabled.
- [ ] Game launches with 3 bots. Countdown 3→2→1→GO.
- [ ] Q1 shows text + 4 options + 15s timer + difficulty badge.
- [ ] Click option → highlights, "Selected A. You can still change..." appears.
- [ ] Re-click different option → first clears, new highlights.
- [ ] Timer → 0 → personal feedback ✓/✗ + points.
- [ ] No public scoreboard during round (own score chip + player list only).
- [ ] Difficulty trends with accuracy.
- [ ] Bots answer at varied times.
- [ ] 10 questions → final leaderboard + winner + medals.
- [ ] Play again → returns to mode picker.

### B. Helps (CPU game)
- [ ] **50/50** — 2 wrong options grayed/struck. Button disables (one-shot).
- [ ] **Call a Friend** — modal with 1-2 sentence advice (real witty or canned fallback if no `OPENAI_API_KEY`).
- [ ] **Double Score** — armed before answering → "Double Score armed". Correct answer → `2×`. Activating after a correct tentative answer → still 2×.
- [ ] Each help one-shot per game.

### C. Multiplayer (vs Friends)
- [ ] Mac → vs Friends → name → QR + lobby + code (e.g. `VO8SY`).
- [ ] iPhone scans QR → `/join/<CODE>` → name → Join.
- [ ] Mac lobby updates (host + iPhone player).
- [ ] Start Game → both enter countdown together.
- [ ] Both screens show same question + difficulty.
- [ ] Each only sees own ✓/✗ between rounds.
- [ ] Final leaderboard ranks both correctly.

### D. Chat
- [ ] Text → both screens see it with sender name.
- [ ] Quick emoji bar → both see it.
- [ ] >200 chars truncated.

### E. Resilience
- [ ] iPhone screen lock 5s mid-question → unlock → in sync.
- [ ] Force-close iPhone Safari mid-game → reopen URL → no auto-rejoin (intentional fresh load).
- [ ] Two simultaneous CPU games (Mac + iPhone, different rooms) → no crosstalk.

### F. Submission
- [ ] Record vs Friends game (host + phone visible) ~3 min.
- [ ] Capture Call-a-Friend modal in the recording.
- [ ] Demo change-answer feature on camera.

---

## Backlog

### Quick wins
- [x] **Keep-alive cron pinger** — cron-job.org hits `/health` and frontend root every 10 min. Both services warm 24/7. Done 2026-05-13.
- [ ] **Cold-start hint** — even with keep-alive, an occasional Render restart can hit a fresh user. Show "Backend waking up — up to 30s on free hosting" if connect takes >5s.
- [ ] **Restart-room button** on leaderboard — fresh round with same players instead of nav back to `/`.
- [ ] **Confetti on win** — `canvas-confetti`, ~5 KB.
- [ ] **Title contrast** — bump home-title legibility (drop-shadow or solid color + accent underline).

### Polish
- [ ] **Sound on/off toggle** — WebAudio cue is on by default; demos may want silence.
- [ ] **Keyboard shortcuts** — `1/2/3/4` answer, `H` for help menu.
- [ ] **Avatar / color per player** — emoji or initials chip in lobby/leaderboard.
- [ ] **Per-question score breakdown** — flying "+750" near score chip.
- [ ] **Animated correct-answer reveal** — flash green on correct option after round (private).

### Real features
- [ ] **Hall of Fame** — `/api/games` endpoint + `/hall-of-fame` page reading `games` + `game_players`. Lifetime ranking.
- [ ] **Persistent game history on Render** — `trivia.db` is ephemeral on free tier. Either attach Render Persistent Disk ($1/mo) or migrate to Neon Postgres (free).
- [ ] **Reconnect grace period config** — rooms tear down 60s after game end. Make configurable + expose hint.
- [ ] **Per-player help loadouts** — host picks which 3 helps the room uses.
- [ ] **Question categories** — tag history/science/sports; host filters.

### Hardening
- [ ] **Tighten CORS allowlist** — verify dev fallback (`*`) triggers only when `FRONTEND_URL` env var unset.
- [ ] **Server-side chat rate-limit** — currently 1/event from frontend; server should throttle (e.g. 5/sec/sid).
- [ ] **Server-side name validation** — optional profanity filter.
- [ ] **Disconnect-mid-game UX** — show dropped players as `(disconnected)` in host lobby.
- [ ] **Replace deprecated `websockets.legacy`** — surfaced by tests.

### Submission
- [ ] Record full vs Friends game including all 3 helps + chat + change-answer.
- [ ] Upload zip to Moodle as `assignment3-exercise2.zip` (exclude `.venv`, `node_modules`, `.next`, `.gstack`).
- [ ] Fill submission Google Form with video links.
