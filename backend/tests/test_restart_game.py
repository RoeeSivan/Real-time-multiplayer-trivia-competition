"""End-to-end socket test: host can restart a friends-mode game in the same room.

Reproduces the race that caused `restart_game` to ack `{ok: False, error: "Room
not found"}`: the pending `_cleanup_after` task's `finally` block was popping
the room out of `self.rooms` even when the task was cancelled by an in-flight
restart. After this fix, the cancelled task short-circuits via the
`except CancelledError: return` and leaves cleanup to `restart_game_by_host`.
"""
from __future__ import annotations

import asyncio
import socket
import threading

import pytest
import socketio
import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def patched_config(monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "QUESTION_TIME", 1)
    monkeypatch.setattr(config, "REVEAL_TIME", 0.2)
    monkeypatch.setattr(config, "START_COUNTDOWN", 1)
    monkeypatch.setattr(config, "BOT_MIN_DELAY", 0.1)
    monkeypatch.setattr(config, "BOT_MAX_DELAY_GAP", 0.05)


class _ServerThread(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.server: uvicorn.Server | None = None

    def run(self) -> None:
        from backend.main import app
        cfg = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(cfg)
        self.server.run()

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


@pytest.mark.asyncio
async def test_host_can_restart_friends_game(patched_config):
    port = _free_port()
    server = _ServerThread(port)
    server.start()

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.1)
    else:
        raise RuntimeError("server did not start")

    host = socketio.AsyncClient()
    guest = socketio.AsyncClient()

    host_game_over = asyncio.Event()
    guest_game_over = asyncio.Event()
    host_starting_count = [0]

    @host.on("question")
    async def host_q(data):
        await host.emit("submit_answer", {"question_idx": data["idx"], "option_idx": 0})

    @guest.on("question")
    async def guest_q(data):
        await guest.emit("submit_answer", {"question_idx": data["idx"], "option_idx": 0})

    @host.on("game_over")
    def _host_go(_data):
        host_game_over.set()

    @guest.on("game_over")
    def _guest_go(_data):
        guest_game_over.set()

    @host.on("game_starting")
    def _host_starting(_data):
        host_starting_count[0] += 1

    try:
        await host.connect(f"http://127.0.0.1:{port}", socketio_path="/socket.io")
        await guest.connect(f"http://127.0.0.1:{port}", socketio_path="/socket.io")

        ack = await host.call("create_room", {"mode": "friends", "name": "Host"})
        assert ack["ok"], ack
        room_code = ack["room_code"]

        ack = await guest.call("join_room", {"room_code": room_code, "name": "Guest"})
        assert ack["ok"], ack

        ack = await host.call("start_game", {})
        assert ack["ok"], ack

        await asyncio.wait_for(host_game_over.wait(), timeout=30)
        await asyncio.wait_for(guest_game_over.wait(), timeout=5)

        host_game_over.clear()
        guest_game_over.clear()

        # The bug: this used to ack `{ok: False, error: "Room not found"}`
        # because the cancelled cleanup task's `finally` block popped the
        # room out of the manager's rooms dict before `_start` could
        # re-acquire it.
        ack = await host.call("restart_game", {})
        assert ack["ok"], f"restart failed: {ack}"

        # Second game must run end-to-end with both clients still in the
        # same room.
        await asyncio.wait_for(host_game_over.wait(), timeout=30)
        await asyncio.wait_for(guest_game_over.wait(), timeout=5)
        assert host_starting_count[0] == 2

        await host.disconnect()
        await guest.disconnect()
    finally:
        server.stop()
        server.join(timeout=5)


@pytest.mark.asyncio
async def test_only_host_can_restart(patched_config):
    port = _free_port()
    server = _ServerThread(port)
    server.start()

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.1)
    else:
        raise RuntimeError("server did not start")

    host = socketio.AsyncClient()
    guest = socketio.AsyncClient()

    host_game_over = asyncio.Event()
    guest_game_over = asyncio.Event()

    @host.on("question")
    async def host_q(data):
        await host.emit("submit_answer", {"question_idx": data["idx"], "option_idx": 0})

    @guest.on("question")
    async def guest_q(data):
        await guest.emit("submit_answer", {"question_idx": data["idx"], "option_idx": 0})

    @host.on("game_over")
    def _host_go(_d):
        host_game_over.set()

    @guest.on("game_over")
    def _guest_go(_d):
        guest_game_over.set()

    try:
        await host.connect(f"http://127.0.0.1:{port}", socketio_path="/socket.io")
        await guest.connect(f"http://127.0.0.1:{port}", socketio_path="/socket.io")

        ack = await host.call("create_room", {"mode": "friends", "name": "Host"})
        room_code = ack["room_code"]
        await guest.call("join_room", {"room_code": room_code, "name": "Guest"})
        await host.call("start_game", {})

        await asyncio.wait_for(host_game_over.wait(), timeout=30)
        await asyncio.wait_for(guest_game_over.wait(), timeout=5)

        ack = await guest.call("restart_game", {})
        assert ack["ok"] is False
        assert "host" in ack["error"].lower()

        await host.disconnect()
        await guest.disconnect()
    finally:
        server.stop()
        server.join(timeout=5)
