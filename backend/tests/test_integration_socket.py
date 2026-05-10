"""End-to-end socket smoke test.

Boots the real ASGI app on an ephemeral port via uvicorn in a thread,
connects a python-socketio AsyncClient, plays a full 10-question CPU-mode
game, and verifies game_over arrives with a leaderboard.

Uses a short QUESTION_TIME by monkey-patching `config` so the test
finishes in a few seconds.
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
    monkeypatch.setattr(config, "QUESTION_TIME", 2)
    monkeypatch.setattr(config, "REVEAL_TIME", 1)
    monkeypatch.setattr(config, "START_COUNTDOWN", 1)
    monkeypatch.setattr(config, "BOT_MIN_DELAY", 0.2)
    monkeypatch.setattr(config, "BOT_MAX_DELAY_GAP", 0.1)


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
async def test_full_cpu_game_via_socket(patched_config):
    port = _free_port()
    server = _ServerThread(port)
    server.start()

    # Wait for server to come up.
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            await asyncio.sleep(0.1)
    else:
        raise RuntimeError("server did not start")

    received: dict[str, list] = {
        "question": [], "round_end": [], "answer_result": [], "game_over": [],
        "answer_received": [], "game_starting": [],
    }
    sio = socketio.AsyncClient()

    for ev in received:
        sio.on(ev, lambda data, _ev=ev: received[_ev].append(data))

    try:
        await sio.connect(f"http://127.0.0.1:{port}", socketio_path="/socket.io")
        ack = await sio.call("create_room", {"mode": "cpu", "name": "Tester"})
        assert ack["ok"], ack
        room_code = ack["room_code"]
        # 4 players (1 human + 3 bots).
        assert len(ack["players"]) == 4

        # Listen for questions and answer first option always.
        question_seen = asyncio.Event()
        async def on_q(data):
            received["question"].append(data)
            question_seen.set()
            try:
                await sio.emit("submit_answer", {"question_idx": data["idx"], "option_idx": 0})
            except Exception:
                pass
        sio.on("question", on_q)

        # Wait for game_over.
        game_over = asyncio.Event()
        sio.on("game_over", lambda data: (received["game_over"].append(data), game_over.set()))

        await asyncio.wait_for(game_over.wait(), timeout=60)
        await sio.disconnect()

        assert len(received["question"]) == 10
        assert len(received["round_end"]) == 10
        assert len(received["answer_result"]) == 10  # private, one per round for the human
        assert len(received["game_over"]) == 1
        lb = received["game_over"][0]["leaderboard"]
        assert len(lb) == 4
        assert {"rank", "name", "score", "is_bot", "id"}.issubset(lb[0].keys())
        assert room_code  # used
    finally:
        server.stop()
        server.join(timeout=5)
