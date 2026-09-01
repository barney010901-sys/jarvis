"""Audit trail (2T): a wildcard subscriber on the existing EventBus — no
second event system, no scattered logging calls. Every event published
anywhere in the backend is recorded here automatically.
"""
from __future__ import annotations

from app.audit.store import AuditEntry, AuditStore
from app.events.bus import EventBus
from app.events.models import Event, EventType

# event type prefix -> component name, for the audit_log.component column.
_COMPONENT_BY_PREFIX = {
    "user": "user",
    "voice": "voice",
    "task": "orchestrator",
    "tool": "tools",
    "confirmation": "permissions",
    "context": "context",
    "knowledge": "knowledge",
    "interest": "profile",
    "suggestion": "suggestions",
}

_CONFIRMATION_EVENTS = {
    EventType.CONFIRMATION_REQUIRED: "required",
    EventType.CONFIRMATION_APPROVED: "approved",
    EventType.CONFIRMATION_REJECTED: "rejected",
}

_RESULT_KEY_BY_EVENT = {
    EventType.TOOL_COMPLETED: "success",
    EventType.TASK_FAILED: None,  # presence of the event itself means failure
    EventType.TASK_COMPLETED: None,  # presence of the event itself means success
}


def _classify(event: Event) -> tuple[str, str | None, str | None]:
    """Returns (component, result, confirmation_state)."""
    prefix = event.type.value.split(".", 1)[0]
    component = _COMPONENT_BY_PREFIX.get(prefix, prefix)

    result: str | None = None
    if event.type == EventType.TOOL_COMPLETED:
        result = "success" if event.payload.get("success") else "failure"
    elif event.type == EventType.TASK_COMPLETED:
        result = "success"
    elif event.type == EventType.TASK_FAILED:
        result = "failure"
    elif event.type == EventType.CONFIRMATION_REJECTED:
        result = "rejected"
    elif event.type == EventType.CONFIRMATION_APPROVED:
        result = "approved"

    confirmation_state = _CONFIRMATION_EVENTS.get(event.type)
    return component, result, confirmation_state


class AuditLogger:
    def __init__(self, event_bus: EventBus, store: AuditStore) -> None:
        self._event_bus = event_bus
        self._store = store
        self._started = False

    def start(self) -> None:
        """Idempotent: subscribes exactly once even if called again."""
        if self._started:
            return
        self._event_bus.subscribe(self._on_event)
        self._started = True

    async def _on_event(self, event: Event) -> None:
        component, result, confirmation_state = _classify(event)
        await self._store.record(
            AuditEntry(
                event_type=event.type.value,
                component=component,
                action=event.type.value,
                task_id=event.task_id,
                result=result,
                confirmation_state=confirmation_state,
                payload=event.payload,
                created_at=event.timestamp,
            )
        )
