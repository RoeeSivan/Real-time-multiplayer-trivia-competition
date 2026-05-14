# Tunnel mode (ngrok)

Run the game from your laptop, expose it to the internet via two ngrok tunnels. Friends join from any network. No deploy.

> **Trade vs. cloud deploy**: laptop must be awake and `./run.sh --tunnel` running for the URLs to work. Goes down the moment you close the laptop. Pay-off: zero cold start, instant changes, no monthly hosting cost.

---

## 1. ngrok signup

1. https://dashboard.ngrok.com — free signup (GitHub OAuth works).
2. Copy your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
3. Reserve one **free static domain** (free tier allows 1): https://dashboard.ngrok.com/domains → **+ New Domain** → copy the assigned `*.ngrok-free.app` hostname.

Why a static domain for the backend: Next.js inlines `NEXT_PUBLIC_API_URL` at compile time. A stable backend URL means we never have to rebuild the frontend on restart. The frontend itself gets a fresh random URL each run — that's fine because the QR uses `window.location.origin`, so phones always reach whatever URL the host is on.

## 2. Local install

```bash
brew install ngrok      # macOS — or download https://ngrok.com/download
```

## 3. Configure

Add to `backend/.env`:

```env
NGROK_AUTHTOKEN=2abc...your-token...
NGROK_BACKEND_DOMAIN=trivia-be.ngrok-free.app   # the domain you reserved
```

(Template lives in `backend/.env.example` and `ngrok.yml.example`.)

## 4. Launch

```bash
./run.sh --tunnel
```

The script:
1. Renders `.ngrok.yml` from the template, substituting your auth + domain.
2. Starts `ngrok start --all` in the background.
3. Polls the ngrok local API (`127.0.0.1:4040`) for the allocated public URLs.
4. Writes `frontend/.env.local` with the backend ngrok URL.
5. Exports `FRONTEND_URL` so backend CORS allows the frontend ngrok origin.
6. Boots backend + frontend in dev mode.
7. Prints the live URLs.

You'll see something like:

```
[run] Tunnels live:
  host (open this on your laptop): https://1a2b-3c4d.ngrok-free.app/host
  solo:                            https://1a2b-3c4d.ngrok-free.app/cpu
  backend API:                     https://trivia-be.ngrok-free.app
  ngrok inspector:                 http://127.0.0.1:4040
```

## 5. Verify

- Open the `host` URL on your laptop → vs Friends → name → QR appears.
- Scan the QR on your phone (cellular network, not Wi-Fi, to prove the tunnel works) → join.
- Host clicks **Start** → both screens enter the countdown together.

Ctrl-C in the terminal kills backend, frontend, and ngrok cleanly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `NGROK_AUTHTOKEN unset` on launch | not in `backend/.env` | add it (see step 3) |
| `ERR_NGROK_4018` / auth error | bad authtoken | re-copy from dashboard, no whitespace |
| `ERR_NGROK_3200` / domain in use | another ngrok agent already holds your reserved domain | kill old `ngrok` processes: `pkill ngrok` |
| backend tunnel is up but `502` | upstream not yet listening | wait ~3s; uvicorn boot takes a moment |
| Phone gets "ERR_NGROK_6024" interstitial | first-visit warning page on free tier | tap through once; subsequent loads skip it (the Socket.IO handshake also bypasses it) |
| **First scan shows "You are about to visit..." page** | ngrok-free interstitial — fires on the first HTML visit to any `*.ngrok-free.app/.dev` URL | Tap **Visit Site** once per device. Socket.IO traffic bypasses the interstitial automatically (only triggers on `Accept: text/html`). Only paid plan removes it. |
| QR encodes `localhost:3000/join/...` | host opened laptop URL `http://localhost:3000/host` instead of the tunnel URL | The `/host` page now shows a yellow warning banner with the correct URL — click it. (The script also auto-opens the tunnel URL on launch to prevent this.) |
| CORS error in browser console | `FRONTEND_URL` not exported to backend | confirm `./run.sh --tunnel` printed both URLs; restart |
| Frontend connects to wrong backend | stale `frontend/.env.local` | the script overwrites this file each run; if you ran `--prod` afterward, run `--tunnel` again |
| `ngrok` not found | not installed | `brew install ngrok` |

## Files involved

- `ngrok.yml.example` — committed template (env-var placeholders).
- `.ngrok.yml` — generated each run, gitignored.
- `.ngrok.log` — ngrok's JSON log, gitignored. Tail with `jq` if debugging: `tail -f .ngrok.log | jq .`.
- `backend/.env` — your authtoken + reserved domain live here.
- `frontend/.env.local` — overwritten each `--tunnel` run with the backend URL.
