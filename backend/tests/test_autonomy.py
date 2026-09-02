"""REAL integration tests for the Phase 4 AutonomyMode + resource budget
additions — see docs/PHASE_4_AUDIT.md §17(a) for why AutonomyMode is kept
distinct from Phase 3's AutonomyLevel.
"""
from __future__ import annotations

import os

import asyncpg
import pytest

from app.autonomy.budget_models import BudgetKind
from app.autonomy.budget_service import BudgetExceeded, ResourceBudgetService
from app.autonomy.budget_store import ResourceBudgetStore
from app.autonomy.models import AutonomyMode, DEFAULT_AUTONOMY_MODE
from app.autonomy.service import AutonomyModeService
from app.profile.postgres_store import PostgresProfileStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


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
        await conn.execute("DELETE FROM preferences WHERE key = 'autonomy_mode'")
        await conn.execute("TRUNCATE resource_budgets")
    await p.close()


@pytest.mark.asyncio
async def test_default_autonomy_mode_is_autonomous_not_human_gated(pool):
    """The user explicitly said not to default to human-gated (2026-09-02)."""
    service = AutonomyModeService(PostgresProfileStore(pool))
    assert await service.get_mode() == AutonomyMode.AUTONOMOUS
    assert DEFAULT_AUTONOMY_MODE == AutonomyMode.AUTONOMOUS
    assert DEFAULT_AUTONOMY_MODE != AutonomyMode.HUMAN_GATED


@pytest.mark.asyncio
async def test_autonomy_mode_persists(pool):
    service = AutonomyModeService(PostgresProfileStore(pool))
    await service.set_mode(AutonomyMode.SUPERVISED_AUTONOMY)
    assert await service.get_mode() == AutonomyMode.SUPERVISED_AUTONOMY


@pytest.mark.asyncio
async def test_budget_with_no_limit_set_is_unlimited_and_untracked(pool):
    budgets = ResourceBudgetService(ResourceBudgetStore(pool))
    result = await budgets.consume("global", BudgetKind.API_CALLS, 1_000_000)
    assert result is None


@pytest.mark.asyncio
async def test_budget_within_limit_is_recorded(pool):
    budgets = ResourceBudgetService(ResourceBudgetStore(pool))
    await budgets.set_limit("global", BudgetKind.MONEY_USD, 20.0)

    updated = await budgets.consume("global", BudgetKind.MONEY_USD, 5.0)
    assert updated.used_amount == 5.0
    assert updated.remaining == 15.0


@pytest.mark.asyncio
async def test_budget_exceeded_raises_and_does_not_record(pool):
    budgets = ResourceBudgetService(ResourceBudgetStore(pool))
    await budgets.set_limit("global", BudgetKind.MONEY_USD, 20.0)
    await budgets.consume("global", BudgetKind.MONEY_USD, 18.0)

    with pytest.raises(BudgetExceeded):
        await budgets.consume("global", BudgetKind.MONEY_USD, 5.0)

    # the failed attempt must not have been recorded
    assert await budgets.remaining("global", BudgetKind.MONEY_USD) == 2.0
