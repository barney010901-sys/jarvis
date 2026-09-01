"""End-to-end ClaudeOrchestrator tests: REAL Postgres (knowledge, profile,
tasks) + REAL tool registry + REAL event bus, with the LLM itself MOCKED
via FakeProvider (see agent/provider/fake_provider.py) — no network call,
no API key required. This is the most representative test of the full
2A flow this sandbox can run without a real ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import os
import uuid

import asyncpg
import pytest

from agent.provider.fake_provider import FakeProvider
from agent.provider.router import FALLBACK, FAST, PRIMARY, ModelRouter
from app.context import ContextEngine
from app.cost.store import InMemoryUsageStore
from app.cost.tracker import CostTracker
from app.evaluation.engine import EvaluationEngine
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.knowledge.models import KnowledgeCategory, KnowledgeRecord
from app.knowledge.postgres_store import PostgresKnowledgeStore
from app.knowledge.service import KnowledgeService
from app.learning.pipeline import LearningPipeline
from app.memory.store import InMemoryLongTermMemory, InMemoryShortTermMemory, InMemoryWorkingMemory
from app.orchestrator.claude_orchestrator import ClaudeOrchestrator
from app.permissions.manager import ConfirmationManager
from app.planner.claude_planner import ClaudePlanner
from app.profile.interest_engine import InterestEngine
from app.profile.postgres_store import PostgresProfileStore
from app.profile.workflow_detector import WorkflowDetector
from app.tasks.models import TaskStatus
from app.tasks.postgres_store import PostgresTaskStore
from app.tools.registry import default_registry

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")

DEFAULT_PLAN_JSON = json.dumps([{"description": "Inspect the project", "tool_name": "project.inspect"}])


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=4, timeout=3)
        async with p.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")
    yield p
    async with p.acquire() as conn:
        await conn.execute("TRUNCATE knowledge, tasks, interests, workflows RESTART IDENTITY CASCADE")
    await p.close()


@pytest.fixture
def project():
    return f"proj-{uuid.uuid4()}"


def build_orchestrator(
    pool,
    tmp_path,
    *,
    primary_response: str = "This is a fake Claude response.",
    plan_json: str = DEFAULT_PLAN_JSON,
    primary_fail_times: int = 0,
    min_confidence_to_skip_claude: float = 0.85,
):
    event_bus = EventBus()
    working_memory = InMemoryWorkingMemory()
    short_term_memory = InMemoryShortTermMemory()
    long_term_memory = InMemoryLongTermMemory()
    confirmations = ConfirmationManager(event_bus)
    tool_registry = default_registry(str(tmp_path))

    knowledge_store = PostgresKnowledgeStore(pool)
    knowledge_service = KnowledgeService(knowledge_store, event_bus)

    profile_store = PostgresProfileStore(pool)
    interest_engine = InterestEngine(profile_store, event_bus)
    workflow_detector = WorkflowDetector(profile_store)
    learning_pipeline = LearningPipeline(knowledge_service=knowledge_service, interest_engine=interest_engine, workflow_detector=workflow_detector)

    context_engine = ContextEngine(
        working_memory, short_term_memory, long_term_memory, knowledge_service=knowledge_service, profile_store=profile_store
    )

    fast_provider = FakeProvider(plan_json=plan_json, role=FAST, model="fake-fast")
    primary_provider = FakeProvider(response_text=primary_response, role=PRIMARY, fail_times=primary_fail_times, model="fake-primary")
    fallback_provider = FakeProvider(response_text="fallback response", role=FALLBACK, model="fake-fallback")
    router = ModelRouter({FAST: fast_provider, PRIMARY: primary_provider, FALLBACK: fallback_provider})

    planner = ClaudePlanner(router, [t.name for t in tool_registry.list()])
    task_store = PostgresTaskStore(pool)
    evaluation_engine = EvaluationEngine(tool_registry)
    usage_store = InMemoryUsageStore()
    cost_tracker = CostTracker(usage_store, daily_budget_usd=5.0)

    orchestrator = ClaudeOrchestrator(
        event_bus=event_bus,
        planner=planner,
        tool_registry=tool_registry,
        working_memory=working_memory,
        short_term_memory=short_term_memory,
        confirmation_manager=confirmations,
        context_engine=context_engine,
        model_router=router,
        task_store=task_store,
        evaluation_engine=evaluation_engine,
        cost_tracker=cost_tracker,
        knowledge_service=knowledge_service,
        learning_pipeline=learning_pipeline,
        profile_store=profile_store,
        min_confidence_to_skip_claude=min_confidence_to_skip_claude,
    )
    return {
        "orchestrator": orchestrator,
        "event_bus": event_bus,
        "task_store": task_store,
        "knowledge_store": knowledge_store,
        "profile_store": profile_store,
        "cost_tracker": cost_tracker,
        "usage_store": usage_store,
        "primary_provider": primary_provider,
        "fast_provider": fast_provider,
    }


@pytest.mark.asyncio
async def test_full_success_flow_event_sequence_and_task_status(pool, tmp_path, project):
    ctx = build_orchestrator(pool, tmp_path)
    events: list[Event] = []

    async def record(event: Event) -> None:
        events.append(event)

    ctx["event_bus"].subscribe(record)

    task_id = await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="What is the project status?")

    types = [e.type for e in events]
    assert types == [
        EventType.USER_MESSAGE,
        EventType.TASK_CREATED,
        EventType.CONTEXT_UPDATED,
        EventType.TASK_PLANNED,
        EventType.TASK_STARTED,
        EventType.TOOL_STARTED,
        EventType.TOOL_COMPLETED,
        *([EventType.TASK_DELTA] * len("This is a fake Claude response.".split(" "))),
        EventType.TASK_EVALUATING,
        EventType.KNOWLEDGE_CREATED,  # LearningPipeline stores the successful task as reusable knowledge
        EventType.TASK_COMPLETED,
    ]

    task = await ctx["task_store"].get(task_id)
    assert task.status == TaskStatus.COMPLETED
    assert "fake Claude response" in task.result["response"]


@pytest.mark.asyncio
async def test_successful_task_creates_knowledge_record(pool, tmp_path, project):
    ctx = build_orchestrator(pool, tmp_path)
    await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="Summarize the current architecture")

    records = await ctx["knowledge_store"].list_by_project(project, category=KnowledgeCategory.SUCCESSFUL_TASKS)
    assert len(records) == 1
    assert "Summarize the current architecture" in records[0].title


@pytest.mark.asyncio
async def test_cost_is_recorded_for_the_primary_call(pool, tmp_path, project):
    ctx = build_orchestrator(pool, tmp_path)
    await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="hello")

    assert ctx["cost_tracker"].counters.requests_to_primary == 1
    status = await ctx["cost_tracker"].budget_status()
    assert status.spent_today_usd >= 0  # fake model isn't in the pricing table -> falls back to default rate, still > 0 tokens
    assert ctx["primary_provider"].calls  # the primary provider was actually invoked


@pytest.mark.asyncio
async def test_skips_claude_when_high_confidence_knowledge_already_exists(pool, tmp_path, project):
    knowledge_store = PostgresKnowledgeStore(pool)
    await knowledge_store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.SOLUTIONS,
            title="Fix CORS error",
            content="Add the frontend origin to allow_origins in the FastAPI CORS middleware.",
            project=project,
            confidence=0.95,
        )
    )

    ctx = build_orchestrator(pool, tmp_path)
    task_id = await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="I'm getting a CORS error")

    assert ctx["primary_provider"].calls == []  # Claude was never called
    assert ctx["cost_tracker"].counters.avoidable_requests_avoided == 1
    task = await ctx["task_store"].get(task_id)
    assert task.result["served_from_knowledge"] is True
    assert "allow_origins" in task.result["response"]


@pytest.mark.asyncio
async def test_tool_lookup_failure_marks_task_failed(pool, tmp_path, project):
    plan_with_bad_tool = json.dumps([{"description": "do something", "tool_name": "not.a.real.tool"}])
    ctx = build_orchestrator(pool, tmp_path, plan_json=plan_with_bad_tool)
    events: list[Event] = []

    async def record(event: Event) -> None:
        events.append(event)

    ctx["event_bus"].subscribe(record, EventType.TASK_FAILED)

    task_id = await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="do the thing")

    assert len(events) == 1
    assert events[0].payload["stage"] == "tool_lookup"
    task = await ctx["task_store"].get(task_id)
    assert task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_claude_planner_falls_back_to_stub_planner_on_malformed_json(pool, tmp_path, project):
    ctx = build_orchestrator(pool, tmp_path, plan_json="not valid json at all")
    task_id = await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="anything")

    task = await ctx["task_store"].get(task_id)
    # StubPlanner's characteristic 3-step shape (see stub_planner.py) proves the fallback ran.
    assert len(task.plan) == 3
    assert "Report completion" in task.plan[-1]["description"]


@pytest.mark.asyncio
async def test_user_correction_lowers_confidence_of_conflicting_knowledge(pool, tmp_path, project):
    knowledge_store = PostgresKnowledgeStore(pool)
    old = await knowledge_store.create(
        KnowledgeRecord(
            id=str(uuid.uuid4()),
            category=KnowledgeCategory.TOOL_KNOWLEDGE,
            title="Use npm for package management",
            content="This project uses npm.",
            project=project,
            confidence=0.8,
        )
    )

    ctx = build_orchestrator(pool, tmp_path)
    await ctx["orchestrator"].handle_message(session_id="s1", project=project, text="No, use pnpm instead of npm.")

    refreshed = await knowledge_store.get(old.id)
    assert refreshed.confidence < 0.8

    corrections = await knowledge_store.list_by_project(project, category=KnowledgeCategory.DECISIONS)
    assert any("pnpm" in c.tags for c in corrections)
