# Deploy to Render

Two services, free tier, ~10 minutes start-to-finish.

> **Free tier caveat**: backend sleeps after 15 min idle. First request after sleep
> takes ~30 s while it wakes. Game history in `trivia.db` resets on each redeploy
> (disk is ephemeral). Both fine for a demo. If you want zero-downtime + persistent
> history, upgrade backend to a paid plan and add a Persistent Disk.

---

## 1. Push to GitHub

```bash
git status                       # confirm clean working tree
git push                         # render reads from GitHub
```

Make sure the repo is **public** (or Render has access via GitHub auth) — otherwise Render can't pull.

## 2. Create Render account

- Go to https://render.com → Sign up with GitHub.
- Authorise Render to read your repos.

## 3. Apply the Blueprint

1. Render Dashboard → **New** → **Blueprint**.
2. Pick this repo. Render will detect [render.yaml](render.yaml) and propose two services: `trivia-backend` and `trivia-frontend`.
3. Click **Apply**. It starts building both. Backend will succeed; frontend will succeed too — but they can't yet talk to each other (env vars not set).

## 4. Set the secrets / cross-service URLs

After both services exist, copy URLs from the dashboard. They look like:

- backend  → `https://trivia-backend.onrender.com`
- frontend → `https://trivia-frontend.onrender.com`

### Backend env vars (Dashboard → trivia-backend → Environment)
| Key | Value |
|---|---|
| `OPENAI_API_KEY` | your key from `backend/.env` |
| `FRONTEND_URL` | `https://trivia-frontend.onrender.com` |

Click **Save Changes** → Render redeploys.

### Frontend env vars (Dashboard → trivia-frontend → Environment)
| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://trivia-backend.onrender.com` |

Click **Save Changes** → Render rebuilds (NEXT_PUBLIC_* must be present at build time, so a redeploy is required).

## 5. Verify

- Open `https://trivia-backend.onrender.com/health` → `{"ok":true,"questions":266}`.
- Open `https://trivia-frontend.onrender.com/` → mode picker loads.
- Click vs Computer → enter a name → game runs.
- vs Friends → QR encodes `https://trivia-frontend.onrender.com/join/<code>` → friends scan from anywhere → join.

## 6. Update flow

Every push to the repo's default branch redeploys both services automatically (`autoDeploy: true` in [render.yaml](render.yaml)). To redeploy manually: Dashboard → service → **Manual Deploy** → **Deploy latest commit**.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `CORS error` in browser console | `FRONTEND_URL` missing on backend | Set it in backend env, save |
| `WebSocket error` / Socket.IO disconnect loop | `NEXT_PUBLIC_API_URL` wrong on frontend | Must be the **backend** URL, no trailing slash |
| Backend boots but questions=0 | `trivia.db` missing from git | `git add trivia.db && git commit && git push` |
| Backend 503 / cold start | Free tier sleep | First request after idle takes ~30 s. Hit `/health` to warm it. |
| Frontend build fails on env var read | `NEXT_PUBLIC_*` only inlined at build time | After setting the var, click **Manual Deploy** to rebuild |
| Call-a-Friend shows fallback line | `OPENAI_API_KEY` missing on backend | Set it; redeploy |

## Local-only files (not used by Render)

- `run.sh` — local one-command launcher
- `frontend/.env.local` — local-only API URL override
- `backend/.env` — local-only secrets

These are git-ignored and ignored by Render. Production reads env vars directly from Render's dashboard.
