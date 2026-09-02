from __future__ import annotations

import uuid

import asyncpg

from app.autonomy.budget_models import BudgetKind, ResourceBudget


def _row_to_budget(row: asyncpg.Record) -> ResourceBudget:
    return ResourceBudget(
        id=str(row["id"]),
        scope=row["scope"],
        kind=BudgetKind(row["kind"]),
        limit_amount=float(row["limit_amount"]),
        used_amount=float(row["used_amount"]),
        period_start=row["period_start"],
        period_end=row["period_end"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ResourceBudgetStore:
    """Only one "current" (period_end IS NULL) budget row per (scope,
    kind) is used by `get_or_create`/`record_usage` in this increment —
    periodic reset/rollover is a scheduler-dependent feature (see
    docs/PHASE_4_AUDIT.md §10/§16) left for a later phase; nothing here
    prevents adding it without changing this schema."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_current(self, scope: str, kind: BudgetKind) -> ResourceBudget | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM resource_budgets WHERE scope = $1 AND kind = $2 AND period_end IS NULL", scope, kind.value
            )
        return _row_to_budget(row) if row else None

    async def get_or_create(self, scope: str, kind: BudgetKind, *, limit_amount: float) -> ResourceBudget:
        existing = await self.get_current(scope, kind)
        if existing is not None:
            return existing
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO resource_budgets (id, scope, kind, limit_amount)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (scope, kind, period_start) DO UPDATE SET limit_amount = EXCLUDED.limit_amount
                RETURNING *
                """,
                str(uuid.uuid4()), scope, kind.value, limit_amount,
            )
        return _row_to_budget(row)

    async def record_usage(self, scope: str, kind: BudgetKind, amount: float) -> ResourceBudget:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE resource_budgets SET used_amount = used_amount + $3, updated_at = now()
                WHERE scope = $1 AND kind = $2 AND period_end IS NULL
                RETURNING *
                """,
                scope, kind.value, amount,
            )
        if row is None:
            raise ValueError(f"no current budget for scope={scope!r} kind={kind.value!r} — call get_or_create first")
        return _row_to_budget(row)
