"""Socket.IO event handlers — transport layer.

All real game logic lives in `backend.game.*`; LLM calls in `backend.llm`.
This module just validates payloads and delegates to GameManager.
"""
from __future__ import annotations

import logging

import socketio
from pydantic import ValidationError

from backend import llm, models
from backend.game.room import RoomError
from backend.manager import GameManager

log = logging.getLogger("trivia.sock")

_manager: GameManager | None = None


def get_manager() -> GameManager:
    if _manager is None:
        raise RuntimeError("Manager not initialised — call register() first")
    return _manager


async def _emit_error(sio: socketio.AsyncServer, sid: str, message: str) -> None:
    await sio.emit("error", {"message": message}, to=sid)


def _ack(error: str | None = None, **data: object) -> dict:
    return {"ok": error is None, "error": error, **data}


def register(sio: socketio.AsyncServer) -> None:
    global _manager
    _manager = GameManager(sio)
    mgr = _manager

    @sio.event
    async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
        log.info("connect sid=%s", sid)

    @sio.event
    async def disconnect(sid: str) -> None:
        log.info("disconnect sid=%s", sid)
        try:
            await mgr.handle_disconnect(sid)
        except Exception:
            log.exception("disconnect cleanup failed")

    @sio.event
    async def create_room(sid: str, data: dict | None) -> dict:
        try:
            payload = models.CreateRoomIn.model_validate(data or {})
            return _ack(None, **await mgr.create_room(
                sid=sid, mode=payload.mode, name=payload.name
            ))
        except ValidationError as e:
            return _ack(str(e))
        except RoomError as e:
            return _ack(str(e))
        except Exception as e:  # pragma: no cover
            log.exception("create_room")
            return _ack(f"server error: {e}")

    @sio.event
    async def join_room(sid: str, data: dict | None) -> dict:
        try:
            payload = models.JoinRoomIn.model_validate(data or {})
            return _ack(None, **await mgr.join_room(
                sid=sid, room_code=payload.room_code.upper(), name=payload.name
            ))
        except ValidationError as e:
            return _ack(str(e))
        except RoomError as e:
            return _ack(str(e))
        except Exception as e:  # pragma: no cover
            log.exception("join_room")
            return _ack(f"server error: {e}")

    @sio.event
    async def start_game(sid: str, _data: dict | None = None) -> dict:
        try:
            await mgr.start_game_by_host(sid)
            return _ack(None)
        except RoomError as e:
            return _ack(str(e))

    @sio.event
    async def submit_answer(sid: str, data: dict | None) -> dict:
        try:
            payload = models.SubmitAnswerIn.model_validate(data or {})
            await mgr.submit_answer(sid, option_idx=payload.option_idx)
            return _ack(None)
        except ValidationError as e:
            return _ack(str(e))
        except RoomError as e:
            return _ack(str(e))

    @sio.event
    async def use_help(sid: str, data: dict | None) -> dict:
        try:
            payload = models.UseHelpIn.model_validate(data or {})
            room, player_id = mgr.get_room_for_sid(sid)
            if payload.type == "fifty":
                removed = room.use_fifty(player_id)
                return _ack(None, type="fifty", removed_indices=removed)
            if payload.type == "double":
                room.use_double(player_id)
                return _ack(None, type="double")
            # friend — call LLM, mark used only if call succeeds (it always returns a string)
            if room.current_question is None:
                return _ack("Call-a-friend only during a question")
            advice = await llm.call_a_friend(
                question=room.current_question.text,
                options=room.current_question.options,
            )
            room.mark_friend_used(player_id)
            return _ack(None, type="friend", advice=advice)
        except ValidationError as e:
            return _ack(str(e))
        except RoomError as e:
            return _ack(str(e))
        except Exception as e:  # pragma: no cover
            log.exception("use_help")
            return _ack(f"server error: {e}")

    @sio.event
    async def chat(sid: str, data: dict | None) -> dict:
        try:
            payload = models.ChatIn.model_validate(data or {})
            await mgr.chat(sid, payload.text)
            return _ack(None)
        except ValidationError as e:
            return _ack(str(e))
        except RoomError as e:
            return _ack(str(e))
