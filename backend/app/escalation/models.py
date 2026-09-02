from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.communication.models import Contact


class Urgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class EscalationEvent:
    id: str
    reason: str
    urgency: Urgency
    disclosure: str
    contact_id: str | None = None
    task_id: str | None = None
    result: str = "PENDING"
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EscalationDecision:
    action: str  # 'NOT_NEEDED' | 'WAIT' | 'QUEUE' | 'ESCALATED' | 'NO_AUTHORIZED_CONTACT'
    reason: str
    contact: Contact | None = None
    message: str | None = None
    event_id: str | None = None
    delivered: bool = False
