"""REAL integration tests against a live PostgreSQL instance."""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.profile.interest_engine import DETECTION_THRESHOLD, InterestEngine
from app.profile.postgres_store import PostgresProfileStore
from app.profile.workflow_detector import CONFIRM_AFTER_EVIDENCE, WorkflowDetector

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
        await conn.execute("TRUNCATE profile_facts, preferences, goals, interests, workflows RESTART IDENTITY CASCADE")
        await conn.execute("DELETE FROM projects")
    await p.close()


@pytest.fixture
def project_slug():
    return f"proj-{uuid.uuid4()}"


@pytest.mark.asyncio
async def test_profile_facts_and_preferences_are_separate(pool):
    store = PostgresProfileStore(pool)
    await store.set_fact("preferred_name", "Barney")
    await store.set_preference("preferred_editor", "vscode")

    fact = await store.get_fact("preferred_name")
    pref = await store.get_preference("preferred_editor")
    assert fact.value == "Barney"
    assert pref.value == "vscode"
    # Same key name, different table -> no collision.
    assert await store.get_preference("preferred_name") is None


@pytest.mark.asyncio
async def test_project_upsert_and_touch(pool, project_slug):
    store = PostgresProfileStore(pool)
    created = await store.upsert_project(project_slug, "Jarvis", goals=["ship phase 2"], technologies=["python"])
    assert created.name == "Jarvis"

    updated = await store.upsert_project(project_slug, "Jarvis Assistant")
    assert updated.name == "Jarvis Assistant"
    assert updated.technologies == ["python"]  # empty goals/technologies on 2nd call don't wipe existing

    await store.touch_project(project_slug)
    fetched = await store.get_project(project_slug)
    assert fetched.last_active_at >= created.last_active_at


@pytest.mark.asyncio
async def test_goals_scoped_to_project(pool, project_slug):
    store = PostgresProfileStore(pool)
    await store.upsert_project(project_slug, "Jarvis")
    goal = await store.create_goal(project_slug, "Ship Phase 2")

    goals = await store.list_goals(project_slug=project_slug)
    assert len(goals) == 1
    assert goals[0].title == "Ship Phase 2"

    await store.update_goal_status(goal.id, "DONE")
    done_goals = await store.list_goals(project_slug=project_slug, status="DONE")
    assert len(done_goals) == 1


@pytest.mark.asyncio
async def test_interest_engine_accumulates_and_detects(pool, project_slug):
    store = PostgresProfileStore(pool)
    bus = EventBus()
    received: list[Event] = []

    async def record(event: Event) -> None:
        received.append(event)

    bus.subscribe(record, EventType.INTEREST_DETECTED)
    engine = InterestEngine(store, bus)

    for _ in range(DETECTION_THRESHOLD):
        await engine.record_signal("react native", project_slug=project_slug)

    top = await engine.top_interests(project_slug=project_slug)
    assert top[0][0].topic == "react native"
    assert top[0][0].signal_count == DETECTION_THRESHOLD
    assert len(received) == 1  # fires exactly once, at the threshold


@pytest.mark.asyncio
async def test_interest_ranking_prefers_frequent_topic(pool, project_slug):
    store = PostgresProfileStore(pool)
    engine = InterestEngine(store, EventBus())

    for _ in range(5):
        await engine.record_signal("postgres", project_slug=project_slug)
    await engine.record_signal("docker", project_slug=project_slug)

    top = await engine.top_interests(project_slug=project_slug, limit=2)
    topics = [i.topic for i, _score in top]
    assert topics[0] == "postgres"


@pytest.mark.asyncio
async def test_workflow_detector_ignores_single_step(pool, project_slug):
    detector = WorkflowDetector(PostgresProfileStore(pool))
    result = await detector.observe(["filesystem.read"], project_slug=project_slug)
    assert result is None


@pytest.mark.asyncio
async def test_workflow_detector_confirms_after_repeated_evidence(pool, project_slug):
    store = PostgresProfileStore(pool)
    detector = WorkflowDetector(store)
    sequence = ["project.inspect", "filesystem.read"]

    workflow = None
    for _ in range(CONFIRM_AFTER_EVIDENCE):
        workflow = await detector.observe(sequence, project_slug=project_slug)

    assert workflow is not None
    assert workflow.evidence_count == CONFIRM_AFTER_EVIDENCE
    assert workflow.confirmed is True

    workflows = await store.list_workflows(project_slug=project_slug, confirmed_only=True)
    assert len(workflows) == 1
