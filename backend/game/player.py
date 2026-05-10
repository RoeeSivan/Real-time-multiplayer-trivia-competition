"""Player state — humans and bots share one class with an `is_bot` flag."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Player:
    name: str
    is_bot: bool = False
    sid: str | None = None  # Socket.IO session id (None for bots)
    score: int = 0

    # Per-game help inventory — each held until used.
    help_fifty_used: bool = False
    help_friend_used: bool = False
    help_double_used: bool = False
    # Set when the player activates Double-Score for the *current* question.
    double_armed: bool = False

    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def to_public(self) -> dict[str, object]:
        """Serialisable view for clients (no internal flags)."""
        return {
            "id": self.id,
            "name": self.name,
            "is_bot": self.is_bot,
            "score": self.score,
        }
