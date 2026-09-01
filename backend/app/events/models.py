"""The event model shared by the orchestrator, permissions system, and the
WebSocket layer. This is the exact vocabulary the Android app should expect
to receive over `/ws`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    USER_MESSAGE = "user.message"
    VOICE_TRANSCRIPTION_COMPLETED = "voice.transcription.completed"
    TASK_CREATED = "task.created"
    TASK_PLANNED = "task.planned"
    TASK_STARTED = "task.started"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    CONFIRMATION_REQUIRED = "confirmation.required"
    CONFIRMATION_APPROVED = "confirmation.approved"
    CONFIRMATION_REJECTED = "confirmation.rejected"
    TASK_FAILED = "task.failed"
    TASK_COMPLETED = "task.completed"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def model_dump_json_safe(self) -> dict[str, Any]:
        """JSON-serializable dict, for sending over the WebSocket."""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }
