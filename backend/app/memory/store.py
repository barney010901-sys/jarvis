"""Three memory tiers, defined as interfaces first so the in-memory
implementation used in Phase 1 and a future PostgreSQL-backed one
(`/memory/schema.sql`) are interchangeable behind the same API.

- WorkingMemory: current task/plan/tool-execution state. Cleared per task.
- ShortTermMemory: recent conversation turns for the current session.
- LongTermMemory: durable facts (preferences, decisions, project notes),
  keyed by project. Designed for pgvector similarity search later — see
  `search` below, which Phase 1 implements as naive substring matching.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LongTermFact:
    id: str
    project: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WorkingMemory(ABC):
    @abstractmethod
    async def set(self, task_id: str, key: str, value: Any) -> None: ...

    @abstractmethod
    async def get(self, task_id: str, key: str) -> Any | None: ...

    @abstractmethod
    async def clear(self, task_id: str) -> None: ...


class ShortTermMemory(ABC):
    @abstractmethod
    async def append(self, session_id: str, turn: ConversationTurn) -> None: ...

    @abstractmethod
    async def recent(self, session_id: str, limit: int = 20) -> list[ConversationTurn]: ...


class LongTermMemory(ABC):
    @abstractmethod
    async def add(self, fact: LongTermFact) -> None: ...

    @abstractmethod
    async def search(self, project: str, query: str, limit: int = 10) -> list[LongTermFact]:
        """Phase 1: naive substring search. A PostgreSQL-backed implementation
        should embed `query` and rank by pgvector cosine distance instead,
        without changing this signature."""

    @abstractmethod
    async def delete(self, fact_id: str) -> None:
        """Memory deletion (Phase 2, 2C). Used when a fact is superseded by
        a correction or otherwise no longer valid."""


class InMemoryWorkingMemory(WorkingMemory):
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def set(self, task_id: str, key: str, value: Any) -> None:
        self._store.setdefault(task_id, {})[key] = value

    async def get(self, task_id: str, key: str) -> Any | None:
        return self._store.get(task_id, {}).get(key)

    async def clear(self, task_id: str) -> None:
        self._store.pop(task_id, None)


class InMemoryShortTermMemory(ShortTermMemory):
    def __init__(self) -> None:
        self._sessions: dict[str, list[ConversationTurn]] = {}

    async def append(self, session_id: str, turn: ConversationTurn) -> None:
        self._sessions.setdefault(session_id, []).append(turn)

    async def recent(self, session_id: str, limit: int = 20) -> list[ConversationTurn]:
        return self._sessions.get(session_id, [])[-limit:]


class InMemoryLongTermMemory(LongTermMemory):
    def __init__(self) -> None:
        self._facts: list[LongTermFact] = []

    async def add(self, fact: LongTermFact) -> None:
        self._facts.append(fact)

    async def search(self, project: str, query: str, limit: int = 10) -> list[LongTermFact]:
        query_lower = query.lower()
        matches = [
            f
            for f in self._facts
            if f.project == project and query_lower in f.content.lower()
        ]
        return matches[:limit]

    async def delete(self, fact_id: str) -> None:
        self._facts = [f for f in self._facts if f.id != fact_id]
