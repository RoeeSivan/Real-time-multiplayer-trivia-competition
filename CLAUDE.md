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

## Live URLs

- **Play** (frontend): https://trivia-frontend-laro.onrender.com
- **API** (backend, internal): https://trivia-backend-ze83.onrender.com

Free tier: backend sleeps after 15 min idle → first hit takes ~30s while the dyno wakes.

---

## Manual QA — your turn

The automated /qa pass on production confirmed the basics work. Before the
demo video / submission, walk through everything by hand. Open the live URL
and tick each item.

### A. Solo (vs Computer)
- [ ] Home loads on https://trivia-frontend-laro.onrender.com — both cards visible.
- [ ] Click **vs Computer** → name form appears.
- [ ] Empty name → Start button stays disabled.
- [ ] Type a name → Start enables → game launches with 3 bots in the player list.
- [ ] Countdown shows 3 → 2 → 1 → GO!
- [ ] Q1 displays question text + 4 options + 15s timer + difficulty badge.
- [ ] Click an option → its border highlights, "Selected A. You can still change your answer..." appears.
- [ ] Click a different option → first highlight clears, new one highlights. (just-shipped)
- [ ] Wait for timer to hit 0 → personal feedback card shows ✓/✗ + your points.
- [ ] No public scoreboard during the round (only own score chip + player list).
- [ ] Difficulty bumps up after a correct answer; drops after a wrong streak.
- [ ] Bots answer at varied times (some quick, some near the end).
- [ ] All 10 questions complete → final leaderboard with medals + winner banner.
- [ ] **Play again** button returns to the mode picker.

### B. Helps (during a CPU game)
- [ ] **50/50** — click once → 2 wrong options gray out / strike through. Button disables (one-shot).
- [ ] **Call a Friend** — click → modal with 1-2 sentence advice. Close modal → game continues.
  - If `OPENAI_API_KEY` is set on Render: real witty hint.
  - If missing: canned fallback line ("Bob shrugs..."). Either is OK.
- [ ] **Double Score** — click before answering → "Double Score armed" hint. If you then answer correctly the points round shows `2×`.
- [ ] Each help is one-shot per game (button stays disabled after use).
- [ ] Activate Double *after* tentatively answering correctly → final reveal shows 2× anyway.

### C. Multiplayer (vs Friends)
- [ ] Mac browser → **vs Friends** → name → QR + lobby render. Code visible (e.g. "VO8SY").
- [ ] iPhone (same Wi-Fi or anywhere on internet — Render is public) → camera → scan QR.
- [ ] iPhone lands on `/join/<CODE>` → name form → Join.
- [ ] Mac lobby updates: now shows host + iPhone player.
- [ ] Mac → **Start Game** → both screens enter countdown together.
- [ ] Both screens show same question + same difficulty.
- [ ] Each player only sees own ✓/✗ between rounds.
- [ ] Final leaderboard ranks both players + (if any) bots correctly.

### D. Chat
- [ ] Type a message → enter → both screens see it with sender name.
- [ ] Tap an emoji from the quick bar → both screens see it.
- [ ] Long messages truncate at 200 chars.

### E. Resilience
- [ ] On the iPhone, lock screen for 5s during a question → unlock → game still in sync (rejoin works).
- [ ] Force-close iPhone Safari mid-game → reopen URL → does NOT auto-rejoin (intentional — fresh load = fresh game).
- [ ] Two simultaneous CPU games on Mac + iPhone (different rooms) → no crosstalk.

### F. Cold-start (free tier)
- [ ] Wait 16+ minutes after last play → click Start → Connecting… visible for ~30s → game eventually loads.
  - Note: this is expected free-tier behavior. ISSUE-003 in the QA report.

### G. Submission readiness
- [ ] Record a screen capture of a full vs Friends game (host + phone visible) ~3 min.
- [ ] Make sure call-a-friend modal is shown in the recording (cool factor).
- [ ] Demo the change-answer feature on camera (click A, then change to C).

If anything fails: paste the screenshot + steps and we'll triage.

---

## Backlog (next things to ship)

Ordered roughly by value/cost.

### Quick wins
- [ ] **Cold-start hint** (ISSUE-003) — frontend detects connect taking >5s and shows "Backend is waking up — this can take up to 30 seconds on free hosting." Soften the worst free-tier UX moment.
- [ ] **Cron pinger** — free job (cron-job.org) hits `/health` every 14 min to keep backend warm. Eliminates ISSUE-003 entirely.
- [ ] **Restart-room button** on leaderboard — instead of navigating back to `/`, kick a fresh round with the same players.
- [ ] **Confetti on win** — `canvas-confetti` ~5 KB. Pure UI delight.
- [ ] **Title contrast** (ISSUE-002) — bump title legibility on home (drop-shadow or solid color + accent underline).

### Polish
- [ ] **Sound on/off** toggle — current WebAudio cue is on by default; some demos want silence.
- [ ] **Keyboard shortcuts** — `1/2/3/4` to answer, `H` for help menu. Power-user touch.
- [ ] **Avatar / color per player** — random emoji or initials chip so the lobby/leaderboard feels more alive.
- [ ] **Per-question score breakdown** — show last round's points awarded as a flying "+750" near the score chip.
- [ ] **Animated correct-answer reveal** — flash green on correct option after the round (private).

### Real features
- [ ] **Hall of Fame** `/api/games` endpoint + a `/hall-of-fame` page reading the `games` + `game_players` tables. Rank by lifetime score across all games.
- [ ] **Persistent game history on Render** — `trivia.db` is currently ephemeral on free tier. Either attach a Render Persistent Disk ($1/mo) or migrate `games` + `game_players` to Neon Postgres (free).
- [ ] **Reconnect grace period config** — currently rooms tear down 60s after game end. Make it configurable; expose a "Game ended — leaderboard available for X minutes" hint.
- [ ] **Per-player help loadouts** — let host choose which 3 helps the room uses (e.g. swap 50/50 for a 5-second time freeze).
- [ ] **Question categories** — tag questions in DB (history/science/sports/etc.) and let host filter.

### Hardening
- [ ] **Tighten CORS allowlist** — currently `FRONTEND_URL` is set on Render. Verify dev fallback (`*`) only triggers when the env var is unset.
- [ ] **Rate-limit `chat` events** — currently 1/event from frontend; server should also throttle (e.g. 5/sec/sid) to prevent spam.
- [ ] **Validate `name` server-side for profanity** — optional, only matters if hosted publicly.
- [ ] **Disconnect-mid-game UX** — if a friend's phone drops permanently, host's lobby should show them as "(disconnected)" rather than just frozen at last-known score.
- [ ] **Replace deprecated `websockets.legacy`** warning surfaced by tests. Pin a non-deprecated path.

### Demo / submission
- [ ] **Record video** of full vs Friends game including all 3 helps + chat + change-answer feature.
- [ ] **Upload zip to Moodle** as `assignment3-exercise2.zip` (exclude `.venv`, `node_modules`, `.next`, `.gstack`).
- [ ] **Fill the submission Google Form** with the video links.

---

## Open / nice-to-haves (legacy — see Backlog above for prioritised list)

- Hall-of-Fame `/api/games` endpoint reading from `games` table.
- Confetti on win.
- Restart-room button on the leaderboard screen.
