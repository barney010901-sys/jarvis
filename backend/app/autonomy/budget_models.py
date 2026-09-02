"""Resource budgets (Phase 4 "Autonomy Budget" / "Resource Management").
A scope ("global", or "objective:<id>" once objectives exist as a Phase 4
concept) x kind (money_usd | api_calls | actions | time_seconds) limit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class BudgetKind(str, Enum):
    MONEY_USD = "money_usd"
    API_CALLS = "api_calls"
    ACTIONS = "actions"
    TIME_SECONDS = "time_seconds"


@dataclass
class ResourceBudget:
    id: str
    scope: str
    kind: BudgetKind
    limit_amount: float
    used_amount: float = 0.0
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def remaining(self) -> float:
        return self.limit_amount - self.used_amount

    @property
    def exhausted(self) -> bool:
        return self.used_amount >= self.limit_amount

    def __post_init__(self) -> None:
        if self.period_start is None:
            self.period_start = datetime.now(timezone.utc)
