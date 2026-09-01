"""Knowledge record shape (Phase 2, section 2F). Backed by the `knowledge`
table in memory/migrations/0002_phase2.sql — keep the CHECK constraints
there in sync with these enums.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class KnowledgeCategory(str, Enum):
    USER_PREFERENCES = "USER_PREFERENCES"
    PROJECT_KNOWLEDGE = "PROJECT_KNOWLEDGE"
    TECHNICAL_KNOWLEDGE = "TECHNICAL_KNOWLEDGE"
    WORKFLOWS = "WORKFLOWS"
    DECISIONS = "DECISIONS"
    SOLUTIONS = "SOLUTIONS"
    TOOL_KNOWLEDGE = "TOOL_KNOWLEDGE"
    ERROR_FIXES = "ERROR_FIXES"
    DESIGN_SYSTEMS = "DESIGN_SYSTEMS"
    SUCCESSFUL_TASKS = "SUCCESSFUL_TASKS"
    FUTURE_RELEVANT_KNOWLEDGE = "FUTURE_RELEVANT_KNOWLEDGE"


class KnowledgeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"


@dataclass
class KnowledgeRecord:
    id: str
    category: KnowledgeCategory
    title: str
    content: str
    source: str = "unknown"
    source_type: str = "manual"
    project: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    last_verified_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0
    last_used_at: datetime | None = None
