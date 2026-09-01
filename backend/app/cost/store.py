"""Where UsageRecords are persisted. Two implementations behind the same
interface, same pattern as memory/knowledge/profile: Postgres when
available, in-memory otherwise — CostTracker doesn't care which.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import asyncpg

from app.cost.models import UsageRecord


class UsageStore(ABC):
    @abstractmethod
    async def record(self, usage: UsageRecord) -> None: ...

    @abstractmethod
    async def total_cost_since(self, since: datetime) -> float: ...

    @abstractmethod
    async def count_since(self, since: datetime) -> int: ...


class InMemoryUsageStore(UsageStore):
    def __init__(self) -> None:
        self._records: list[UsageRecord] = []

    async def record(self, usage: UsageRecord) -> None:
        self._records.append(usage)

    async def total_cost_since(self, since: datetime) -> float:
        return sum(r.estimated_cost_usd for r in self._records if r.created_at >= since)

    async def count_since(self, since: datetime) -> int:
        return sum(1 for r in self._records if r.created_at >= since)


class PostgresUsageStore(UsageStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(self, usage: UsageRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO token_usage (
                    task_id, provider, model, role, input_tokens, output_tokens,
                    estimated_cost_usd, served_from_cache, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                usage.task_id,
                usage.provider,
                usage.model,
                usage.role,
                usage.input_tokens,
                usage.output_tokens,
                usage.estimated_cost_usd,
                usage.served_from_cache,
                usage.created_at,
            )

    async def total_cost_since(self, since: datetime) -> float:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM token_usage WHERE created_at >= $1", since
            )
        return float(value)

    async def count_since(self, since: datetime) -> int:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval("SELECT COUNT(*) FROM token_usage WHERE created_at >= $1", since)
        return int(value)


def start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
