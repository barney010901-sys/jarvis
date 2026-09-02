"""ResourceBudgetService: opt-in budget checks for autonomous work ("Work
autonomously for 6 hours, within a €20 API budget" — Phase 4 "Autonomy
Budget"). Nothing in Phase 1-3 is required to call this; it's a new,
additive control a caller can consult before spending time/money/API
calls/actions on an autonomous objective.

Not a replacement for Phase 3's wallet limits — the wallet's own
GREEN/YELLOW/RED classification remains the hard financial control for
real spend proposals (`app.wallet.service.WalletService`). This is a
lighter-weight, generic budget for the *other* resources (time, API call
count, action count) autonomous work consumes, plus an optional money
budget for tracking-only use cases that don't go through the wallet at
all (e.g. "don't let research alone cost more than $2 in model calls").

`consume()` is check-then-update, not a single atomic SQL statement —
honest limitation under concurrent callers for the same scope+kind; fine
for a single-process, single-owner deployment (matches every other
concurrency assumption already documented for Phase 1-3), not something
to rely on unmodified for multi-worker deployment.
"""
from __future__ import annotations

from app.autonomy.budget_models import BudgetKind, ResourceBudget
from app.autonomy.budget_store import ResourceBudgetStore


class BudgetExceeded(Exception):
    def __init__(self, budget: ResourceBudget, requested: float) -> None:
        self.budget = budget
        self.requested = requested
        super().__init__(
            f"budget exceeded: scope={budget.scope!r} kind={budget.kind.value!r} "
            f"remaining={budget.remaining} requested={requested}"
        )


class ResourceBudgetService:
    def __init__(self, store: ResourceBudgetStore) -> None:
        self._store = store

    async def set_limit(self, scope: str, kind: BudgetKind, limit_amount: float) -> ResourceBudget:
        return await self._store.get_or_create(scope, kind, limit_amount=limit_amount)

    async def remaining(self, scope: str, kind: BudgetKind) -> float | None:
        budget = await self._store.get_current(scope, kind)
        return budget.remaining if budget else None

    async def consume(self, scope: str, kind: BudgetKind, amount: float) -> ResourceBudget | None:
        """Raise `BudgetExceeded` (without recording usage) if `amount`
        would push used_amount past the limit; otherwise record it and
        return the updated budget. A scope/kind with no configured budget
        is treated as unlimited — returns `None` and records nothing, since
        Postgres `NUMERIC` has no infinity to store a limit as. Call
        `set_limit` first for anything that should actually be capped and
        tracked."""
        budget = await self._store.get_current(scope, kind)
        if budget is None:
            return None
        if budget.used_amount + amount > budget.limit_amount:
            raise BudgetExceeded(budget, amount)
        return await self._store.record_usage(scope, kind, amount)
