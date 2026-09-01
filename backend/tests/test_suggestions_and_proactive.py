"""REAL integration tests against a live PostgreSQL instance."""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.knowledge.postgres_store import PostgresKnowledgeStore
from app.knowledge.service import KnowledgeService
from app.profile.interest_engine import InterestEngine
from app.profile.postgres_store import PostgresProfileStore
from app.proactive.learning import HIGH_PRIORITY_SCORE, ProactiveLearningEngine
from app.suggestions.models import Priority, Suggestion, SuggestionStatus
from app.suggestions.postgres_store import PostgresSuggestionQueue
from app.suggestions.service import SuggestionService

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with p.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")
    yield p
    async with p.acquire() as conn:
        await conn.execute("TRUNCATE suggestions, knowledge, interests")
    await p.close()


@pytest.fixture
def project_slug():
    return f"proj-{uuid.uuid4()}"


@pytest.mark.asyncio
async def test_suggestion_service_enqueues_and_publishes_event(pool):
    queue = PostgresSuggestionQueue(pool)
    bus = EventBus()
    received: list[Event] = []

    async def record(event: Event) -> None:
        received.append(event)

    bus.subscribe(record, EventType.SUGGESTION_CREATED)
    service = SuggestionService(queue, bus)

    await service.suggest(title="Try uv for Python packaging", reason="mentioned repeatedly", relevance=0.7, source="test", priority=Priority.MEDIUM)

    assert len(received) == 1
    pending = await service.list_actionable(min_priority=Priority.LOW)
    assert len(pending) == 1
    assert pending[0].title == "Try uv for Python packaging"


@pytest.mark.asyncio
async def test_list_actionable_filters_by_priority(pool):
    queue = PostgresSuggestionQueue(pool)
    service = SuggestionService(queue, EventBus())

    await service.suggest(title="low", reason="r", relevance=0.1, source="t", priority=Priority.LOW)
    await service.suggest(title="high", reason="r", relevance=0.9, source="t", priority=Priority.HIGH)

    only_high = await service.list_actionable(min_priority=Priority.HIGH)
    assert [s.title for s in only_high] == ["high"]

    everything = await service.list_actionable(min_priority=Priority.LOW)
    assert {s.title for s in everything} == {"low", "high"}


@pytest.mark.asyncio
async def test_dismiss_and_accept(pool):
    queue = PostgresSuggestionQueue(pool)
    service = SuggestionService(queue, EventBus())
    created = await service.suggest(title="x", reason="r", relevance=0.5, source="t")

    await service.dismiss(created.id)
    pending_after_dismiss = await service.list_actionable(min_priority=Priority.LOW)
    assert created.id not in [s.id for s in pending_after_dismiss]


@pytest.mark.asyncio
async def test_proactive_learning_disabled_by_default_produces_nothing(pool, project_slug):
    profile_store = PostgresProfileStore(pool)
    interest_engine = InterestEngine(profile_store, EventBus())
    knowledge_service = KnowledgeService(PostgresKnowledgeStore(pool), EventBus())
    suggestion_service = SuggestionService(PostgresSuggestionQueue(pool), EventBus())

    engine = ProactiveLearningEngine(
        interest_engine=interest_engine, knowledge_service=knowledge_service, suggestion_service=suggestion_service, enabled=False
    )
    titles = await engine.run_cycle(project_slug=project_slug)
    assert titles == []


@pytest.mark.asyncio
async def test_proactive_learning_creates_knowledge_and_suggestion_for_strong_interest(pool, project_slug):
    profile_store = PostgresProfileStore(pool)
    interest_engine = InterestEngine(profile_store, EventBus())
    knowledge_store = PostgresKnowledgeStore(pool)
    knowledge_service = KnowledgeService(knowledge_store, EventBus())
    suggestion_queue = PostgresSuggestionQueue(pool)
    suggestion_service = SuggestionService(suggestion_queue, EventBus())

    # Build up a strong, recent interest signal.
    for _ in range(int(HIGH_PRIORITY_SCORE) + 1):
        await interest_engine.record_signal("kubernetes", project_slug=project_slug)

    engine = ProactiveLearningEngine(
        interest_engine=interest_engine, knowledge_service=knowledge_service, suggestion_service=suggestion_service, enabled=True
    )
    titles = await engine.run_cycle(project_slug=project_slug)

    assert any("kubernetes" in t for t in titles)
    pending = await suggestion_service.list_actionable(min_priority=Priority.HIGH)
    assert any("kubernetes" in s.title for s in pending)

    knowledge_records = await knowledge_store.list_by_project(project_slug)
    assert any("kubernetes" in k.title for k in knowledge_records)
