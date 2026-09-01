"""REAL integration tests against a live PostgreSQL instance — see
backend/tests/test_postgres_memory.py for the skip-if-unreachable pattern
this reuses.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.knowledge.models import KnowledgeCategory, KnowledgeRecord, KnowledgeStatus
from app.knowledge.postgres_store import PostgresKnowledgeStore
from app.knowledge.service import KnowledgeService

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
        await conn.execute("TRUNCATE knowledge")
    await p.close()


@pytest.fixture
def project():
    return f"proj-{uuid.uuid4()}"


@pytest.mark.asyncio
async def test_create_and_search(pool, project):
    store = PostgresKnowledgeStore(pool)
    record = KnowledgeRecord(
        id=str(uuid.uuid4()),
        category=KnowledgeCategory.TECHNICAL_KNOWLEDGE,
        title="Use asyncpg for Postgres access",
        content="asyncpg is faster than psycopg2 for async workloads.",
        project=project,
    )
    created = await store.create(record)
    assert created.id == record.id

    results = await store.search(project=project, query="asyncpg")
    assert len(results) == 1
    assert results[0].title == record.title


@pytest.mark.asyncio
async def test_record_usage_and_adjust_confidence(pool, project):
    store = PostgresKnowledgeStore(pool)
    record = await store.create(
        KnowledgeRecord(id=str(uuid.uuid4()), category=KnowledgeCategory.SOLUTIONS, title="x", content="y", project=project, confidence=0.5)
    )

    await store.record_usage(record.id)
    fetched = await store.get(record.id)
    assert fetched.usage_count == 1
    assert fetched.last_used_at is not None

    new_confidence = await store.adjust_confidence(record.id, -0.9)
    assert new_confidence == pytest.approx(0.0)  # clamped, not negative
    new_confidence = await store.adjust_confidence(record.id, 5.0)
    assert new_confidence == pytest.approx(1.0)  # clamped, not > 1


@pytest.mark.asyncio
async def test_service_deduplicates_similar_knowledge(pool, project):
    store = PostgresKnowledgeStore(pool)
    service = KnowledgeService(store, EventBus(), similarity_threshold=0.6)

    first = await service.learn_from_result(
        project=project,
        category=KnowledgeCategory.SOLUTIONS,
        title="Fix flaky WebSocket reconnect",
        content="Add exponential backoff on reconnect.",
        source="task-1",
    )
    second = await service.learn_from_result(
        project=project,
        category=KnowledgeCategory.SOLUTIONS,
        title="Fix flaky websocket reconnect issue",
        content="Add exponential backoff on reconnect attempts.",
        source="task-2",
    )

    # Same underlying fact -> merged into the same record, not duplicated.
    assert second.id == first.id
    all_records = await store.list_by_project(project, category=KnowledgeCategory.SOLUTIONS)
    assert len(all_records) == 1


@pytest.mark.asyncio
async def test_service_creates_new_when_genuinely_different(pool, project):
    store = PostgresKnowledgeStore(pool)
    service = KnowledgeService(store, EventBus(), similarity_threshold=0.82)

    await service.learn_from_result(
        project=project, category=KnowledgeCategory.SOLUTIONS, title="Fix WebSocket reconnect", content="backoff", source="t1"
    )
    await service.learn_from_result(
        project=project, category=KnowledgeCategory.SOLUTIONS, title="Fix database connection pool exhaustion", content="increase pool size", source="t2"
    )

    all_records = await store.list_by_project(project, category=KnowledgeCategory.SOLUTIONS)
    assert len(all_records) == 2


@pytest.mark.asyncio
async def test_service_publishes_knowledge_created_event(pool, project):
    store = PostgresKnowledgeStore(pool)
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler, EventType.KNOWLEDGE_CREATED)
    service = KnowledgeService(store, bus)

    await service.learn_from_result(project=project, category=KnowledgeCategory.TECHNICAL_KNOWLEDGE, title="t", content="c", source="s")

    assert len(received) == 1
    assert received[0].type == EventType.KNOWLEDGE_CREATED


@pytest.mark.asyncio
async def test_apply_correction_lowers_confidence_and_stores_new_fact(pool, project):
    store = PostgresKnowledgeStore(pool)
    service = KnowledgeService(store, EventBus())

    old = await store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.TOOL_KNOWLEDGE,
            title="Use npm for package management",
            content="This project uses npm.",
            project=project,
            confidence=0.8,
        )
    )

    correction = await service.apply_correction(project=project, old_term="npm", new_term="pnpm", raw_text="No, use pnpm instead of npm.")

    refreshed_old = await store.get(old.id)
    assert refreshed_old.confidence < 0.8
    assert correction.category == KnowledgeCategory.DECISIONS
    assert "pnpm" in correction.tags


@pytest.mark.asyncio
async def test_find_high_confidence_answer_only_matches_eligible_categories(pool, project):
    store = PostgresKnowledgeStore(pool)
    service = KnowledgeService(store, EventBus())

    await store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.SOLUTIONS,
            title="Fix CORS error",
            content="Add the frontend origin to allow_origins.",
            project=project,
            confidence=0.9,
        )
    )
    # A high confidence fact in a non-eligible category should NOT short-circuit.
    await store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.PROJECT_KNOWLEDGE,
            title="CORS project note",
            content="Some note about CORS.",
            project=project,
            confidence=0.99,
        )
    )

    answer = await service.find_high_confidence_answer(project=project, query="CORS error", min_confidence=0.85)
    assert answer is not None
    assert answer.category == KnowledgeCategory.SOLUTIONS

    none_found = await service.find_high_confidence_answer(project=project, query="something unrelated xyz", min_confidence=0.85)
    assert none_found is None
