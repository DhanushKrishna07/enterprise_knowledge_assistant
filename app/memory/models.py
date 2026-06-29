"""
app/memory/models.py — Dataclasses representing a single message turn.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    role: str = ""  # "user" or "assistant"
    content: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }
