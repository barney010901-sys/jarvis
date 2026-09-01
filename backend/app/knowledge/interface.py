from __future__ import annotations

from abc import ABC, abstractmethod

from app.knowledge.models import KnowledgeCategory, KnowledgeRecord, KnowledgeStatus


class KnowledgeStore(ABC):
    @abstractmethod
    async def create(self, record: KnowledgeRecord) -> KnowledgeRecord: ...

    @abstractmethod
    async def get(self, knowledge_id: str) -> KnowledgeRecord | None: ...

    @abstractmethod
    async def search(
        self,
        *,
        project: str | None,
        query: str,
        category: KnowledgeCategory | None = None,
        status: KnowledgeStatus | None = KnowledgeStatus.ACTIVE,
        limit: int = 10,
    ) -> list[KnowledgeRecord]:
        """Text search (title/content). Phase 2 uses trigram similarity, not
        embeddings — see docs/DECISIONS.md ("Knowledge similarity without
        an embeddings API")."""

    @abstractmethod
    async def update(self, record: KnowledgeRecord) -> KnowledgeRecord: ...

    @abstractmethod
    async def set_status(self, knowledge_id: str, status: KnowledgeStatus) -> None: ...

    @abstractmethod
    async def record_usage(self, knowledge_id: str) -> None:
        """Bump usage_count and last_used_at — called when a record is
        actually included in a Claude request's context, not merely
        returned by search()."""

    @abstractmethod
    async def adjust_confidence(self, knowledge_id: str, delta: float) -> float:
        """Clamped to [0, 1]. Returns the new confidence."""

    @abstractmethod
    async def list_by_project(
        self, project: str | None, category: KnowledgeCategory | None = None, limit: int = 50
    ) -> list[KnowledgeRecord]: ...
