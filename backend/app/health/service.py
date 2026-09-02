"""Self-diagnostics (section 55/63) — live checks where a live check is
meaningful, honest static status where it isn't (no MCP registry exists
yet, no device is attached to this backend, etc.). Never reports HEALTHY
for something not actually verified this cycle.
"""
from __future__ import annotations

import asyncpg
import httpx

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.health.models import ComponentHealth, HealthStatus
from app.tools.registry import ToolRegistry

GITHUB_PROBE_URL = "https://api.github.com"


class HealthService:
    def __init__(
        self,
        *,
        pool: asyncpg.Pool | None,
        claude_configured: bool,
        event_bus: EventBus,
        tool_registry: ToolRegistry | None = None,
        local_model_base_url: str | None = None,
    ) -> None:
        self._pool = pool
        self._claude_configured = claude_configured
        self._event_bus = event_bus
        self._tool_registry = tool_registry
        self._local_model_base_url = local_model_base_url

    async def check_all(self) -> list[ComponentHealth]:
        checks = [
            ComponentHealth("backend", HealthStatus.HEALTHY, "process is running"),
            await self._check_database(),
            self._check_claude(),
            await self._check_local_model(),
            ComponentHealth("event_bus", HealthStatus.HEALTHY, "in-process bus active"),
            self._check_tools(),
            await self._check_github(),
            # Not implemented / not attached in this phase — see docs/PHASE_3.md.
            ComponentHealth("mcp", HealthStatus.NOT_CONFIGURED, "no MCP registry integration yet (interface only)"),
            ComponentHealth("browser", HealthStatus.NOT_CONFIGURED, "no browser automation backend configured"),
            ComponentHealth("coding_agent", HealthStatus.NOT_CONFIGURED, "CodingAgentInterface has no implementation (by design — see agent/coding_agent)"),
            ComponentHealth("android", HealthStatus.NOT_TESTED, "no physical device/emulator attached to this backend"),
            ComponentHealth("stt", HealthStatus.NOT_CONFIGURED, "no speech-to-text provider configured"),
            ComponentHealth("tts", HealthStatus.NOT_CONFIGURED, "client-side (expo-speech); not verifiable from the backend"),
        ]

        for check in checks:
            if check.status in (HealthStatus.WARNING, HealthStatus.ERROR):
                await self._event_bus.publish(
                    Event(type=EventType.SYSTEM_HEALTH_WARNING, payload={"component": check.component, "status": check.status.value, "detail": check.detail})
                )
        return checks

    async def _check_database(self) -> ComponentHealth:
        if self._pool is None:
            return ComponentHealth("database", HealthStatus.NOT_CONFIGURED, "JARVIS_USE_POSTGRES is false or unset")
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return ComponentHealth("database", HealthStatus.HEALTHY, "PostgreSQL reachable")
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth("database", HealthStatus.ERROR, f"PostgreSQL unreachable: {exc}")

    def _check_claude(self) -> ComponentHealth:
        if not self._claude_configured:
            return ComponentHealth("claude", HealthStatus.NOT_CONFIGURED, "ANTHROPIC_API_KEY not set or JARVIS_USE_CLAUDE=false")
        return ComponentHealth("claude", HealthStatus.NOT_TESTED, "configured; live API reachability not verified this cycle (no request made)")

    async def _check_local_model(self) -> ComponentHealth:
        if not self._local_model_base_url:
            return ComponentHealth("local_model", HealthStatus.NOT_CONFIGURED, "JARVIS_USE_LOCAL_MODEL is false — not attempted")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._local_model_base_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                return ComponentHealth("local_model", HealthStatus.HEALTHY, f"Ollama reachable at {self._local_model_base_url}")
            return ComponentHealth("local_model", HealthStatus.ERROR, f"Ollama returned HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            return ComponentHealth(
                "local_model", HealthStatus.ERROR, f"Ollama unreachable at {self._local_model_base_url} — is `ollama serve` running? ({exc})"
            )

    def _check_tools(self) -> ComponentHealth:
        if self._tool_registry is None:
            return ComponentHealth("tools", HealthStatus.NOT_CONFIGURED, "no tool registry wired in")
        count = len(self._tool_registry.list())
        return ComponentHealth("tools", HealthStatus.HEALTHY, f"{count} tool(s) registered")

    async def _check_github(self) -> ComponentHealth:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(GITHUB_PROBE_URL)
            return ComponentHealth("github", HealthStatus.HEALTHY, f"reachable (HTTP {response.status_code})")
        except httpx.HTTPError as exc:
            return ComponentHealth("github", HealthStatus.NOT_TESTED, f"unreachable from this environment: {exc}")
