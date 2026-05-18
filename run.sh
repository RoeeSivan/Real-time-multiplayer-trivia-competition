#!/usr/bin/env bash
# One-command launcher for the trivia stack.
#
#   ./run.sh           # dev mode  — uvicorn --reload + next dev (LAN-only)
#   ./run.sh --prod    # prod-ish  — uvicorn + next build && next start (LAN-only)
#   ./run.sh --tunnel  # ngrok     — dev servers + 2 ngrok tunnels (any network)
#
# First run auto-installs Python venv, pip deps, npm deps, and seeds env files.
# Ctrl-C cleanly shuts down everything.

set -euo pipefail

cd "$(dirname "$0")"

MODE="dev"
case "${1:-}" in
  --prod)   MODE="prod" ;;
  --tunnel) MODE="tunnel" ;;
  "")       MODE="dev" ;;
  *)        echo "Usage: $0 [--prod|--tunnel]" >&2; exit 1 ;;
esac

C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_BLUE=$'\033[34m'; C_PURPLE=$'\033[35m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'

log()  { printf "%s[run]%s %s\n" "$C_BLUE" "$C_RESET" "$*"; }
warn() { printf "%s[run]%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf "%s[run]%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; }

# --- Backend setup ---
if [[ ! -d .venv ]]; then
  log "creating Python venv (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

NEED_PIP=0
if ! python -c "import fastapi" 2>/dev/null; then NEED_PIP=1; fi
if [[ -f backend/requirements.txt && ( ! -f .venv/.req-stamp || backend/requirements.txt -nt .venv/.req-stamp ) ]]; then
  NEED_PIP=1
fi
if [[ $NEED_PIP -eq 1 ]]; then
  log "installing Python deps…"
  pip install --quiet --upgrade pip
  pip install --quiet -r backend/requirements.txt
  touch .venv/.req-stamp
fi

if [[ ! -f backend/.env && -f backend/.env.example ]]; then
  warn "backend/.env missing — copying from .env.example (set OPENAI_API_KEY for call-a-friend)"
  cp backend/.env.example backend/.env
fi

# --- Frontend setup ---
if [[ ! -d frontend/node_modules ]]; then
  log "installing npm deps (first run, may take ~1 min)…"
  (cd frontend && npm install --no-fund --no-audit --silent)
fi
if [[ ! -f frontend/.env.local ]]; then
  log "seeding frontend/.env.local"
  cp frontend/.env.local.example frontend/.env.local
fi

# --- Tunnel mode: ngrok (backend) + cloudflared (frontend) ---
# ngrok free = 1 simultaneous public URL per agent, so it gets the backend
# (paired with the reserved static domain so NEXT_PUBLIC_API_URL stays stable).
# Cloudflare quick tunnels are free, no signup, support multiple per machine
# and WebSocket — perfect for the frontend.
NGROK_PID=""
CFD_PID=""
if [[ $MODE == "tunnel" ]]; then
  for bin in ngrok cloudflared; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      err "$bin not installed. Install: brew install $bin"
      exit 1
    fi
  done
  if [[ ! -f ngrok.yml.example ]]; then
    err "ngrok.yml.example missing — repo broken."
    exit 1
  fi

  # Kill any orphan tunnels (and stale dev servers) still holding our resources.
  # Common cause: a previous session's terminal was closed without Ctrl-C, so
  # the trap never fired and ngrok/cloudflared kept their reserved-domain
  # claim. Without this the new ngrok session can't claim the static domain
  # and curl-through-tunnel returns 502 (ERR_NGROK_8012) forever.
  log "checking for orphan tunnels + listeners…"
  for pat in "ngrok start --all --config .ngrok.yml" \
             "cloudflared tunnel --url http://localhost:3000" \
             "uvicorn backend.main:app" \
             "next dev" "next start"; do
    pids=$(pgrep -f "$pat" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      warn "killing orphan: $pat ($pids)"
      kill $pids 2>/dev/null || true
    fi
  done
  sleep 1

  # Load NGROK_* + FRONTEND_URL placeholder from backend/.env without exporting OPENAI_API_KEY noise.
  set -a
  # shellcheck disable=SC1091
  source backend/.env
  set +a

  : "${NGROK_AUTHTOKEN:?NGROK_AUTHTOKEN unset — add to backend/.env (see ngrok.yml.example)}"
  : "${NGROK_BACKEND_DOMAIN:?NGROK_BACKEND_DOMAIN unset — add to backend/.env (reserve a free static domain at https://dashboard.ngrok.com/domains)}"

  log "rendering .ngrok.yml from template…"
  envsubst '${NGROK_AUTHTOKEN} ${NGROK_BACKEND_DOMAIN}' < ngrok.yml.example > .ngrok.yml

  log "starting ngrok backend → ${C_PURPLE}https://${NGROK_BACKEND_DOMAIN}${C_RESET}…"
  ngrok start --all --config .ngrok.yml --log .ngrok.log --log-format json >/dev/null 2>&1 &
  NGROK_PID=$!

  log "waiting for ngrok backend tunnel…"
  BACKEND_URL=""
  for _ in $(seq 1 30); do
    if TUNNEL_JSON=$(curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null); then
      BACKEND_URL=$(printf '%s' "$TUNNEL_JSON" | python3 -c "import json,sys
for t in json.load(sys.stdin).get('tunnels',[]):
    if t.get('name')=='backend':
        print(t['public_url']); break")
      [[ -n "$BACKEND_URL" ]] && break
    fi
    sleep 0.5
  done

  if [[ -z "$BACKEND_URL" ]]; then
    err "ngrok did not allocate the backend tunnel. Check .ngrok.log."
    kill "$NGROK_PID" 2>/dev/null || true
    exit 1
  fi

  log "starting cloudflared frontend → ${C_PURPLE}trycloudflare.com${C_RESET}…"
  : > .cloudflared.log
  cloudflared tunnel --url http://localhost:3000 --no-autoupdate >.cloudflared.log 2>&1 &
  CFD_PID=$!

  log "waiting for cloudflared to allocate URL (can take 5–15s)…"
  FRONTEND_URL_TUN=""
  for _ in $(seq 1 60); do
    # `|| true` swallows grep's exit-1 on no-match so set -e + pipefail don't abort.
    FRONTEND_URL_TUN=$( { grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .cloudflared.log || true; } | head -1)
    [[ -n "$FRONTEND_URL_TUN" ]] && break
    sleep 0.5
  done

  if [[ -z "$FRONTEND_URL_TUN" ]]; then
    err "cloudflared did not allocate a URL in 30s. Tail of .cloudflared.log:"
    tail -20 .cloudflared.log >&2
    kill "$NGROK_PID" "$CFD_PID" 2>/dev/null || true
    exit 1
  fi

  log "writing frontend/.env.local  ← NEXT_PUBLIC_API_URL=$BACKEND_URL"
  cat > frontend/.env.local <<EOF
# Auto-generated by ./run.sh --tunnel — overwritten on each run.
NEXT_PUBLIC_API_URL=$BACKEND_URL
NEXT_PUBLIC_TUNNEL_URL=$FRONTEND_URL_TUN
EOF

  # Backend reads FRONTEND_URL via load_dotenv (override=False). Exporting wins.
  # Include localhost so opening http://localhost:3000 still connects.
  export FRONTEND_URL="$FRONTEND_URL_TUN,http://localhost:3000,http://127.0.0.1:3000"
fi

# --- Boot ---
PIDS=()
cleanup() {
  log "shutting down…"
  for pid in "$NGROK_PID" "$CFD_PID" "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

log "starting backend  → ${C_PURPLE}http://localhost:8000${C_RESET}  ${C_DIM}(uvicorn)${C_RESET}"
if [[ $MODE == "prod" ]]; then
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
else
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
fi
PIDS+=($!)

log "starting frontend → ${C_PURPLE}http://localhost:3000${C_RESET}  ${C_DIM}(next)${C_RESET}"
if [[ $MODE == "prod" ]]; then
  (cd frontend && npm run build && npm run start) &
else
  (cd frontend && npm run dev) &
fi
PIDS+=($!)

if [[ $MODE == "tunnel" ]]; then
  BAR="══════════════════════════════════════════════════════════════════"
  printf "\n%s%s%s\n" "$C_GREEN" "$BAR" "$C_RESET"
  printf " %sPLAY HERE (laptop):%s  %s%s%s\n" "$C_GREEN" "$C_RESET" "$C_PURPLE" "$FRONTEND_URL_TUN" "$C_RESET"
  printf "   %s↳ vs Computer:%s     %s%s/cpu%s\n" "$C_DIM" "$C_RESET" "$C_PURPLE" "$FRONTEND_URL_TUN" "$C_RESET"
  printf "   %s↳ vs Friends:%s      %s%s/host%s\n" "$C_DIM" "$C_RESET" "$C_PURPLE" "$FRONTEND_URL_TUN" "$C_RESET"
  printf " %sFriends scan the QR shown on /host (cellular data works).%s\n" "$C_DIM" "$C_RESET"
  printf " %sbackend API:%s          %s%s%s\n" "$C_DIM" "$C_RESET" "$C_PURPLE" "$BACKEND_URL" "$C_RESET"
  printf " %sngrok inspector:%s      %shttp://127.0.0.1:4040%s\n" "$C_DIM" "$C_RESET" "$C_PURPLE" "$C_RESET"
  printf "%s%s%s\n\n" "$C_GREEN" "$BAR" "$C_RESET"

  # Auto-open frontend tunnel URL so the host never accidentally lands on
  # localhost (which would make the QR encode an unreachable address).
  # Wait a few seconds for next dev to start compiling so the first request
  # doesn't race a 503.
  (
    sleep 4
    if command -v open >/dev/null 2>&1; then
      open "$FRONTEND_URL_TUN/" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$FRONTEND_URL_TUN/" >/dev/null 2>&1 || true
    fi
  ) &

  # Post-boot health probe via the public tunnel. Catches the "tunnel alive,
  # local service dead" 502 (ERR_NGROK_8012) that bit us before.
  (
    sleep 6
    for _ in 1 2 3; do
      if curl -fsS --max-time 5 \
           -H "ngrok-skip-browser-warning: 1" \
           "$BACKEND_URL/health" >/dev/null 2>&1; then
        printf "%s[run] ✓ backend reachable via tunnel%s\n" "$C_GREEN" "$C_RESET"
        exit 0
      fi
      sleep 3
    done
    printf "%s[run] ✗ backend NOT reachable via tunnel (%s/health). Tunnels alive but service down? Check the uvicorn log above.%s\n" \
      "$C_RED" "$BACKEND_URL" "$C_RESET" >&2
  ) &
fi

log "${C_GREEN}both servers up. Ctrl-C to stop.${C_RESET}"
wait
