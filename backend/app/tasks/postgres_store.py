from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.tasks.interface import TaskStore
from app.tasks.models import TERMINAL_STATUSES, TaskRecord, TaskStatus


def _row_to_record(row: asyncpg.Record) -> TaskRecord:
    return TaskRecord(
        id=str(row["id"]),
        session_id=row["session_id"],
        project=row["project"],
        request=row["request"],
        status=TaskStatus(row["status"]),
        plan=json.loads(row["plan"]) if row["plan"] else None,
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


class PostgresTaskStore(TaskStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, record: TaskRecord) -> TaskRecord:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (id, session_id, project, request, status)
                VALUES ($1, $2, $3, $4, $5) RETURNING *
                """,
                record.id,
                record.session_id,
                record.project,
                record.request,
                record.status.value,
            )
        return _row_to_record(row)

    async def get(self, task_id: str) -> TaskRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        return _row_to_record(row) if row else None

    async def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        plan: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        completed_at_clause = "completed_at = now()," if status in TERMINAL_STATUSES else ""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE tasks SET
                    status = $2,
                    {completed_at_clause}
                    plan = COALESCE($3::jsonb, plan),
                    result = COALESCE($4::jsonb, result),
                    error = COALESCE($5, error),
                    updated_at = now()
                WHERE id = $1
                """,
                task_id,
                status.value,
                json.dumps(plan) if plan is not None else None,
                json.dumps(result) if result is not None else None,
                error,
            )

    async def list_recent(self, session_id: str | None = None, limit: int = 20) -> list[TaskRecord]:
        async with self._pool.acquire() as conn:
            if session_id is not None:
                rows = await conn.fetch(
                    "SELECT * FROM tasks WHERE session_id = $1 ORDER BY created_at DESC LIMIT $2", session_id, limit
                )
            else:
                rows = await conn.fetch("SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_record(r) for r in rows]
