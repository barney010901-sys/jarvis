"""PostgreSQL-backed implementations of the same three interfaces defined
in `store.py` (`WorkingMemory`, `ShortTermMemory`, `LongTermMemory`).

This is the Phase 2 realization of the Phase 1 decision in
docs/DECISIONS.md ("In-memory MemoryStore instead of a live PostgreSQL
connection") — same interfaces, same call sites, different backing store.
Tables are defined in `memory/schema.sql`.

Values stored in `working_memory.value` (JSONB) must be JSON-serializable —
see docs/DECISIONS.md ("Working memory stores plain data, not live
objects") for why callers pass dicts/lists rather than dataclass instances.
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.memory.store import (
    ConversationTurn,
    LongTermFact,
    LongTermMemory,
    ShortTermMemory,
    WorkingMemory,
)


class PostgresWorkingMemory(WorkingMemory):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def set(self, task_id: str, key: str, value: Any) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO working_memory (task_id, key, value, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (task_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                """,
                task_id,
                key,
                json.dumps(value),
            )

    async def get(self, task_id: str, key: str) -> Any | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM working_memory WHERE task_id = $1 AND key = $2", task_id, key
            )
        return json.loads(row["value"]) if row else None

    async def clear(self, task_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM working_memory WHERE task_id = $1", task_id)


class PostgresShortTermMemory(ShortTermMemory):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, session_id: str, turn: ConversationTurn) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO short_term_memory (session_id, role, content, created_at) VALUES ($1, $2, $3, $4)",
                session_id,
                turn.role,
                turn.content,
                turn.timestamp,
            )

    async def recent(self, session_id: str, limit: int = 20) -> list[ConversationTurn]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, created_at FROM short_term_memory
                WHERE session_id = $1 ORDER BY created_at DESC LIMIT $2
                """,
                session_id,
                limit,
            )
        turns = [ConversationTurn(role=r["role"], content=r["content"], timestamp=r["created_at"]) for r in rows]
        return list(reversed(turns))

    async def prune(self, session_id: str, keep_last: int) -> int:
        """Expiration/archiving (2C): delete all but the most recent
        `keep_last` turns for a session. Not called automatically — wire
        this to a periodic job when a real deployment needs it (see
        memory/README.md)."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM short_term_memory
                WHERE session_id = $1 AND id NOT IN (
                    SELECT id FROM short_term_memory WHERE session_id = $1 ORDER BY created_at DESC LIMIT $2
                )
                """,
                session_id,
                keep_last,
            )
        return int(result.split()[-1]) if result else 0


class PostgresLongTermMemory(LongTermMemory):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, fact: LongTermFact) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO long_term_memory (id, project, content, tags, created_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, tags = EXCLUDED.tags
                """,
                fact.id,
                fact.project,
                fact.content,
                fact.tags,
                fact.created_at,
            )

    async def search(self, project: str, query: str, limit: int = 10) -> list[LongTermFact]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, project, content, tags, created_at FROM long_term_memory
                WHERE project = $1 AND content ILIKE $2
                ORDER BY created_at DESC LIMIT $3
                """,
                project,
                f"%{query}%",
                limit,
            )
        return [
            LongTermFact(id=r["id"], project=r["project"], content=r["content"], tags=list(r["tags"]), created_at=r["created_at"])
            for r in rows
        ]

    async def delete(self, fact_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM long_term_memory WHERE id = $1", fact_id)
