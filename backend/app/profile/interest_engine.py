"""Interest Engine (2L): tracks recurring interests with recency decay.

Score model: each signal adds `weight` to the topic's score, but the
existing score is first decayed by elapsed time since it was last seen
(half-life based), so a topic mentioned once months ago fades, while one
mentioned repeatedly and recently stays high. This is intentionally simple
— frequency + recency — not a learned ranking model.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.profile.interface import ProfileStore
from app.profile.models import Interest

HALF_LIFE_DAYS = 14.0
# A topic is "detected" (interest.detected fires) the first time its
# signal_count reaches this — a single passing mention isn't a pattern.
DETECTION_THRESHOLD = 3


def _decay_factor(last_seen_at: datetime, now: datetime) -> float:
    elapsed_days = max((now - last_seen_at).total_seconds() / 86400.0, 0.0)
    return math.pow(0.5, elapsed_days / HALF_LIFE_DAYS)


class InterestEngine:
    def __init__(self, store: ProfileStore, event_bus: EventBus) -> None:
        self._store = store
        self._event_bus = event_bus

    async def record_signal(self, topic: str, *, project_slug: str | None = None, weight: float = 1.0) -> Interest:
        topic = topic.strip().lower()
        existing = await self._store.get_interest(topic, project_slug)
        now = datetime.now(timezone.utc)

        if existing is None:
            score = weight
            signal_count = 1
        else:
            decayed = existing.score * _decay_factor(existing.last_seen_at, now)
            score = decayed + weight
            signal_count = existing.signal_count + 1

        interest = await self._store.upsert_interest(topic, project_slug, score, signal_count)

        if signal_count == DETECTION_THRESHOLD:
            await self._event_bus.publish(
                Event(
                    type=EventType.INTEREST_DETECTED,
                    payload={"topic": topic, "project": project_slug, "score": score, "signal_count": signal_count},
                )
            )
        return interest

    async def top_interests(self, *, project_slug: str | None = None, limit: int = 10) -> list[tuple[Interest, float]]:
        """Returns (interest, effective_score_now) pairs, decayed to the
        current moment (the stored `score` reflects decay as of
        last_seen_at, not now — see module docstring)."""
        now = datetime.now(timezone.utc)
        interests = await self._store.top_interests(project_slug=project_slug, limit=limit * 2)
        scored = [(i, i.score * _decay_factor(i.last_seen_at, now)) for i in interests]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]
