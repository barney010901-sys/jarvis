from __future__ import annotations

from abc import ABC, abstractmethod

from app.suggestions.models import Priority, Suggestion, SuggestionStatus


class SuggestionQueue(ABC):
    @abstractmethod
    async def enqueue(self, suggestion: Suggestion) -> Suggestion: ...

    @abstractmethod
    async def list_pending(self, min_priority: Priority | None = None, limit: int = 20) -> list[Suggestion]: ...

    @abstractmethod
    async def set_status(self, suggestion_id: str, status: SuggestionStatus) -> None: ...
