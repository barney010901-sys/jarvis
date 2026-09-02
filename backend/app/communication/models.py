from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ContactRole(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    EMERGENCY = "EMERGENCY"
    CLIENT = "CLIENT"
    OTHER = "OTHER"


class Category(str, Enum):
    PERSONAL = "PERSONAL"
    CLIENT = "CLIENT"
    BUSINESS = "BUSINESS"
    IMPORTANT = "IMPORTANT"
    LOW_PRIORITY = "LOW_PRIORITY"
    UNKNOWN = "UNKNOWN"


class Direction(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


@dataclass
class Contact:
    id: str
    name: str
    relationship: str = ""
    role: ContactRole = ContactRole.OTHER
    channel: str = "unknown"
    allowed_categories: list[str] = field(default_factory=list)
    disclosure_limit: str = "minimum necessary"
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Communication:
    id: str
    direction: Direction
    category: Category
    summary: str
    policy_action: str  # 'AUTO' | 'ASK' | 'BLOCKED'
    contact_id: str | None = None
    channel: str = "unknown"
    task_id: str | None = None
    approval_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
