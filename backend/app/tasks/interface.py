from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.tasks.models import TaskRecord, TaskStatus


class TaskStore(ABC):
    @abstractmethod
    async def create(self, record: TaskRecord) -> TaskRecord: ...

    @abstractmethod
    async def get(self, task_id: str) -> TaskRecord | None: ...

    @abstractmethod
    async def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        plan: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def list_recent(self, session_id: str | None = None, limit: int = 20) -> list[TaskRecord]: ...
