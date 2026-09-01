"""High-level knowledge use-cases: learning from a completed task (2H),
applying a user correction (2I), and retrieving relevant knowledge for the
context engine (2D). Everything here goes through `KnowledgeStore` and the
existing `EventBus` — no separate storage or event system.
"""
from __future__ import annotations

import logging
import uuid

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.knowledge.interface import KnowledgeStore
from app.knowledge.models import KnowledgeCategory, KnowledgeRecord, KnowledgeStatus
from app.knowledge.similarity import find_most_similar

logger = logging.getLogger(__name__)

# A record's confidence has to fall below this to stop being served as an
# "already known" answer, but it isn't archived outright — see apply_correction.
STALE_CONFIDENCE_THRESHOLD = 0.2


class KnowledgeService:
    def __init__(self, store: KnowledgeStore, event_bus: EventBus, similarity_threshold: float = 0.82) -> None:
        self._store = store
        self._event_bus = event_bus
        self._similarity_threshold = similarity_threshold

    async def learn_from_result(
        self,
        *,
        project: str | None,
        category: KnowledgeCategory,
        title: str,
        content: str,
        source: str,
        source_type: str = "claude_response",
        tags: list[str] | None = None,
        confidence: float = 0.6,
    ) -> KnowledgeRecord:
        """Create or merge-update a knowledge record. Deduplicates against
        existing ACTIVE records in the same project+category (2G) before
        ever creating a new row."""
        existing = await self._store.list_by_project(project, category=category, limit=200)
        match = find_most_similar(title, content, existing) if existing else None

        if match and match[1] >= self._similarity_threshold:
            record, score = match
            logger.info("Knowledge dedup: merging into %s (similarity=%.2f)", record.id, score)
            # Prefer the longer/more specific content; bump confidence
            # slightly (repeated evidence for the same fact) and refresh
            # usage bookkeeping.
            merged_content = content if len(content) > len(record.content) else record.content
            record.content = merged_content
            record.confidence = min(1.0, record.confidence + 0.05)
            record.status = KnowledgeStatus.ACTIVE
            updated = await self._store.update(record)
            await self._event_bus.publish(
                Event(type=EventType.KNOWLEDGE_UPDATED, payload={"knowledge_id": updated.id, "reason": "deduplicated_merge"})
            )
            return updated

        record = KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=category,
            title=title,
            content=content,
            source=source,
            source_type=source_type,
            project=project,
            tags=tags or [],
            confidence=confidence,
        )
        created = await self._store.create(record)
        await self._event_bus.publish(Event(type=EventType.KNOWLEDGE_CREATED, payload={"knowledge_id": created.id, "category": category.value}))
        return created

    async def apply_correction(
        self, *, project: str | None, old_term: str, new_term: str, raw_text: str
    ) -> KnowledgeRecord:
        """User correction (2I): lower confidence on knowledge mentioning
        the superseded term, then store the correction itself with high
        confidence so future retrieval prefers it."""
        affected = await self._store.search(project=project, query=old_term, limit=20)
        for record in affected:
            new_confidence = await self._store.adjust_confidence(record.id, -0.3)
            if new_confidence < STALE_CONFIDENCE_THRESHOLD:
                await self._store.set_status(record.id, KnowledgeStatus.STALE)
            logger.info("Correction lowered confidence of %s to %.2f (old_term=%r)", record.id, new_confidence, old_term)

        correction = KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.DECISIONS,
            title=f"Correction: use {new_term} instead of {old_term}",
            content=raw_text,
            source="user_correction",
            source_type="user_correction",
            project=project,
            tags=["correction", old_term, new_term],
            confidence=0.9,
        )
        created = await self._store.create(correction)
        await self._event_bus.publish(
            Event(type=EventType.KNOWLEDGE_CREATED, payload={"knowledge_id": created.id, "category": correction.category.value, "reason": "user_correction"})
        )
        return created

    async def retrieve_relevant(
        self, *, project: str | None, query: str, limit: int = 5
    ) -> list[KnowledgeRecord]:
        """For the context engine: search, then mark each returned record
        as used (usage_count/last_used_at) since it's about to be included
        in a real request's context — see docs/ARCHITECTURE.md."""
        results = await self._store.search(project=project, query=query, limit=limit)
        for record in results:
            await self._store.record_usage(record.id)
        return results

    async def find_high_confidence_answer(
        self, *, project: str | None, query: str, min_confidence: float
    ) -> KnowledgeRecord | None:
        """The 2E cost-hierarchy short-circuit: if JARVIS already has a
        sufficiently-confident answer, the orchestrator can skip calling
        Claude entirely. Only SOLUTIONS/ERROR_FIXES/DECISIONS are eligible
        — categories where "the answer" is a well-defined, reusable fact,
        not a per-conversation reply."""
        eligible = {KnowledgeCategory.SOLUTIONS, KnowledgeCategory.ERROR_FIXES, KnowledgeCategory.DECISIONS}
        results = await self._store.search(project=project, query=query, limit=5)
        for record in results:
            if record.category in eligible and record.confidence >= min_confidence:
                await self._store.record_usage(record.id)
                return record
        return None
