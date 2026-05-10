"""Socket.IO event handlers — transport layer only.

Phase 1: minimal connect/disconnect logging so the server boots cleanly.
Phase 4 will fill in create_room / join_room / start_game / submit_answer /
use_help / chat. All real game logic lives under `backend.game`.
"""
from __future__ import annotations

import logging

import socketio

log = logging.getLogger("trivia.sock")


def register(sio: socketio.AsyncServer) -> None:
    """Attach all event handlers to the given server instance."""

    @sio.event
    async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
        log.info("connect sid=%s", sid)

    @sio.event
    async def disconnect(sid: str) -> None:
        log.info("disconnect sid=%s", sid)
