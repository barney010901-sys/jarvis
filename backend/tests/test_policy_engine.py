"""REAL integration tests against a live PostgreSQL instance — PolicyEngine
reuses the real ConfirmationManager (no mocking of the gate itself).
"""
from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest

from app.events.bus import EventBus
from app.permissions.manager import ConfirmationManager
from app.policy.approvals import ApprovalStore
from app.policy.engine import PolicyEngine
from app.policy.models import AutonomyLevel, Decision, PolicyRequest
from app.policy.store import PolicyStore
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
        await conn.execute("TRUNCATE approvals, policies CASCADE")
        await conn.execute("DELETE FROM preferences WHERE key = 'autonomy_level'")
    await p.close()


async def _wait_for_pending(confirmations, timeout: float = 2.0):
    """Real Postgres I/O happens inside evaluate() before the confirmation
    is registered, so a bare `await asyncio.sleep(0)` isn't reliably enough
    — poll briefly instead of assuming a fixed number of event-loop ticks."""
    elapsed = 0.0
    while not confirmations.list_pending():
        await asyncio.sleep(0.01)
        elapsed += 0.01
        if elapsed > timeout:
            raise TimeoutError("no pending confirmation appeared in time")
    return confirmations.list_pending()[0]


def make_engine(pool, *, with_profile=True):
    event_bus = EventBus()
    confirmations = ConfirmationManager(event_bus)
    profile_store = PostgresProfileStore(pool) if with_profile else None
    engine = PolicyEngine(
        policy_store=PolicyStore(pool),
        approval_store=ApprovalStore(pool),
        confirmation_manager=confirmations,
        event_bus=event_bus,
        profile_store=profile_store,
    )
    return engine, confirmations, profile_store


@pytest.mark.asyncio
async def test_hard_block_denies_without_asking(pool):
    engine, confirmations, _ = make_engine(pool)
    result = await engine.evaluate(
        PolicyRequest(kind="wallet_transaction", title="gambling site", description="x", hard_block=True)
    )
    assert result.decision == Decision.DENY
    assert result.approval_id is None
    assert confirmations.list_pending() == []


@pytest.mark.asyncio
async def test_default_autonomy_level_auto_allows_low_risk(pool):
    engine, _, _ = make_engine(pool)
    result = await engine.evaluate(
        PolicyRequest(kind="other", title="read a file", description="x", risk="low", reversible=True)
    )
    assert result.decision == Decision.ALLOW
    assert "autonomy level LEVEL_3_ASK" in result.reason


@pytest.mark.asyncio
async def test_default_autonomy_level_asks_for_medium_risk_and_approves(pool):
    engine, confirmations, _ = make_engine(pool)

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    result, _ = await asyncio.gather(
        engine.evaluate(PolicyRequest(kind="communication", title="send email", description="x", risk="medium")),
        approve_soon(),
    )
    assert result.decision == Decision.ALLOW
    assert result.approval_id is not None

    approvals = ApprovalStore(pool)
    approval = await approvals.get(result.approval_id)
    assert approval.status == "APPROVED"


@pytest.mark.asyncio
async def test_rejection_denies_and_records_approval_status(pool):
    engine, confirmations, _ = make_engine(pool)

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id, reason="not now")

    result, _ = await asyncio.gather(
        engine.evaluate(PolicyRequest(kind="communication", title="send email", description="x", risk="medium")),
        reject_soon(),
    )
    assert result.decision == Decision.DENY

    approvals = ApprovalStore(pool)
    approval = await approvals.get(result.approval_id)
    assert approval.status == "REJECTED"


@pytest.mark.asyncio
async def test_level_1_suggest_always_asks_even_for_low_risk(pool):
    engine, confirmations, profile_store = make_engine(pool)
    await engine.set_autonomy_level(AutonomyLevel.LEVEL_1_SUGGEST)

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    result, _ = await asyncio.gather(
        engine.evaluate(PolicyRequest(kind="other", title="trivial read", description="x", risk="low", reversible=True)),
        approve_soon(),
    )
    assert result.decision == Decision.ALLOW
    assert result.approval_id is not None  # it WAS asked, unlike the default-level test above


@pytest.mark.asyncio
async def test_level_4_auto_allows_with_matching_preapproval_policy(pool):
    engine, confirmations, _ = make_engine(pool)
    await engine.set_autonomy_level(AutonomyLevel.LEVEL_4_EXECUTE_APPROVED)

    policy_store = PolicyStore(pool)
    await policy_store.upsert(
        "communication:routine_reply", description="Routine replies are pre-approved", rule_type="communication", config={"action": "AUTO"}
    )

    result = await engine.evaluate(
        PolicyRequest(
            kind="communication",
            title="routine reply",
            description="x",
            risk="medium",
            reversible=True,
            preapproval_key="communication:routine_reply",
        )
    )
    assert result.decision == Decision.ALLOW
    assert confirmations.list_pending() == []  # never asked — the policy pre-approved it


@pytest.mark.asyncio
async def test_level_4_without_matching_preapproval_still_asks(pool):
    engine, confirmations, _ = make_engine(pool)
    await engine.set_autonomy_level(AutonomyLevel.LEVEL_4_EXECUTE_APPROVED)

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    result, _ = await asyncio.gather(
        engine.evaluate(
            PolicyRequest(kind="communication", title="new type of message", description="x", risk="medium", preapproval_key="communication:unknown_kind")
        ),
        reject_soon(),
    )
    assert result.decision == Decision.DENY


@pytest.mark.asyncio
async def test_autonomy_level_persists_via_profile_store(pool):
    engine, _, _ = make_engine(pool)
    await engine.set_autonomy_level(AutonomyLevel.LEVEL_5_SAFE_AUTOMATION)
    assert await engine.autonomy_level() == AutonomyLevel.LEVEL_5_SAFE_AUTOMATION


@pytest.mark.asyncio
async def test_without_profile_store_uses_default_level(pool):
    engine, _, _ = make_engine(pool, with_profile=False)
    assert await engine.autonomy_level() == AutonomyLevel.LEVEL_3_ASK
