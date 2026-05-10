"""GameManager — registry that owns rooms and their runners.

Single source of truth for which sid is in which room. Socket handlers
delegate to the manager so room/runner lifecycle stays in one place.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import socketio

from backend import config
from backend.game.room import Mode, Room, RoomError, generate_room_code
from backend.game.runner import GameRunner

log = logging.getLogger("trivia.mgr")


@dataclass
class SidLink:
    room_code: str
    player_id: str


class GameManager:
    def __init__(self, sio: socketio.AsyncServer) -> None:
        self.sio = sio
        self.rooms: dict[str, Room] = {}
        self.runners: dict[str, GameRunner] = {}
        self.sid_links: dict[str, SidLink] = {}

    # --- Room lifecycle --------------------------------------------------

    def _new_room_code(self) -> str:
        for _ in range(20):
            code = generate_room_code()
            if code not in self.rooms:
                return code
        raise RuntimeError("Could not allocate unique room code")

    async def create_room(self, *, sid: str, mode: Mode, name: str) -> dict:
        code = self._new_room_code()
        room = Room(code=code, mode=mode)
        host = room.add_player(name=name, sid=sid)
        self.rooms[code] = room
        self.sid_links[sid] = SidLink(room_code=code, player_id=host.id)
        await self.sio.enter_room(sid, code)
        log.info("created room %s mode=%s host=%s", code, mode, name)

        if mode == "cpu":
            room.fill_with_bots_if_needed()
            await self._start(code)

        return {
            "room_code": code,
            "player_id": host.id,
            "is_host": True,
            "players": [p.to_public() for p in room.players.values()],
        }

    async def join_room(self, *, sid: str, room_code: str, name: str) -> dict:
        room = self.rooms.get(room_code.upper())
        if room is None:
            raise RoomError("Room not found")
        if room.mode == "cpu":
            raise RoomError("CPU rooms are private")
        player = room.add_player(name=name, sid=sid)
        self.sid_links[sid] = SidLink(room_code=room.code, player_id=player.id)
        await self.sio.enter_room(sid, room.code)
        await self.sio.emit(
            "lobby_update",
            {
                "players": [p.to_public() for p in room.players.values()],
                "host_id": room.host_id,
            },
            room=room.code,
        )
        return {
            "room_code": room.code,
            "player_id": player.id,
            "is_host": room.host_id == player.id,
            "players": [p.to_public() for p in room.players.values()],
        }

    async def start_game_by_host(self, sid: str) -> None:
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        if room.host_id != link.player_id:
            raise RoomError("Only host can start")
        await self._start(room.code)

    async def _start(self, code: str) -> None:
        room = self._require_room(code)
        room.start_game()
        runner = GameRunner(self.sio, room)
        self.runners[code] = runner
        runner.start()

    # --- Player actions --------------------------------------------------

    async def submit_answer(self, sid: str, *, option_idx: int) -> None:
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        runner = self.runners.get(room.code)
        if runner is None:
            raise RoomError("Game not started")
        room.submit_answer(player_id=link.player_id, option_idx=option_idx)
        await self.sio.emit(
            "answer_received", {"player_id": link.player_id}, room=room.code
        )
        runner.notify_answer_received()

    def get_room_for_sid(self, sid: str) -> tuple[Room, str]:
        link = self._require_link(sid)
        return self._require_room(link.room_code), link.player_id

    async def chat(self, sid: str, text: str) -> None:
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        player = room.players.get(link.player_id)
        if player is None:
            return
        await self.sio.emit(
            "chat_msg",
            {"player_id": player.id, "name": player.name, "text": text},
            room=room.code,
        )

    # --- Disconnect ------------------------------------------------------

    async def handle_disconnect(self, sid: str) -> None:
        link = self.sid_links.pop(sid, None)
        if link is None:
            return
        room = self.rooms.get(link.room_code)
        if room is None:
            return
        room.remove_player(link.player_id)
        if not any(not p.is_bot for p in room.players.values()):
            # No humans left → tear down.
            runner = self.runners.pop(room.code, None)
            if runner:
                runner.cancel()
            self.rooms.pop(room.code, None)
            log.info("torn down empty room %s", room.code)
            return
        if room.host_id == link.player_id:
            new_host = next((p for p in room.players.values() if not p.is_bot), None)
            room.host_id = new_host.id if new_host else None
        await self.sio.emit(
            "lobby_update",
            {
                "players": [p.to_public() for p in room.players.values()],
                "host_id": room.host_id,
            },
            room=room.code,
        )

    # --- Helpers ---------------------------------------------------------

    def _require_link(self, sid: str) -> SidLink:
        link = self.sid_links.get(sid)
        if link is None:
            raise RoomError("Not in a room")
        return link

    def _require_room(self, code: str) -> Room:
        room = self.rooms.get(code)
        if room is None:
            raise RoomError("Room not found")
        return room
