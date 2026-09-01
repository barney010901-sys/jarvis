"""In-process async pub/sub event bus.

Phase 1 implementation is intentionally simple: a dict of event type ->
list of async handlers, plus wildcard subscribers that receive every
event (used by the WebSocket layer). See docs/DECISIONS.md for why this
isn't Redis/NATS yet — the public API below is the seam a future
broker-backed implementation would preserve.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache

from app.events.models import Event, EventType

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]

_WILDCARD = "*"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, handler: Handler, event_type: EventType | None = None) -> None:
        """Subscribe to one event type, or every event when `event_type` is None."""
        key = event_type.value if event_type else _WILDCARD
        self._subscribers.setdefault(key, []).append(handler)

    def unsubscribe(self, handler: Handler, event_type: EventType | None = None) -> None:
        key = event_type.value if event_type else _WILDCARD
        handlers = self._subscribers.get(key, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        handlers = list(self._subscribers.get(event.type.value, []))
        handlers += list(self._subscribers.get(_WILDCARD, []))
        for handler in handlers:
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - a broken subscriber must not break the bus
                logger.exception("Event handler raised for event %s", event.type.value)

    def subscribe_queue(
        self, event_type: EventType | None = None
    ) -> tuple["asyncio.Queue[Event]", Callable[[], None]]:
        """Convenience: get a queue fed by every matching event, plus an
        `unsubscribe()` callable to stop feeding it.

        Used by the WebSocket layer to fan events out to one connection at a
        time without each connection needing to write its own handler.
        """
        queue: asyncio.Queue[Event] = asyncio.Queue()

        async def _handler(event: Event) -> None:
            await queue.put(event)

        self.subscribe(_handler, event_type)

        def unsubscribe() -> None:
            self.unsubscribe(_handler, event_type)

        return queue, unsubscribe


@lru_cache
def get_event_bus() -> EventBus:
    """Process-wide singleton. Tests should construct their own `EventBus()`
    instead of relying on this when isolation matters."""
    return EventBus()
