"""REAL integration tests for the Phase 4 self-modification safety gate.

The one thing these tests must prove beyond doubt: a self_modification
proposal is NEVER auto-approved, at any autonomy level — see
docs/PHASE_4_AUDIT.md §17(b) and app/policy/engine.py's hard carve-out.
"""
from __future__ import annotations

import asyncio
import os

import asyncpg
import pytest

from app.events.bus import EventBus
from app.permissions.manager import ConfirmationManager
from app.policy.approvals import ApprovalStore
from app.policy.engine import PolicyEngine
from app.policy.models import AutonomyLevel
from app.policy.store import PolicyStore
from app.profile.postgres_store import PostgresProfileStore
from app.selfcode.models import ProposalStatus
from app.selfcode.service import SelfCodeService
from app.selfcode.store import SelfModificationStore

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
        await conn.execute("TRUNCATE self_modification_proposals, approvals, policies CASCADE")
        await conn.execute("DELETE FROM preferences WHERE key = 'autonomy_level'")
    await p.close()


async def _wait_for_pending(confirmations, timeout: float = 2.0):
    elapsed = 0.0
    while not confirmations.list_pending():
        await asyncio.sleep(0.01)
        elapsed += 0.01
        if elapsed > timeout:
            raise TimeoutError("no pending confirmation appeared in time")
    return confirmations.list_pending()[0]


def make_service(pool):
    event_bus = EventBus()
    confirmations = ConfirmationManager(event_bus)
    engine = PolicyEngine(
        policy_store=PolicyStore(pool),
        approval_store=ApprovalStore(pool),
        confirmation_manager=confirmations,
        event_bus=event_bus,
        profile_store=PostgresProfileStore(pool),
    )
    service = SelfCodeService(SelfModificationStore(pool), engine, event_bus)
    return service, engine, confirmations


@pytest.mark.asyncio
async def test_propose_always_asks_even_at_max_autonomy_level(pool):
    """The core safety property: LEVEL_5_SAFE_AUTOMATION auto-allows almost
    everything else, but must still ASK for a self-modification proposal."""
    service, engine, confirmations = make_service(pool)
    await engine.set_autonomy_level(AutonomyLevel.LEVEL_5_SAFE_AUTOMATION)

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    (proposal, _) = await asyncio.gather(
        service.propose(
            title="add a retry to X",
            reason="X fails intermittently",
            diff="--- a/x.py\n+++ b/x.py\n",
            test_plan="run test_x.py",
            rollback_plan="git revert",
            risk="low",  # even "low" risk must still ask
        ),
        approve_soon(),
    )
    assert proposal.status == ProposalStatus.APPROVED
    assert proposal.approval_id is not None  # it WAS asked — proves no auto-approval happened


@pytest.mark.asyncio
async def test_rejected_proposal_is_recorded_as_rejected(pool):
    service, engine, confirmations = make_service(pool)

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id, reason="too risky")

    (proposal, _) = await asyncio.gather(
        service.propose(
            title="rewrite the orchestrator",
            reason="perf",
            diff="diff",
            test_plan="plan",
            rollback_plan="rollback",
            risk="high",
        ),
        reject_soon(),
    )
    assert proposal.status == ProposalStatus.REJECTED


@pytest.mark.asyncio
async def test_apply_raises_not_implemented_even_when_approved(pool):
    """No sandbox/snapshot infra exists yet — apply() must never silently
    pretend to have changed the running system."""
    service, engine, confirmations = make_service(pool)

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    (proposal, _) = await asyncio.gather(
        service.propose(title="t", reason="r", diff="d", test_plan="tp", rollback_plan="rp"),
        approve_soon(),
    )
    assert proposal.status == ProposalStatus.APPROVED

    with pytest.raises(NotImplementedError):
        await service.apply(proposal.id)


@pytest.mark.asyncio
async def test_apply_rejects_a_non_approved_proposal_before_even_reaching_not_implemented(pool):
    service, engine, confirmations = make_service(pool)

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    (proposal, _) = await asyncio.gather(
        service.propose(title="t", reason="r", diff="d", test_plan="tp", rollback_plan="rp"),
        reject_soon(),
    )
    assert proposal.status == ProposalStatus.REJECTED

    with pytest.raises(ValueError, match="not APPROVED"):
        await service.apply(proposal.id)


@pytest.mark.asyncio
async def test_list_proposals_returns_newest_first(pool):
    service, engine, confirmations = make_service(pool)

    async def approve_both():
        for _ in range(2):
            pending = await _wait_for_pending(confirmations)
            await confirmations.approve(pending.id)

    await asyncio.gather(
        service.propose(title="first", reason="r", diff="d", test_plan="tp", rollback_plan="rp"),
        service.propose(title="second", reason="r", diff="d", test_plan="tp", rollback_plan="rp"),
        approve_both(),
    )

    proposals = await service.list_proposals()
    assert len(proposals) == 2
    assert {p.title for p in proposals} == {"first", "second"}
