from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

MAX_HISTORY_TURNS = 10  # last 10 user<->assistant exchanges


@dataclass
class ConversationSession:
    messages: Deque[dict] = field(
        default_factory=lambda: deque(maxlen=MAX_HISTORY_TURNS * 2)
    )


_store: dict[str, ConversationSession] = {}


def get_session(session_id: str) -> ConversationSession:
    if session_id not in _store:
        _store[session_id] = ConversationSession()
    return _store[session_id]


def add_message(session_id: str, role: str, content: str) -> None:
    get_session(session_id).messages.append({"role": role, "content": content})


def get_history(session_id: str) -> list[dict]:
    return list(get_session(session_id).messages)


def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)

