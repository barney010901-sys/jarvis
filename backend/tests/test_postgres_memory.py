"""REAL integration tests against a live PostgreSQL instance (see
docs/PHASE_2.md, "REAL / MOCKED / NOT TESTED"). Skipped automatically if
TEST_DATABASE_URL isn't reachable, so the rest of the suite stays runnable
without Postgres installed.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.memory.postgres_store import (
    PostgresLongTermMemory,
    PostgresShortTermMemory,
    PostgresWorkingMemory,
)
from app.memory.store import ConversationTurn, LongTermFact

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


async def _try_connect():
    try:
        pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return pool
    except Exception:
        return None


@pytest.fixture
async def pool():
    p = await _try_connect()
    if p is None:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")
    yield p
    async with p.acquire() as conn:
        await conn.execute("TRUNCATE working_memory, short_term_memory, long_term_memory")
    await p.close()


@pytest.mark.asyncio
async def test_working_memory_roundtrip(pool):
    memory = PostgresWorkingMemory(pool)
    task_id = str(uuid.uuid4())

    assert await memory.get(task_id, "plan") is None
    await memory.set(task_id, "plan", {"steps": ["a", "b"]})
    assert await memory.get(task_id, "plan") == {"steps": ["a", "b"]}

    await memory.set(task_id, "plan", {"steps": ["a", "b", "c"]})
    assert await memory.get(task_id, "plan") == {"steps": ["a", "b", "c"]}

    await memory.clear(task_id)
    assert await memory.get(task_id, "plan") is None


@pytest.mark.asyncio
async def test_short_term_memory_roundtrip(pool):
    memory = PostgresShortTermMemory(pool)
    session_id = f"s-{uuid.uuid4()}"

    await memory.append(session_id, ConversationTurn(role="user", content="hello"))
    await memory.append(session_id, ConversationTurn(role="assistant", content="hi there"))

    turns = await memory.recent(session_id)
    assert [t.content for t in turns] == ["hello", "hi there"]
    assert [t.role for t in turns] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_short_term_memory_recent_respects_limit_and_order(pool):
    memory = PostgresShortTermMemory(pool)
    session_id = f"s-{uuid.uuid4()}"
    for i in range(5):
        await memory.append(session_id, ConversationTurn(role="user", content=f"msg-{i}"))

    turns = await memory.recent(session_id, limit=3)
    assert [t.content for t in turns] == ["msg-2", "msg-3", "msg-4"]


@pytest.mark.asyncio
async def test_short_term_memory_prune(pool):
    memory = PostgresShortTermMemory(pool)
    session_id = f"s-{uuid.uuid4()}"
    for i in range(5):
        await memory.append(session_id, ConversationTurn(role="user", content=f"msg-{i}"))

    deleted = await memory.prune(session_id, keep_last=2)
    assert deleted == 3
    remaining = await memory.recent(session_id, limit=10)
    assert [t.content for t in remaining] == ["msg-3", "msg-4"]


@pytest.mark.asyncio
async def test_long_term_memory_add_search_delete(pool):
    memory = PostgresLongTermMemory(pool)
    project = f"proj-{uuid.uuid4()}"
    fact = LongTermFact(id=str(uuid.uuid4()), project=project, content="Uses PostgreSQL for storage", tags=["db"])

    await memory.add(fact)
    results = await memory.search(project, "postgresql")
    assert len(results) == 1
    assert results[0].content == fact.content

    no_match = await memory.search(project, "mongodb")
    assert no_match == []

    await memory.delete(fact.id)
    assert await memory.search(project, "postgresql") == []


@pytest.mark.asyncio
async def test_long_term_memory_scoped_by_project(pool):
    memory = PostgresLongTermMemory(pool)
    project_a = f"proj-a-{uuid.uuid4()}"
    project_b = f"proj-b-{uuid.uuid4()}"
    await memory.add(LongTermFact(id=str(uuid.uuid4()), project=project_a, content="shared keyword hello", tags=[]))
    await memory.add(LongTermFact(id=str(uuid.uuid4()), project=project_b, content="shared keyword hello", tags=[]))

    results = await memory.search(project_a, "hello")
    assert len(results) == 1
