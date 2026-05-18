# Tunnel mode (ngrok backend + cloudflared frontend)

Run the game from your laptop, expose it to the internet via two free tunnels. Friends join from any network. No deploy.

> **Why two tunneling services?** ngrok free tier allocates only **one** simultaneous public URL per agent. We use it for the backend (paired with the reserved free static domain so `NEXT_PUBLIC_API_URL` stays stable across restarts and Next.js doesn't need rebuilding). For the frontend we use a **Cloudflare quick tunnel** — free, no signup, no auth, supports WebSocket, and you can run as many concurrent tunnels as you want per machine. Frontend URL is random per restart but invisible to phones because the QR uses `window.location.origin`.

> **Trade vs. cloud deploy**: laptop must be awake and `./run.sh --tunnel` running for the URLs to work. Goes down the moment you close the laptop. Pay-off: zero cold start, instant changes, no monthly hosting cost.

---

## 1. ngrok signup (one-time)

1. https://dashboard.ngrok.com — free signup (GitHub OAuth works).
2. Copy your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
3. Reserve one **free static domain** for the backend: https://dashboard.ngrok.com/domains → **+ New Domain** → copy the assigned hostname (looks like `xxxx.ngrok-free.dev`).

## 2. Local install

```bash
brew install ngrok          # macOS — or download https://ngrok.com/download
brew install cloudflared    # macOS — or https://github.com/cloudflare/cloudflared
```

Cloudflare quick tunnels need **no account, no auth** — just the binary.

## 3. Configure

Add to `backend/.env`:

```env
NGROK_AUTHTOKEN=2abc...your-token...
NGROK_BACKEND_DOMAIN=fifth-morphine-shock.ngrok-free.dev   # the domain you reserved
```

(Template lives in `backend/.env.example` and `ngrok.yml.example`.)

## 4. Launch

```bash
./run.sh --tunnel
```

The script:
1. Renders `.ngrok.yml` from the template, substituting your auth + domain.
2. Starts `ngrok start` (backend tunnel only) in the background.
3. Polls the ngrok local API (`127.0.0.1:4040`) for the backend URL.
4. Starts `cloudflared tunnel --url http://localhost:3000` in the background.
5. Tails `.cloudflared.log` for the allocated `*.trycloudflare.com` URL.
6. Writes `frontend/.env.local` with both `NEXT_PUBLIC_API_URL` (ngrok) and `NEXT_PUBLIC_TUNNEL_URL` (cloudflared).
7. Exports `FRONTEND_URL` so backend CORS allows the frontend tunnel origin.
8. Boots backend + frontend in dev mode.
9. Prints the live URLs and auto-opens the frontend in your browser.

You'll see something like:

```
══════════════════════════════════════════════════════════════════
 PLAY HERE (laptop):  https://random-words-1234.trycloudflare.com
   ↳ vs Computer:     https://random-words-1234.trycloudflare.com/cpu
   ↳ vs Friends:      https://random-words-1234.trycloudflare.com/host
 Friends scan the QR shown on /host (cellular data works).
 backend API:          https://fifth-morphine-shock.ngrok-free.dev
 ngrok inspector:      http://127.0.0.1:4040
══════════════════════════════════════════════════════════════════
```

## 5. Verify

- Browser auto-opens to the trycloudflare URL → vs Friends → name → QR appears.
- Scan the QR on your phone (cellular network, not Wi-Fi, to prove the tunnel works) → join.
- Host clicks **Start** → both screens enter the countdown together.

Ctrl-C in the terminal kills backend, frontend, ngrok, and cloudflared cleanly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ngrok not installed` / `cloudflared not installed` | binary missing | `brew install ngrok cloudflared` |
| `NGROK_AUTHTOKEN unset` on launch | not in `backend/.env` | add it (see step 3) |
| `ERR_NGROK_4018` / auth error | bad authtoken | re-copy from dashboard, no whitespace |
| `ERR_NGROK_3200` / domain in use | another ngrok agent already holds your reserved domain | `pkill ngrok` and retry |
| `cloudflared did not allocate a URL in 30s` | network/firewall blocking outbound to Cloudflare, or cloudflared crashed | `tail .cloudflared.log` for details; try `cloudflared tunnel --url http://localhost:3000` standalone to confirm |
| backend tunnel is up but `502` from ngrok | upstream not yet listening | wait ~3s; uvicorn boot takes a moment |
| Phone scan opens **backend** ngrok URL and shows `{"detail":"Not Found"}` | host opened the wrong URL on laptop, so QR encoded the backend URL | Open the **trycloudflare** URL printed in the green banner. The `/host` page also shows a yellow warning banner if you opened localhost. |
| QR encodes `localhost:3000/join/...` | host opened `http://localhost:3000/host` | Banner on `/host` shows the correct tunnel URL — click it. |
| CORS error in browser console | `FRONTEND_URL` not exported to backend | confirm `./run.sh --tunnel` printed the trycloudflare URL; restart |
| Frontend connects to wrong backend | stale `frontend/.env.local` | the script overwrites this file each run; if you ran `--prod` afterward, run `--tunnel` again |
| Phone scan opens the trycloudflare URL but spins forever / errors. `curl $BACKEND_URL/health` returns `502 ERR_NGROK_8012`. | Backend died but tunnels still alive (orphans from a prior session whose terminal closed without Ctrl-C) | `pkill -f "ngrok start"; pkill -f cloudflared`, then `./run.sh --tunnel`. The script now kills orphans automatically at startup. |
| Connection hangs the first time a phone joins, or socket.io polling 502s | ngrok free-tier interstitial intercepting Socket.IO handshake | Frontend already sends `ngrok-skip-browser-warning`. If still broken, visit `$BACKEND_URL/health` once in the phone browser to accept the interstitial cookie. |

## Files involved

- `ngrok.yml.example` — committed template (env-var placeholders).
- `.ngrok.yml` — generated each run, gitignored.
- `.ngrok.log` — ngrok's JSON log, gitignored. Tail with `jq` if debugging: `tail -f .ngrok.log | jq .`.
- `.cloudflared.log` — cloudflared's log, gitignored. Contains the trycloudflare URL.
- `backend/.env` — your ngrok authtoken + reserved domain live here.
- `frontend/.env.local` — overwritten each `--tunnel` run with both tunnel URLs.
