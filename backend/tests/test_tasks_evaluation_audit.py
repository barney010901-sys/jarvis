from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.audit.logger import AuditLogger
from app.audit.store import InMemoryAuditStore, PostgresAuditStore
from app.evaluation.engine import EvaluationEngine, EvaluationVerdict
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.planner.interface import PlanStep
from app.tools.base import ToolResult
from app.tools.registry import default_registry
from app.tasks.models import TaskRecord, TaskStatus
from app.tasks.postgres_store import PostgresTaskStore
from app.tasks.store import InMemoryTaskStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


# --- Task store (in-memory, unit) ---


@pytest.mark.asyncio
async def test_in_memory_task_store_lifecycle():
    store = InMemoryTaskStore()
    task = await store.create(TaskRecord(id="t1", session_id="s1", project="p1", request="do a thing"))
    assert task.status == TaskStatus.CREATED

    await store.set_status("t1", TaskStatus.PLANNED, plan=[{"description": "step 1"}])
    fetched = await store.get("t1")
    assert fetched.status == TaskStatus.PLANNED
    assert fetched.plan == [{"description": "step 1"}]

    await store.set_status("t1", TaskStatus.COMPLETED, result={"response": "done"})
    fetched = await store.get("t1")
    assert fetched.status == TaskStatus.COMPLETED
    assert fetched.completed_at is not None


@pytest.mark.asyncio
async def test_in_memory_task_store_list_recent_filters_by_session():
    store = InMemoryTaskStore()
    await store.create(TaskRecord(id="t1", session_id="s1", project="p1", request="a"))
    await store.create(TaskRecord(id="t2", session_id="s2", project="p1", request="b"))

    only_s1 = await store.list_recent(session_id="s1")
    assert [t.id for t in only_s1] == ["t1"]


# --- Task store (REAL Postgres) ---


@pytest.mark.asyncio
async def test_postgres_task_store_real_persistence():
    try:
        pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")

    store = PostgresTaskStore(pool)
    task_id = str(uuid.uuid4())
    await store.create(TaskRecord(id=task_id, session_id="s1", project="p1", request="build a landing page"))
    await store.set_status(task_id, TaskStatus.RUNNING)
    fetched = await store.get(task_id)
    assert fetched.status == TaskStatus.RUNNING

    await store.set_status(task_id, TaskStatus.FAILED, error="tool failed")
    fetched = await store.get(task_id)
    assert fetched.status == TaskStatus.FAILED
    assert fetched.error == "tool failed"
    assert fetched.completed_at is not None

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
    await pool.close()


# --- Evaluation engine (unit, real tools) ---


@pytest.mark.asyncio
async def test_evaluation_success_when_tools_ok_and_response_present():
    engine = EvaluationEngine()
    result = await engine.evaluate(
        plan_steps=[PlanStep(description="x", tool_name="project.inspect")],
        tool_results=[ToolResult.ok()],
        response_text="Here is the answer.",
    )
    assert result.verdict == EvaluationVerdict.SUCCESS


@pytest.mark.asyncio
async def test_evaluation_failed_when_a_tool_failed():
    engine = EvaluationEngine()
    result = await engine.evaluate(
        plan_steps=[PlanStep(description="x", tool_name="project.inspect")],
        tool_results=[ToolResult.ok(), ToolResult.fail("boom")],
        response_text="Here is the answer.",
    )
    assert result.verdict == EvaluationVerdict.FAILED


@pytest.mark.asyncio
async def test_evaluation_needs_review_when_no_response_text():
    engine = EvaluationEngine()
    result = await engine.evaluate(plan_steps=[], tool_results=[], response_text="")
    assert result.verdict == EvaluationVerdict.NEEDS_REVIEW


@pytest.mark.asyncio
async def test_evaluation_checks_expected_file_with_real_filesystem_tool(tmp_path):
    (tmp_path / "report.md").write_text("hello")
    registry = default_registry(str(tmp_path))
    engine = EvaluationEngine(tool_registry=registry)

    result = await engine.evaluate(
        plan_steps=[PlanStep(description="write report", expected_file="report.md")],
        tool_results=[],
        response_text="Done.",
    )
    assert result.verdict == EvaluationVerdict.SUCCESS
    assert any(c.name == "expected_files_exist" and c.passed for c in result.checks)


@pytest.mark.asyncio
async def test_evaluation_partial_when_expected_file_missing(tmp_path):
    registry = default_registry(str(tmp_path))
    engine = EvaluationEngine(tool_registry=registry)

    result = await engine.evaluate(
        plan_steps=[PlanStep(description="write report", expected_file="missing.md")],
        tool_results=[],
        response_text="Done.",
    )
    assert result.verdict == EvaluationVerdict.PARTIAL


# --- Audit logger (in-memory unit + REAL Postgres) ---


@pytest.mark.asyncio
async def test_audit_logger_records_every_published_event():
    bus = EventBus()
    store = InMemoryAuditStore()
    AuditLogger(bus, store).start()

    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1", payload={"request": "hi"}))
    await bus.publish(Event(type=EventType.TOOL_COMPLETED, task_id="t1", payload={"tool_name": "x", "success": True}))
    await bus.publish(Event(type=EventType.TASK_FAILED, task_id="t1", payload={"error": "boom"}))

    entries = await store.list_for_task("t1")
    assert [e.action for e in entries] == ["task.created", "tool.completed", "task.failed"]
    assert entries[1].result == "success"
    assert entries[2].result == "failure"
    assert entries[1].component == "tools"


@pytest.mark.asyncio
async def test_audit_logger_captures_confirmation_state():
    bus = EventBus()
    store = InMemoryAuditStore()
    AuditLogger(bus, store).start()

    await bus.publish(Event(type=EventType.CONFIRMATION_REQUIRED, task_id="t1", payload={"confirmation_id": "c1"}))
    await bus.publish(Event(type=EventType.CONFIRMATION_APPROVED, task_id="t1", payload={"confirmation_id": "c1"}))

    entries = await store.list_for_task("t1")
    assert entries[0].confirmation_state == "required"
    assert entries[1].confirmation_state == "approved"


@pytest.mark.asyncio
async def test_postgres_audit_store_real_persistence():
    try:
        pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")

    bus = EventBus()
    store = PostgresAuditStore(pool)
    AuditLogger(bus, store).start()
    task_id = str(uuid.uuid4())

    await bus.publish(Event(type=EventType.TASK_CREATED, task_id=task_id, payload={"request": "hi"}))
    entries = await store.list_for_task(task_id)
    assert len(entries) == 1
    assert entries[0].event_type == "task.created"

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM audit_log WHERE task_id = $1", task_id)
    await pool.close()
