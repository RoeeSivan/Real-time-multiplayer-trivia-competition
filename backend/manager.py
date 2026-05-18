"""GameManager — registry that owns rooms and their runners.

Single source of truth for which sid is in which room. Socket handlers
delegate to the manager so room/runner lifecycle stays in one place.
"""
from __future__ import annotations

import asyncio
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
        # Per-room cleanup task. Restarting a game must cancel the pending
        # cleanup so the new runner isn't torn down 60s into the next match.
        self.cleanup_tasks: dict[str, asyncio.Task] = {}

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

    async def rejoin_room(self, *, sid: str, room_code: str, player_id: str) -> dict:
        """Rebind a new sid to an existing player after a transport reconnect.

        Browsers behind proxies (Render, etc.) can drop the websocket and
        reopen with a new sid. Without this hook every reconnect would lose
        the player's membership.
        """
        room = self.rooms.get(room_code.upper())
        if room is None:
            raise RoomError("Room expired")
        player = room.players.get(player_id)
        if player is None:
            raise RoomError("Player not found")
        # Drop old sid link (if any) for this player.
        old_sid = player.sid
        if old_sid and old_sid != sid:
            self.sid_links.pop(old_sid, None)
        player.sid = sid
        self.sid_links[sid] = SidLink(room_code=room.code, player_id=player_id)
        await self.sio.enter_room(sid, room.code)
        log.info("rejoin %s → room %s as %s", sid, room.code, player.name)
        return {
            "room_code": room.code,
            "player_id": player_id,
            "is_host": room.host_id == player_id,
            "players": [p.to_public() for p in room.players.values()],
        }

    async def start_game_by_host(self, sid: str) -> None:
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        if room.host_id != link.player_id:
            raise RoomError("Only host can start")
        await self._start(room.code)

    async def restart_game_by_host(self, sid: str) -> None:
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        if room.host_id != link.player_id:
            raise RoomError("Only host can restart")
        if room.state != "ended":
            raise RoomError("Game still running")
        # Cancel the pending cleanup so the room survives.
        pending = self.cleanup_tasks.pop(room.code, None)
        if pending is not None and not pending.done():
            pending.cancel()
        self.runners.pop(room.code, None)
        room.reset_for_replay()
        await self.sio.emit(
            "lobby_update",
            {
                "players": [p.to_public() for p in room.players.values()],
                "host_id": room.host_id,
            },
            room=room.code,
        )
        await self._start(room.code)

    async def _start(self, code: str) -> None:
        room = self._require_room(code)
        # PDF: 1-3 bots when only one human is in the game. Apply to any mode.
        room.fill_with_bots_if_needed()
        room.start_game()
        runner = GameRunner(self.sio, room)
        self.runners[code] = runner
        runner.start()
        # Tear down room ~60s after the game ends so a player who stays on
        # the leaderboard screen can still receive late events. Track the
        # task so restart_game_by_host can cancel it.
        self.cleanup_tasks[code] = asyncio.create_task(
            self._cleanup_after(code, runner)
        )

    async def _cleanup_after(self, code: str, runner: GameRunner) -> None:
        try:
            if runner._main_task:
                try:
                    await runner._main_task
                except Exception:
                    pass
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return
        finally:
            self.cleanup_tasks.pop(code, None)
            # If the current runner for this code isn't ours, a restart
            # already swapped it in — leave the new runner + room alone.
            if self.runners.get(code) is runner:
                self.runners.pop(code, None)
                room = self.rooms.pop(code, None)
                if room is not None:
                    log.info("cleaned up room %s", code)

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

    async def reaction(self, sid: str, emoji: str) -> None:
        """Ephemeral emoji broadcast — no persistence, no history."""
        link = self._require_link(sid)
        room = self._require_room(link.room_code)
        player = room.players.get(link.player_id)
        if player is None:
            return
        await self.sio.emit(
            "reaction",
            {"player_id": player.id, "name": player.name, "emoji": emoji},
            room=room.code,
        )

    # --- Disconnect ------------------------------------------------------

    async def handle_disconnect(self, sid: str) -> None:
        """Clear sid binding but keep the player in the room so a reconnect
        with a new sid can rejoin via `rejoin_room`. Cleanup of stale rooms
        happens in `_cleanup_after` once the runner finishes."""
        link = self.sid_links.pop(sid, None)
        if link is None:
            return
        room = self.rooms.get(link.room_code)
        if room is None:
            return
        player = room.players.get(link.player_id)
        if player is not None and player.sid == sid:
            player.sid = None
        log.info("disconnect %s — kept player in room %s", sid, room.code)

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
