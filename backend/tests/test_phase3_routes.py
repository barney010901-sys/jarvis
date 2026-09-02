"""REAL integration test of the actual FastAPI app + lifespan (not just
the service layer) — verifies the Phase 3 REST surface responds correctly
both when domain services aren't configured (503, not a crash or fake
200) and for the always-available dashboard/health endpoints.

This is the one test module that boots the real `app.main:app` (via
TestClient's `with` block, which runs the FastAPI lifespan) rather than
constructing services directly — see app/deps.py's module docstring for
why every other test avoids this. `reset_state()` before and after keeps
it from leaking process-wide state into other test modules.
"""
from __future__ import annotations

import asyncio
import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

import app.deps as deps

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


def _postgres_reachable(dsn: str) -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(dsn=dsn, timeout=3)
        except Exception:
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


@pytest.fixture
def client():
    if not _postgres_reachable(TEST_DATABASE_URL):
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")

    # This test's own env — deliberately NOT touching ANTHROPIC_API_KEY, so
    # it stays whatever conftest.py set (empty) and claude_ready is False:
    # exercising the "Postgres yes, Claude no" branch honestly rather than
    # faking a configured Claude stack.
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    deps.reset_state()
    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    try:
        with TestClient(app) as c:
            c.headers["Authorization"] = "Bearer " + os.environ["JARVIS_API_TOKEN"]
            yield c
    finally:
        deps.reset_state()
        get_settings.cache_clear()


def test_dashboard_reports_real_health_and_empty_optional_sections(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.json()

    components = {c["component"]: c["status"] for c in body["system_health"]}
    assert components["backend"] == "HEALTHY"
    assert components["database"] == "HEALTHY"
    assert components["claude"] == "NOT_CONFIGURED"  # no ANTHROPIC_API_KEY in this test env
    # Postgres-but-not-Claude -> Phase 3 domain services are absent (see
    # docs/DECISIONS.md, "Phase 3 domains share Phase 2's one-fallback-axis rule").
    assert body["suggestions"] == []
    assert body["pending_approvals"] == []
    assert body["wallet"] is None
    assert body["business"] is None


def test_system_health_endpoint(client):
    response = client.get("/system/health")
    assert response.status_code == 200
    components = {c["component"]: c["status"] for c in response.json()["components"]}
    assert components["database"] == "HEALTHY"
    assert components["tools"] == "HEALTHY"


@pytest.mark.parametrize(
    "path",
    ["/wallet", "/business/summary", "/business/opportunities", "/settings/autonomy", "/capabilities", "/contacts"],
)
def test_domain_endpoints_return_503_when_not_configured(client, path):
    response = client.get(path)
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_dashboard_requires_auth():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    deps.reset_state()
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    try:
        with TestClient(app) as c:
            response = c.get("/dashboard")  # no Authorization header set
        assert response.status_code in (401, 403)
    finally:
        deps.reset_state()
        get_settings.cache_clear()
