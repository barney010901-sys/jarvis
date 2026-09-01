from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg


@dataclass
class AuditEntry:
    event_type: str
    component: str
    action: str
    task_id: str | None = None
    result: str | None = None
    confirmation_state: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditStore(ABC):
    @abstractmethod
    async def record(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    async def list_for_task(self, task_id: str, limit: int = 200) -> list[AuditEntry]: ...


class InMemoryAuditStore(AuditStore):
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    async def record(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    async def list_for_task(self, task_id: str, limit: int = 200) -> list[AuditEntry]:
        return [e for e in self._entries if e.task_id == task_id][:limit]


class PostgresAuditStore(AuditStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(self, entry: AuditEntry) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (task_id, event_type, component, action, result, confirmation_state, payload, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                """,
                entry.task_id,
                entry.event_type,
                entry.component,
                entry.action,
                entry.result,
                entry.confirmation_state,
                json.dumps(entry.payload),
                entry.created_at,
            )

    async def list_for_task(self, task_id: str, limit: int = 200) -> list[AuditEntry]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM audit_log WHERE task_id = $1 ORDER BY created_at ASC LIMIT $2", task_id, limit
            )
        return [
            AuditEntry(
                event_type=r["event_type"],
                component=r["component"],
                action=r["action"],
                task_id=r["task_id"],
                result=r["result"],
                confirmation_state=r["confirmation_state"],
                payload=json.loads(r["payload"]) if r["payload"] else {},
                created_at=r["created_at"],
            )
            for r in rows
        ]
