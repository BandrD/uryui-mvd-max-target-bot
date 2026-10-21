from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DialogState(str, Enum):
    IDLE = "idle"
    WAIT_PHOTO = "wait_photo"
    PROCESSING = "processing"
    CHAT = "chat"


@dataclass
class UserSession:
    state: DialogState = DialogState.IDLE
    extra: dict[str, Any] = field(default_factory=dict)


class SessionStore:
    """In-memory сессии по chat_id (для прототипа)."""

    def __init__(self) -> None:
        self._data: dict[int, UserSession] = {}

    def get(self, chat_id: int) -> UserSession:
        if chat_id not in self._data:
            self._data[chat_id] = UserSession()
        return self._data[chat_id]

    def set_state(self, chat_id: int, state: DialogState) -> UserSession:
        session = self.get(chat_id)
        session.state = state
        return session

    def reset(self, chat_id: int) -> None:
        self._data[chat_id] = UserSession()
