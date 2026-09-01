"""Thin service layer over SuggestionQueue: enqueue + publish suggestion.created
on the existing EventBus, per 2P: "Every suggestion should include: reason,
relevance, related project, related goal, source, confidence, created_at."
LOW priority ones are stored silently (no different handling here — the
Android/API layer decides what to surface based on priority, per 2P).
"""
from __future__ import annotations

import uuid

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.suggestions.interface import SuggestionQueue
from app.suggestions.models import Priority, Suggestion, SuggestionStatus


class SuggestionService:
    def __init__(self, queue: SuggestionQueue, event_bus: EventBus) -> None:
        self._queue = queue
        self._event_bus = event_bus

    async def suggest(
        self,
        *,
        title: str,
        reason: str,
        relevance: float,
        source: str,
        priority: Priority = Priority.LOW,
        related_project: str | None = None,
        related_goal: str | None = None,
        confidence: float = 0.5,
    ) -> Suggestion:
        suggestion = Suggestion(
            id=str(uuid.uuid4()),
            priority=priority,
            title=title,
            reason=reason,
            relevance=relevance,
            source=source,
            related_project=related_project,
            related_goal=related_goal,
            confidence=confidence,
        )
        created = await self._queue.enqueue(suggestion)
        await self._event_bus.publish(
            Event(
                type=EventType.SUGGESTION_CREATED,
                payload={
                    "suggestion_id": created.id,
                    "priority": created.priority.value,
                    "title": created.title,
                    "reason": created.reason,
                },
            )
        )
        return created

    async def list_actionable(self, min_priority: Priority = Priority.MEDIUM, limit: int = 20) -> list[Suggestion]:
        """MEDIUM+ suggestions — what a client should actually show, per 2P
        ("MEDIUM: show when appropriate. HIGH: may notify/intervene")."""
        return await self._queue.list_pending(min_priority=min_priority, limit=limit)

    async def dismiss(self, suggestion_id: str) -> None:
        await self._queue.set_status(suggestion_id, SuggestionStatus.DISMISSED)

    async def accept(self, suggestion_id: str) -> None:
        await self._queue.set_status(suggestion_id, SuggestionStatus.ACCEPTED)
