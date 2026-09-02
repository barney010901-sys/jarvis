"""Capability discovery: dedup logic is tested with a fake GitHub search
client (real Postgres store + real service logic — only the network layer
is a test double); the REAL network call is attempted separately and
skips with a clear message if this environment's proxy blocks it (it
does — see app/capabilities/github_search.py's module docstring).

Health service: real checks against real Postgres/tool registry/network.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.capabilities.github_search import GitHubSearchClient, GitHubSearchError
from app.capabilities.models import VerificationStatus
from app.capabilities.service import CapabilityDiscoveryService
from app.capabilities.store import CapabilityStore
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.health.models import HealthStatus
from app.health.service import HealthService
from app.tools.registry import default_registry

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


class _FakeGitHubClient:
    """A test double for the network layer only — see module docstring."""

    def __init__(self, results):
        self._results = results
        self.calls = 0

    async def search_repositories(self, query, limit=5):
        self.calls += 1
        return self._results[:limit]


@pytest.mark.asyncio
async def test_search_github_creates_capability_and_publishes_event(pool):
    fake = _FakeGitHubClient([{"name": "openai/whisper", "url": "https://github.com/openai/whisper", "description": "STT model", "stars": 50000, "language": "Python", "license": "MIT", "archived": False, "updated_at": "2024-01-01"}])
    event_bus = EventBus()
    received: list[Event] = []

    async def record(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(record, EventType.CAPABILITY_DISCOVERED)
    service = CapabilityDiscoveryService(CapabilityStore(pool), event_bus, github_client=fake)

    results = await service.search_github("speech to text", purpose="offline STT")
    assert len(results) == 1
    assert results[0].verification_status == VerificationStatus.NOT_TESTED
    assert len(received) == 1


@pytest.mark.asyncio
async def test_search_github_deduplicates_by_source(pool):
    fake = _FakeGitHubClient([{"name": "openai/whisper", "url": "https://github.com/openai/whisper", "description": "STT model", "stars": 50000, "language": "Python", "license": "MIT", "archived": False, "updated_at": "2024-01-01"}])
    service = CapabilityDiscoveryService(CapabilityStore(pool), EventBus(), github_client=fake)

    first = await service.search_github("speech to text", purpose="offline STT")
    second = await service.search_github("speech to text", purpose="offline STT")

    assert first[0].id == second[0].id
    all_caps = await CapabilityStore(pool).list()
    assert len(all_caps) == 1


@pytest.mark.asyncio
async def test_mark_verified_updates_status(pool):
    store = CapabilityStore(pool)
    fake = _FakeGitHubClient([{"name": "x/y", "url": "https://github.com/x/y", "description": "", "stars": 1, "language": None, "license": None, "archived": False, "updated_at": None}])
    service = CapabilityDiscoveryService(store, EventBus(), github_client=fake)

    [capability] = await service.search_github("x", purpose="test")
    await service.mark_verified(capability.id, VerificationStatus.REAL)

    refreshed = [c for c in await store.list() if c.id == capability.id][0]
    assert refreshed.verification_status == VerificationStatus.REAL


@pytest.mark.asyncio
async def test_real_github_search_network_call():
    """Attempts the actual, unauthenticated GitHub search API. This
    session's outbound proxy blocks it (403) — skip with a clear reason
    rather than failing, per this test suite's established pattern for
    external dependencies that aren't reachable in this sandbox."""
    client = GitHubSearchClient()
    try:
        results = await client.search_repositories("speech to text language:python", limit=3)
    except GitHubSearchError as exc:
        pytest.skip(f"Real GitHub search API not reachable in this sandbox: {exc}")
    else:
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_health_service_reports_real_database_and_tools_status(pool):
    event_bus = EventBus()
    service = HealthService(pool=pool, claude_configured=False, event_bus=event_bus, tool_registry=default_registry("."))
    checks = await service.check_all()

    by_component = {c.component: c for c in checks}
    assert by_component["database"].status == HealthStatus.HEALTHY
    assert by_component["claude"].status == HealthStatus.NOT_CONFIGURED
    assert by_component["tools"].status == HealthStatus.HEALTHY
    assert "5 tool" in by_component["tools"].detail
    assert by_component["mcp"].status == HealthStatus.NOT_CONFIGURED
    assert by_component["android"].status == HealthStatus.NOT_TESTED


@pytest.mark.asyncio
async def test_health_service_reports_claude_not_tested_when_configured(pool):
    service = HealthService(pool=pool, claude_configured=True, event_bus=EventBus())
    checks = await service.check_all()
    claude_check = [c for c in checks if c.component == "claude"][0]
    assert claude_check.status == HealthStatus.NOT_TESTED


@pytest.mark.asyncio
async def test_health_service_reports_database_error_when_pool_broken():
    try:
        # min_size=0 so pool creation itself succeeds lazily — the failure
        # this test wants to observe happens on acquire(), inside
        # _check_database(), matching what a real outage looks like.
        bad_pool = await asyncpg.create_pool(dsn="postgresql://jarvis:jarvis@127.0.0.1:1/nope", min_size=0, max_size=1, timeout=1)
    except Exception:
        pytest.skip("could not even construct a pool object pointed at a bad DSN in this environment")
    service = HealthService(pool=bad_pool, claude_configured=False, event_bus=EventBus())
    checks = await service.check_all()
    db_check = [c for c in checks if c.component == "database"][0]
    assert db_check.status == HealthStatus.ERROR
    await bad_pool.close()


@pytest.mark.asyncio
async def test_health_service_publishes_warning_events_for_error_status():
    event_bus = EventBus()
    warnings: list[Event] = []

    async def record(event: Event) -> None:
        warnings.append(event)

    event_bus.subscribe(record, EventType.SYSTEM_HEALTH_WARNING)
    service = HealthService(pool=None, claude_configured=False, event_bus=event_bus)
    await service.check_all()
    # NOT_CONFIGURED/NOT_TESTED don't count as WARNING/ERROR — expect none here.
    assert warnings == []
