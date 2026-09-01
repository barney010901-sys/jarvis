from __future__ import annotations

import os

import asyncpg
import pytest

from agent.provider.base import ProviderResult, Usage
from app.cost.models import BudgetState
from app.cost.store import InMemoryUsageStore, PostgresUsageStore
from app.cost.tracker import CostTracker

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


@pytest.mark.asyncio
async def test_in_memory_tracker_records_usage_and_computes_cost():
    tracker = CostTracker(InMemoryUsageStore(), daily_budget_usd=5.0)
    result = ProviderResult(text="hi", usage=Usage(input_tokens=1000, output_tokens=500), model="claude-sonnet-5")

    usage = await tracker.record_provider_usage(result, provider="claude", role="primary")
    assert usage.estimated_cost_usd > 0
    assert tracker.counters.requests_to_primary == 1

    status = await tracker.budget_status()
    assert status.state == BudgetState.OK
    assert status.spent_today_usd == pytest.approx(usage.estimated_cost_usd)


@pytest.mark.asyncio
async def test_budget_transitions_near_limit_and_exceeded():
    tracker = CostTracker(InMemoryUsageStore(), daily_budget_usd=0.01)
    result = ProviderResult(text="hi", usage=Usage(input_tokens=1_000_000, output_tokens=1_000_000), model="claude-sonnet-5")

    await tracker.record_provider_usage(result, provider="claude", role="primary")
    status = await tracker.budget_status()
    assert status.state == BudgetState.EXCEEDED


@pytest.mark.asyncio
async def test_record_avoided_request_increments_counters():
    tracker = CostTracker(InMemoryUsageStore(), daily_budget_usd=5.0)
    await tracker.record_avoided_request(task_id="t1", reason="high confidence knowledge match")
    assert tracker.counters.avoidable_requests_avoided == 1
    assert tracker.counters.knowledge_hits == 1


@pytest.mark.asyncio
async def test_postgres_usage_store_real_persistence():
    try:
        pool = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=2, timeout=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")

    store = PostgresUsageStore(pool)
    tracker = CostTracker(store, daily_budget_usd=5.0)
    result = ProviderResult(text="hi", usage=Usage(input_tokens=100, output_tokens=100), model="claude-haiku-4-5-20251001")

    await tracker.record_provider_usage(result, provider="claude", role="fast", task_id="test-task")
    status = await tracker.budget_status()
    assert status.spent_today_usd > 0

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM token_usage WHERE task_id = 'test-task'")
    await pool.close()
