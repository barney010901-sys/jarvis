from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SuggestionStatus(str, Enum):
    PENDING = "PENDING"
    SHOWN = "SHOWN"
    DISMISSED = "DISMISSED"
    ACCEPTED = "ACCEPTED"


@dataclass
class Suggestion:
    id: str
    priority: Priority
    title: str
    reason: str
    relevance: float
    source: str
    related_project: str | None = None
    related_goal: str | None = None
    confidence: float = 0.5
    status: SuggestionStatus = SuggestionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
