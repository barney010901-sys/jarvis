from __future__ import annotations

import uuid

import asyncpg

from app.escalation.models import EscalationEvent, Urgency


def _row_to_event(row: asyncpg.Record) -> EscalationEvent:
    return EscalationEvent(
        id=str(row["id"]),
        reason=row["reason"],
        urgency=Urgency(row["urgency"]),
        disclosure=row["disclosure"],
        contact_id=str(row["contact_id"]) if row["contact_id"] else None,
        task_id=row["task_id"],
        result=row["result"],
        triggered_at=row["triggered_at"],
    )


class EscalationStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, event: EscalationEvent) -> EscalationEvent:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO escalation_events (id, contact_id, reason, urgency, disclosure, task_id, result)
                VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *
                """,
                event.id or str(uuid.uuid4()),
                event.contact_id,
                event.reason,
                event.urgency.value,
                event.disclosure,
                event.task_id,
                event.result,
            )
        return _row_to_event(row)

    async def set_result(self, event_id: str, result: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE escalation_events SET result = $2 WHERE id = $1", event_id, result)

    async def list_recent(self, limit: int = 50) -> list[EscalationEvent]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM escalation_events ORDER BY triggered_at DESC LIMIT $1", limit)
        return [_row_to_event(r) for r in rows]
