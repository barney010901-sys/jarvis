"""REAL integration tests for the Phase 4 Capability Registry additions
to the existing Phase 3 `capabilities` table/service (register_internal,
compose, search, usage tracking) — see docs/PHASE_4_AUDIT.md §17(c).
"""
from __future__ import annotations

import os

import asyncpg
import pytest

from app.capabilities.models import VerificationStatus
from app.capabilities.service import CapabilityDiscoveryService, CapabilityUsageTracker
from app.capabilities.store import CapabilityStore
from app.events.bus import EventBus
from app.events.models import Event, EventType

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
        await conn.execute("TRUNCATE capabilities")
    await p.close()


@pytest.mark.asyncio
async def test_register_internal_is_idempotent_by_source(pool):
    store = CapabilityStore(pool)
    event_bus = EventBus()
    service = CapabilityDiscoveryService(store, event_bus)

    first = await service.register_internal(name="wallet.propose_transaction", type="tool", purpose="propose a spend")
    second = await service.register_internal(name="wallet.propose_transaction", type="tool", purpose="propose a spend (again)")

    assert first.id == second.id
    assert first.verification_status == VerificationStatus.REAL


@pytest.mark.asyncio
async def test_compose_records_component_ids(pool):
    store = CapabilityStore(pool)
    event_bus = EventBus()
    service = CapabilityDiscoveryService(store, event_bus)

    a = await service.register_internal(name="research", type="tool", purpose="research a topic")
    b = await service.register_internal(name="summarize", type="tool", purpose="summarize text")

    composite = await service.compose(name="research_and_summarize", purpose="research then summarize", component_ids=[a.id, b.id])

    assert composite.type == "composite"
    assert set(composite.composed_of) == {a.id, b.id}


@pytest.mark.asyncio
async def test_search_matches_name_and_purpose(pool):
    store = CapabilityStore(pool)
    event_bus = EventBus()
    service = CapabilityDiscoveryService(store, event_bus)

    await service.register_internal(name="client_acquisition_helper", type="tool", purpose="find new clients")
    await service.register_internal(name="unrelated_thing", type="tool", purpose="does something else entirely")

    results = await service.search("client")
    names = {r.name for r in results}
    assert "client_acquisition_helper" in names
    assert "unrelated_thing" not in names


@pytest.mark.asyncio
async def test_record_usage_updates_counts_and_observed_success_rate(pool):
    store = CapabilityStore(pool)
    event_bus = EventBus()
    service = CapabilityDiscoveryService(store, event_bus)

    cap = await service.register_internal(name="flaky_tool", type="tool", purpose="sometimes fails")
    await service.record_usage(cap.id, success=True)
    await service.record_usage(cap.id, success=False)

    updated = await store.get(cap.id)
    assert updated.usage_count == 2
    assert updated.success_count == 1
    assert updated.success_rate_observed == 0.5


@pytest.mark.asyncio
async def test_usage_tracker_updates_capability_from_tool_completed_event(pool):
    store = CapabilityStore(pool)
    event_bus = EventBus()
    service = CapabilityDiscoveryService(store, event_bus)

    cap = await service.register_internal(
        name="wallet.propose_transaction", type="tool", purpose="propose a spend", metadata={"tool_name": "wallet.propose_transaction"}
    )

    tracker = CapabilityUsageTracker(store, event_bus)
    tracker.attach()

    await event_bus.publish(Event(type=EventType.TOOL_COMPLETED, payload={"tool_name": "wallet.propose_transaction", "success": True}))
    await event_bus.publish(Event(type=EventType.TOOL_COMPLETED, payload={"tool_name": "some.other.tool", "success": False}))

    updated = await store.get(cap.id)
    assert updated.usage_count == 1  # only the matching tool_name counted
    assert updated.success_count == 1
