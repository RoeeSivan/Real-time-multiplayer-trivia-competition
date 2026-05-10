#!/usr/bin/env bash
# One-command launcher for the trivia stack.
#
#   ./run.sh           # dev mode (FastAPI reload + Next.js dev)
#   ./run.sh --prod    # production-ish (uvicorn no-reload + next start, requires prior build)
#
# First run auto-installs Python venv, pip deps, npm deps, and seeds frontend/.env.local.
# Ctrl-C cleanly shuts down both servers.

set -euo pipefail

cd "$(dirname "$0")"

MODE="dev"
if [[ "${1:-}" == "--prod" ]]; then MODE="prod"; fi

C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_BLUE=$'\033[34m'; C_PURPLE=$'\033[35m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'

log()  { printf "%s[run]%s %s\n" "$C_BLUE" "$C_RESET" "$*"; }
warn() { printf "%s[run]%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }

# --- Backend setup ---
if [[ ! -d .venv ]]; then
  log "creating Python venv (.venv)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Cheap freshness check: install when fastapi missing OR requirements newer than venv stamp.
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

# --- Boot ---
PIDS=()
cleanup() {
  log "shutting down…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

log "starting backend  → ${C_PURPLE}http://localhost:8000${C_RESET}  ${C_DIM}(uvicorn)${C_RESET}"
if [[ $MODE == "dev" ]]; then
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
else
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
fi
PIDS+=($!)

log "starting frontend → ${C_PURPLE}http://localhost:3000${C_RESET}  ${C_DIM}(next)${C_RESET}"
if [[ $MODE == "dev" ]]; then
  (cd frontend && npm run dev) &
else
  (cd frontend && npm run build && npm run start) &
fi
PIDS+=($!)

log "${C_GREEN}both servers up. Ctrl-C to stop.${C_RESET}"
wait
