"""Gates SENSITIVE tool execution behind an explicit confirmation step.

Flow:
1. Orchestrator wants to run a SENSITIVE tool -> calls `request_confirmation`.
2. That publishes `confirmation.required` on the event bus (the Android app
   is expected to render a dialog on receipt) and returns a future.
3. A client resolves it via `approve`/`reject` (wired to
   `POST /confirmations/{id}/approve|reject` in `app/api/routes.py`), which
   publishes `confirmation.approved` / `confirmation.rejected` and completes
   the future.
4. The orchestrator awaits the future; on rejection it raises
   `ConfirmationRejected` so callers can turn that into a `task.failed`.

Phase 1 keeps this in-memory and per-process, matching the event bus.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.events.bus import EventBus
from app.events.models import Event, EventType


class ConfirmationRejected(Exception):
    def __init__(self, confirmation_id: str, reason: str | None = None):
        self.confirmation_id = confirmation_id
        self.reason = reason
        super().__init__(f"Confirmation {confirmation_id} was rejected: {reason or 'no reason given'}")


@dataclass
class PendingConfirmation:
    id: str
    task_id: str | None
    tool_name: str
    description: str
    future: "asyncio.Future[bool]" = field(repr=False)


class ConfirmationManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._pending: dict[str, PendingConfirmation] = {}

    async def request_confirmation(
        self,
        *,
        tool_name: str,
        description: str,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Publish confirmation.required and wait for approve/reject.

        Returns True if approved, raises ConfirmationRejected if rejected.
        """
        confirmation_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        pending = PendingConfirmation(
            id=confirmation_id,
            task_id=task_id,
            tool_name=tool_name,
            description=description,
            future=loop.create_future(),
        )
        self._pending[confirmation_id] = pending

        await self._event_bus.publish(
            Event(
                type=EventType.CONFIRMATION_REQUIRED,
                task_id=task_id,
                payload={
                    "confirmation_id": confirmation_id,
                    "tool_name": tool_name,
                    "description": description,
                    "details": details or {},
                },
            )
        )

        approved = await pending.future
        if not approved:
            raise ConfirmationRejected(confirmation_id)
        return True

    async def approve(self, confirmation_id: str) -> None:
        pending = self._require_pending(confirmation_id)
        if not pending.future.done():
            pending.future.set_result(True)
        await self._event_bus.publish(
            Event(
                type=EventType.CONFIRMATION_APPROVED,
                task_id=pending.task_id,
                payload={"confirmation_id": confirmation_id},
            )
        )
        del self._pending[confirmation_id]

    async def reject(self, confirmation_id: str, reason: str | None = None) -> None:
        pending = self._require_pending(confirmation_id)
        if not pending.future.done():
            pending.future.set_result(False)
        await self._event_bus.publish(
            Event(
                type=EventType.CONFIRMATION_REJECTED,
                task_id=pending.task_id,
                payload={"confirmation_id": confirmation_id, "reason": reason},
            )
        )
        del self._pending[confirmation_id]

    def _require_pending(self, confirmation_id: str) -> PendingConfirmation:
        pending = self._pending.get(confirmation_id)
        if pending is None:
            raise KeyError(f"No pending confirmation with id {confirmation_id}")
        return pending

    def list_pending(self) -> list[PendingConfirmation]:
        return list(self._pending.values())
