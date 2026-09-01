"""Structured profile/project/goal/interest/workflow records (2J/2K/2L/2M/
2N). Deliberately separate dataclasses/tables per instruction: "do not mix
these into one giant memory table."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any


@dataclass
class ProfileFact:
    """A single explicitly-authorized fact about the user (2J). Examples:
    preferred name, timezone, communication style — not preferences about
    tools/tech (see Preference) and not projects (see Project)."""

    key: str
    value: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Preference:
    """Tool/technology/workflow/communication preferences (2J)."""

    key: str
    value: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Project:
    id: str
    slug: str
    name: str
    goals: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    status: str = "ACTIVE"  # ACTIVE | PAUSED | ARCHIVED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Goal:
    id: str
    project_slug: str | None
    title: str
    description: str = ""
    status: str = "ACTIVE"  # ACTIVE | DONE | PAUSED | ABANDONED
    target_date: date | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Interest:
    id: str
    topic: str
    project_slug: str | None
    score: float
    signal_count: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class Workflow:
    id: str
    name: str
    steps: list[str]
    project_slug: str | None
    evidence_count: int
    confirmed: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
