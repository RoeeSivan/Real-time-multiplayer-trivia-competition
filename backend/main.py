"""FastAPI + Socket.IO entrypoint.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

The Socket.IO server is mounted under the same ASGI app, so the websocket
endpoint is available at the same host:port (default path /socket.io).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import socketio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import db

load_dotenv(dotenv_path=".env")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("trivia.main")


# --- FastAPI ---

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_schema()
    log.info("Schema initialised. Question bank: %d rows.", db.count_questions())
    yield


fastapi_app = FastAPI(title="Trivia Multiplayer API", version="0.1.0", lifespan=lifespan)

# CORS / Socket.IO origins.
# - In dev (no FRONTEND_URL set): allow everything for easy LAN testing.
# - In prod: comma-separated list of origins via FRONTEND_URL, e.g.
#       FRONTEND_URL=https://trivia.example.com,https://staging.example.com
def _allowed_origins() -> list[str] | str:
    raw = os.getenv("FRONTEND_URL", "").strip()
    if not raw:
        return "*"
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


_origins = _allowed_origins()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if isinstance(_origins, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "questions": db.count_questions()}


# --- Socket.IO ---
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=_origins)

# Register event handlers (imported for side effects).
from backend import socket_handlers  # noqa: E402, F401

socket_handlers.register(sio)

# Combined ASGI app — Socket.IO wraps FastAPI.
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="/socket.io")
