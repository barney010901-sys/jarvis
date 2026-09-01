from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.tasks.interface import TaskStore
from app.tasks.models import TERMINAL_STATUSES, TaskRecord, TaskStatus


class InMemoryTaskStore(TaskStore):
    """Used by tests and as the Phase 1-compatible fallback when Postgres
    isn't reachable — matches the pattern of every other memory-tier
    store in this codebase."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    async def create(self, record: TaskRecord) -> TaskRecord:
        self._tasks[record.id] = record
        return record

    async def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    async def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        plan: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        record = self._tasks.get(task_id)
        if record is None:
            raise KeyError(f"no task with id {task_id}")
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        if plan is not None:
            record.plan = plan
        if result is not None:
            record.result = result
        if error is not None:
            record.error = error
        if status in TERMINAL_STATUSES:
            record.completed_at = record.updated_at

    async def list_recent(self, session_id: str | None = None, limit: int = 20) -> list[TaskRecord]:
        records = list(self._tasks.values())
        if session_id is not None:
            records = [r for r in records if r.session_id == session_id]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]
