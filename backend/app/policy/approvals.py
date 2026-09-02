"""The durable Approval Center backing store (section 70). Every ASK
decision from `PolicyEngine.evaluate()` gets a row here, sharing its `id`
with the underlying `ConfirmationManager` confirmation — one gate
(`ConfirmationManager`), one durable record (`ApprovalStore`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg


@dataclass
class Approval:
    id: str
    kind: str
    title: str
    description: str
    risk: str = "unknown"
    payload: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None
    status: str = "PENDING"
    task_id: str | None = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


def _row_to_approval(row: asyncpg.Record) -> Approval:
    return Approval(
        id=str(row["id"]),
        kind=row["kind"],
        title=row["title"],
        description=row["description"],
        risk=row["risk"],
        payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"]),
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        status=row["status"],
        task_id=row["task_id"],
        requested_at=row["requested_at"],
        resolved_at=row["resolved_at"],
    )


class ApprovalStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, approval: Approval) -> Approval:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO approvals (id, kind, title, description, payload, risk, cost_usd, status, task_id)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)
                RETURNING *
                """,
                approval.id,
                approval.kind,
                approval.title,
                approval.description,
                json.dumps(approval.payload),
                approval.risk,
                approval.cost_usd,
                approval.status,
                approval.task_id,
            )
        return _row_to_approval(row)

    async def set_status(self, approval_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE approvals SET status = $2, resolved_at = now() WHERE id = $1", approval_id, status
            )

    async def get(self, approval_id: str) -> Approval | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM approvals WHERE id = $1", approval_id)
        return _row_to_approval(row) if row else None

    async def list_pending(self, limit: int = 50) -> list[Approval]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM approvals WHERE status = 'PENDING' ORDER BY requested_at DESC LIMIT $1", limit)
        return [_row_to_approval(r) for r in rows]

    async def list_recent(self, limit: int = 50) -> list[Approval]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM approvals ORDER BY requested_at DESC LIMIT $1", limit)
        return [_row_to_approval(r) for r in rows]
