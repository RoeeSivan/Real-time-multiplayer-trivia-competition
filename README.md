# Real-time Multiplayer Trivia

Real-time multiplayer trivia for Assignment #3, Exercise 2. Two modes (vs Computer / vs Friends), 10 questions × 15s, server-authoritative timing, adaptive difficulty, three helps (50/50, Call-a-Friend via PydanticAI/OpenAI, Double-Score), live chat with emojis, final leaderboard.

## Play it

The game runs from your laptop and is exposed to the internet via two ngrok tunnels — no cloud deploy. Live URL only works while `./run.sh --tunnel` is running on the host machine.

```bash
./run.sh --tunnel    # see TUNNEL.md for one-time ngrok setup
```

The script prints the live URL on launch — looks like `https://1a2b-3c4d.ngrok-free.app/host`.

### Friends game

1. Run `./run.sh --tunnel` on your laptop. Open the printed `/host` URL.
2. Pick a name → QR code + room code appear.
3. Friends scan the QR (or open `/join/<CODE>`), pick a name, join.
4. Host clicks **Start** → 3-2-1 → 10 questions → leaderboard.

Solo? Open the printed `/cpu` URL — instant game with 3 bots.

## Stack

- **Backend**: FastAPI + `python-socketio` (ASGI), uvicorn
- **Frontend**: Next.js 14 + React + TypeScript strict + Tailwind + Framer Motion + qrcode.react + socket.io-client
- **DB**: SQLite — 266 questions in `trivia.db`, plus `games` + `game_players` history tables
- **LLM**: PydanticAI → OpenAI (`gpt-4o-mini`) for Call-a-Friend
- **Tunneling**: ngrok (backend, reserved free static domain) + cloudflared (frontend, quick tunnel)

## Run locally

```bash
./run.sh            # dev      — uvicorn --reload + next dev (LAN-only)
./run.sh --prod     # prod-ish — uvicorn + next build && next start (LAN-only)
./run.sh --tunnel   # ngrok    — public URLs via two ngrok tunnels (any network)
```

First run auto-creates `.venv`, installs deps, copies `.env` / `.env.local` from examples.

**LAN play (phone QR scan, same Wi-Fi):** leave `frontend/.env.local` empty — the frontend auto-derives the backend URL from the browser's hostname. Open `http://<host-LAN-IP>:3000/host` on the host.

**Tunnel play (any network):** see [TUNNEL.md](TUNNEL.md) for the one-time ngrok setup, then `./run.sh --tunnel`.

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
| Friends-anywhere tunnel | ✅ ngrok (backend, reserved domain) + cloudflared (frontend) |
| ≥ 2 extra features | ✅ QR-code multiplayer, Framer Motion, WebAudio, mobile-first, private reveal, one-command tunnel launch |

## Tunnel (ngrok + cloudflared)

Full setup in [TUNNEL.md](TUNNEL.md). Short version:

1. Sign up at ngrok.com (free), copy authtoken, reserve 1 free static domain.
2. Add `NGROK_AUTHTOKEN` + `NGROK_BACKEND_DOMAIN` to `backend/.env`.
3. `brew install ngrok cloudflared`.
4. `./run.sh --tunnel` — boots backend, frontend, ngrok (backend), cloudflared (frontend) in one command. Prints the live URL and auto-opens the browser.

ngrok carries the backend on its reserved (stable) domain because Next.js bakes `NEXT_PUBLIC_API_URL` at compile time. cloudflared carries the frontend on a random `*.trycloudflare.com` URL each run — that's fine because the QR uses `window.location.origin`. CORS is wired up automatically: `run.sh` reads both URLs and exports `FRONTEND_URL` before launching uvicorn.

Why two tunneling services? ngrok free tier allocates only one simultaneous public URL per agent. Cloudflare quick tunnels are free, no signup, support multiple per machine and WebSocket — perfect for the second URL.

**Trade vs. cloud deploy**: tunnels only work while your laptop is on and `./run.sh --tunnel` is running. No cold start, no hosting bill.
