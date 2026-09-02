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
