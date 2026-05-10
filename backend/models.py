"""Pydantic schemas for Socket.IO event payloads.

Used to validate inbound client events. Outbound server payloads are
plain dicts (built once in handlers/runner) — Socket.IO serialises them.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend import config


Mode = Literal["cpu", "friends"]
HelpType = Literal["fifty", "friend", "double"]


class CreateRoomIn(BaseModel):
    mode: Mode
    name: str = Field(min_length=1, max_length=20)


class JoinRoomIn(BaseModel):
    room_code: str = Field(min_length=config.ROOM_CODE_LENGTH, max_length=config.ROOM_CODE_LENGTH)
    name: str = Field(min_length=1, max_length=20)


class RejoinRoomIn(BaseModel):
    room_code: str = Field(min_length=config.ROOM_CODE_LENGTH, max_length=config.ROOM_CODE_LENGTH)
    player_id: str = Field(min_length=1, max_length=64)


class SubmitAnswerIn(BaseModel):
    question_idx: int = Field(ge=0)
    option_idx: int = Field(ge=0, le=3)


class UseHelpIn(BaseModel):
    type: HelpType


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=config.CHAT_MAX_LEN)
