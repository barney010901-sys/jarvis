"""Mostly unit tests against in-memory memory stores (fast, no DB needed);
the knowledge/profile integration test is REAL against Postgres.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.context.engine import ContextEngine
from app.events.bus import EventBus
from app.knowledge.models import KnowledgeCategory, KnowledgeRecord
from app.knowledge.postgres_store import PostgresKnowledgeStore
from app.knowledge.service import KnowledgeService
from app.memory.store import (
    ConversationTurn,
    InMemoryLongTermMemory,
    InMemoryShortTermMemory,
    InMemoryWorkingMemory,
    LongTermFact,
)
from app.profile.postgres_store import PostgresProfileStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


@pytest.mark.asyncio
async def test_build_is_empty_with_nothing_stored():
    engine = ContextEngine(InMemoryWorkingMemory(), InMemoryShortTermMemory(), InMemoryLongTermMemory())
    bundle = await engine.build(task_id="t1", session_id="s1", project="p1")
    assert bundle.is_empty()
    assert bundle.included == {}


@pytest.mark.asyncio
async def test_build_includes_recent_conversation():
    short_term = InMemoryShortTermMemory()
    await short_term.append("s1", ConversationTurn(role="user", content="hello"))
    await short_term.append("s1", ConversationTurn(role="assistant", content="hi there"))
    engine = ContextEngine(InMemoryWorkingMemory(), short_term, InMemoryLongTermMemory())

    bundle = await engine.build(task_id="t1", session_id="s1", project="p1")
    assert "hello" in bundle.text
    assert "hi there" in bundle.text
    assert bundle.included["conversation_turns"] == 2
    assert bundle.history_truncated is False


@pytest.mark.asyncio
async def test_build_truncates_long_history_and_notes_it():
    short_term = InMemoryShortTermMemory()
    for i in range(20):
        await short_term.append("s1", ConversationTurn(role="user", content=f"msg-{i}"))
    engine = ContextEngine(InMemoryWorkingMemory(), short_term, InMemoryLongTermMemory())

    bundle = await engine.build(task_id="t1", session_id="s1", project="p1", max_recent_turns=5)
    assert bundle.history_truncated is True
    assert bundle.included["conversation_turns"] == 5
    assert "omitted" in bundle.text
    assert "msg-19" in bundle.text  # most recent kept
    assert "msg-0" not in bundle.text  # oldest dropped


@pytest.mark.asyncio
async def test_build_dedupes_long_term_facts():
    long_term = InMemoryLongTermMemory()
    await long_term.add(LongTermFact(id="1", project="p1", content="Uses PostgreSQL", tags=[]))
    await long_term.add(LongTermFact(id="2", project="p1", content="Uses PostgreSQL", tags=[]))  # duplicate content
    engine = ContextEngine(InMemoryWorkingMemory(), InMemoryShortTermMemory(), long_term)

    bundle = await engine.build(task_id="t1", session_id="s1", project="p1", query="postgres")
    assert bundle.included["long_term_facts"] == 1


@pytest.mark.asyncio
async def test_build_renders_plan_steps():
    working = InMemoryWorkingMemory()
    await working.set("t1", "plan", [{"description": "Inspect project"}, {"description": "Report"}])
    engine = ContextEngine(working, InMemoryShortTermMemory(), InMemoryLongTermMemory())

    bundle = await engine.build(task_id="t1", session_id="s1", project="p1")
    assert "1. Inspect project" in bundle.text
    assert "2. Report" in bundle.text
    assert bundle.included["plan_steps"] == 2


@pytest.mark.asyncio
async def test_build_includes_knowledge_and_profile_real_postgres():
    try:
        pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")

    project = f"proj-{uuid.uuid4()}"
    knowledge_store = PostgresKnowledgeStore(pool)
    await knowledge_store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.SOLUTIONS,
            title="Fix flaky reconnect",
            content="Use exponential backoff.",
            project=project,
            confidence=0.9,
        )
    )
    knowledge_service = KnowledgeService(knowledge_store, EventBus())

    profile_store = PostgresProfileStore(pool)
    await profile_store.set_preference("editor", "vscode")
    await profile_store.upsert_project(project, "Jarvis", goals=["ship phase 2"], technologies=["python", "postgres"])

    engine = ContextEngine(
        InMemoryWorkingMemory(),
        InMemoryShortTermMemory(),
        InMemoryLongTermMemory(),
        knowledge_service=knowledge_service,
        profile_store=profile_store,
    )

    bundle = await engine.build(task_id="t1", session_id="s1", project=project, query="reconnect")

    assert "Fix flaky reconnect" in bundle.text
    assert bundle.included["knowledge_records"] == 1
    assert "editor: vscode" in bundle.text
    assert "Project: Jarvis" in bundle.text
    assert "ship phase 2" in bundle.text

    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE knowledge, preferences")
        await conn.execute("DELETE FROM projects WHERE slug = $1", project)
    await pool.close()
