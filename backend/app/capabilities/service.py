"""CapabilityDiscoveryService: turns a capability gap into candidate
`Capability` rows (section 19/20). It only ever *proposes* — it never
installs, downloads, or executes anything discovered. "Never blindly
install unknown code" (section 20) means installation stays a manual/
future step gated by its own PolicyEngine approval, not part of this
service.
"""
from __future__ import annotations

import logging
import uuid

from app.capabilities.github_search import GitHubSearchClient
from app.capabilities.models import Capability, VerificationStatus
from app.capabilities.store import CapabilityStore
from app.events.bus import EventBus
from app.events.models import Event, EventType

logger = logging.getLogger(__name__)


class CapabilityDiscoveryService:
    def __init__(self, store: CapabilityStore, event_bus: EventBus, github_client: GitHubSearchClient | None = None) -> None:
        self._store = store
        self._event_bus = event_bus
        self._github = github_client or GitHubSearchClient()

    async def search_github(self, query: str, *, purpose: str, limit: int = 5) -> list[Capability]:
        results = await self._github.search_repositories(query, limit=limit)
        capabilities: list[Capability] = []

        for item in results:
            existing = await self._store.find_by_source(item["url"])
            if existing is not None:
                capabilities.append(existing)
                continue

            capability = await self._store.create(
                Capability(
                    id=str(uuid.uuid4()),
                    name=item["name"],
                    type="library",
                    purpose=purpose,
                    source=item["url"],
                    risk="unknown",
                    reversibility="reversible",
                    confidence=0.3,
                    verification_status=VerificationStatus.NOT_TESTED,
                    metadata={
                        "description": item["description"],
                        "stars": item["stars"],
                        "language": item["language"],
                        "license": item["license"],
                        "archived": item["archived"],
                    },
                )
            )
            await self._event_bus.publish(
                Event(type=EventType.CAPABILITY_DISCOVERED, payload={"capability_id": capability.id, "name": capability.name, "source": capability.source})
            )
            capabilities.append(capability)

        return capabilities

    async def mark_verified(self, capability_id: str, status: VerificationStatus) -> None:
        await self._store.set_verification_status(capability_id, status)

    # -- Phase 4: Capability Registry (additive) -----------------------
    # "search existing tools/capabilities... if not, design it" (section
    # 30/§28): the same `capabilities` table now also holds internally
    # registered capabilities (not just GitHub-discovered ones) and
    # composites built from them, so there is exactly one registry, never
    # a second capability store.

    async def register_internal(
        self, *, name: str, type: str, purpose: str, owner: str | None = None, metadata: dict | None = None
    ) -> Capability:
        """Register a capability that already exists in this codebase
        (a Tool, a workflow, anything not discovered externally) so it's
        searchable/composable through the same registry as discovered
        candidates. `source` is a stable internal identifier, not a URL."""
        existing = await self._store.find_by_source(f"internal:{name}")
        if existing is not None:
            return existing
        return await self._store.create(
            Capability(
                id=str(uuid.uuid4()),
                name=name,
                type=type,
                purpose=purpose,
                source=f"internal:{name}",
                owner=owner,
                verification_status=VerificationStatus.REAL,
                confidence=1.0,
                metadata=metadata or {},
            )
        )

    async def compose(self, *, name: str, purpose: str, component_ids: list[str], owner: str | None = None) -> Capability:
        """Register a composite capability from existing component
        capability ids (section 27: "capability composition"). Does not
        verify the components are compatible — that's the caller's job;
        this only records the composition."""
        return await self._store.create(
            Capability(
                id=str(uuid.uuid4()),
                name=name,
                type="composite",
                purpose=purpose,
                source=f"composite:{name}",
                owner=owner,
                composed_of=component_ids,
                verification_status=VerificationStatus.NOT_TESTED,
            )
        )

    async def search(self, query: str, *, limit: int = 20) -> list[Capability]:
        return await self._store.search(query, limit=limit)

    async def record_usage(self, capability_id: str, *, success: bool) -> None:
        await self._store.record_usage(capability_id, success=success)


class CapabilityUsageTracker:
    """Wildcard EventBus subscriber (same pattern as `AuditLogger` — no
    second event system, no change to plan_execution.py) that records
    usage stats for any registered capability whose `metadata.tool_name`
    matches the tool a `TOOL_COMPLETED` event reports on. A capability not
    yet linked to a tool_name is simply never matched — safe no-op."""

    def __init__(self, store: CapabilityStore, event_bus: EventBus) -> None:
        self._store = store
        self._event_bus = event_bus

    def attach(self) -> None:
        self._event_bus.subscribe(self._on_event, EventType.TOOL_COMPLETED)

    async def _on_event(self, event: Event) -> None:
        tool_name = event.payload.get("tool_name")
        if not tool_name:
            return
        capability_id = await self._resolve(tool_name)
        if capability_id is None:
            return
        await self._store.record_usage(capability_id, success=bool(event.payload.get("success")))

    async def _resolve(self, tool_name: str) -> str | None:
        # Rebuilt on every miss rather than cached indefinitely, since new
        # capabilities can be registered at any time; cheap relative to a
        # tool call itself.
        candidates = await self._store.list(limit=500)
        for c in candidates:
            if c.metadata.get("tool_name") == tool_name:
                return c.id
        return None
