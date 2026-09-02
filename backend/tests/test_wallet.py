"""REAL integration tests against a live PostgreSQL instance. The wallet's
policy gate reuses the real ConfirmationManager/PolicyEngine — nothing
here is mocked except, implicitly, the absence of any real payment rail
(see app/wallet/models.py's module docstring).
"""
from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.permissions.manager import ConfirmationManager
from app.policy.approvals import ApprovalStore
from app.policy.engine import PolicyEngine
from app.policy.store import PolicyStore
from app.wallet.models import PolicyColor
from app.wallet.service import WalletService
from app.wallet.store import WalletStore

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
        await conn.execute("TRUNCATE wallet_transactions, wallet_accounts, approvals CASCADE")
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
    policy = PolicyEngine(
        policy_store=PolicyStore(pool), approval_store=ApprovalStore(pool), confirmation_manager=confirmations, event_bus=event_bus
    )
    store = WalletStore(pool)
    service = WalletService(store, policy, event_bus)
    return service, store, confirmations, event_bus


@pytest.mark.asyncio
async def test_green_transaction_auto_approved_and_deducted(pool):
    service, store, confirmations, event_bus = make_service(pool)
    account = await store.get_or_create_account()
    await store.update_limits(account.id, approved_categories=["hosting"])
    events: list[Event] = []

    async def record(event: Event) -> None:
        events.append(event)

    event_bus.subscribe(record, EventType.WALLET_TRANSACTION_CREATED)

    result = await service.propose_transaction(amount_usd=5.0, vendor="digitalocean", category="hosting", purpose="VPS for Jarvis")

    assert result.approved is True
    assert result.policy_decision == PolicyColor.GREEN
    assert confirmations.list_pending() == []  # never asked
    assert len(events) == 1

    refreshed = await store.get_or_create_account()
    assert refreshed.balance_usd == account.balance_usd - 5.0


@pytest.mark.asyncio
async def test_yellow_unknown_category_asks_and_executes_on_approval(pool):
    service, store, confirmations, _ = make_service(pool)
    account = await store.get_or_create_account()

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    result, _ = await asyncio.gather(
        service.propose_transaction(amount_usd=3.0, vendor="some-new-saas", category="productivity_tool", purpose="trying a new tool"),
        approve_soon(),
    )
    assert result.policy_decision == PolicyColor.YELLOW
    assert result.approved is True

    refreshed = await store.get_or_create_account()
    assert refreshed.balance_usd == account.balance_usd - 3.0


@pytest.mark.asyncio
async def test_yellow_rejected_does_not_deduct_balance(pool):
    service, store, confirmations, _ = make_service(pool)
    account = await store.get_or_create_account()

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    result, _ = await asyncio.gather(
        service.propose_transaction(amount_usd=3.0, vendor="some-new-saas", category="productivity_tool", purpose="trying a new tool"),
        reject_soon(),
    )
    assert result.approved is False

    refreshed = await store.get_or_create_account()
    assert refreshed.balance_usd == account.balance_usd  # untouched


@pytest.mark.asyncio
async def test_red_blocked_category_never_asks_and_is_denied(pool):
    service, store, confirmations, _ = make_service(pool)
    account = await store.get_or_create_account()

    result = await service.propose_transaction(amount_usd=10.0, vendor="some-casino", category="gambling", purpose="???")

    assert result.approved is False
    assert result.policy_decision == PolicyColor.RED
    assert confirmations.list_pending() == []  # never asked — hard blocked

    refreshed = await store.get_or_create_account()
    assert refreshed.balance_usd == account.balance_usd


@pytest.mark.asyncio
async def test_exceeding_per_transaction_limit_requires_approval(pool):
    service, store, confirmations, _ = make_service(pool)
    account = await store.get_or_create_account()
    await store.update_limits(account.id, per_transaction_limit_usd=2.0, approved_categories=["hosting"])

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    result, _ = await asyncio.gather(
        service.propose_transaction(amount_usd=50.0, vendor="digitalocean", category="hosting", purpose="big upgrade"),
        reject_soon(),
    )
    assert result.policy_decision == PolicyColor.YELLOW
    assert result.approved is False


@pytest.mark.asyncio
async def test_weekly_spent_only_counts_executed_transactions(pool):
    service, store, confirmations, _ = make_service(pool)
    account = await store.get_or_create_account()
    await store.update_limits(account.id, approved_categories=["hosting"])

    await service.propose_transaction(amount_usd=5.0, vendor="digitalocean", category="hosting", purpose="a")

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    await asyncio.gather(
        service.propose_transaction(amount_usd=7.0, vendor="unknown-vendor", category="unknown_category", purpose="b"),
        reject_soon(),
    )

    weekly = await store.weekly_spent(account.id)
    assert weekly == 5.0  # only the GREEN, executed transaction counts


@pytest.mark.asyncio
async def test_weekly_limit_warning_fires_near_threshold(pool):
    service, store, confirmations, event_bus = make_service(pool)
    account = await store.get_or_create_account()
    await store.update_limits(account.id, weekly_limit_usd=10.0, per_transaction_limit_usd=100.0, approved_categories=["hosting"])

    warnings: list[Event] = []

    async def record(event: Event) -> None:
        warnings.append(event)

    event_bus.subscribe(record, EventType.WALLET_LIMIT_WARNING)

    result = await service.propose_transaction(amount_usd=9.0, vendor="digitalocean", category="hosting", purpose="a")
    assert result.approved is True
    assert len(warnings) == 1
