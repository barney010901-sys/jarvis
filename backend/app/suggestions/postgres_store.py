from __future__ import annotations

import uuid

import asyncpg

from app.suggestions.interface import SuggestionQueue
from app.suggestions.models import Priority, Suggestion, SuggestionStatus

_PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}


def _row_to_suggestion(row: asyncpg.Record) -> Suggestion:
    return Suggestion(
        id=str(row["id"]),
        priority=Priority(row["priority"]),
        title=row["title"],
        reason=row["reason"],
        relevance=row["relevance"],
        source=row["source"],
        related_project=row["related_project"],
        related_goal=str(row["related_goal"]) if row["related_goal"] else None,
        confidence=row["confidence"],
        status=SuggestionStatus(row["status"]),
        created_at=row["created_at"],
    )


class PostgresSuggestionQueue(SuggestionQueue):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def enqueue(self, suggestion: Suggestion) -> Suggestion:
        record_id = suggestion.id or str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO suggestions (
                    id, priority, title, reason, relevance, related_project, related_goal,
                    source, confidence, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
                """,
                record_id,
                suggestion.priority.value,
                suggestion.title,
                suggestion.reason,
                suggestion.relevance,
                suggestion.related_project,
                suggestion.related_goal,
                suggestion.source,
                suggestion.confidence,
                suggestion.status.value,
            )
        return _row_to_suggestion(row)

    async def list_pending(self, min_priority: Priority | None = None, limit: int = 20) -> list[Suggestion]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM suggestions WHERE status = 'PENDING' ORDER BY created_at DESC LIMIT $1", limit
            )
        results = [_row_to_suggestion(r) for r in rows]
        if min_priority is not None:
            threshold = _PRIORITY_RANK[min_priority]
            results = [s for s in results if _PRIORITY_RANK[s.priority] >= threshold]
        return results

    async def set_status(self, suggestion_id: str, status: SuggestionStatus) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE suggestions SET status = $2 WHERE id = $1", suggestion_id, status.value)
