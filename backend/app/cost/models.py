from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


@dataclass
class UsageRecord:
    provider: str
    model: str
    role: str  # "fast" | "primary" | "fallback"
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    served_from_cache: bool = False
    task_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BudgetState(str, Enum):
    OK = "OK"
    NEAR_LIMIT = "NEAR_LIMIT"
    EXCEEDED = "EXCEEDED"


@dataclass
class BudgetStatus:
    state: BudgetState
    spent_today_usd: float
    budget_usd: float

    @property
    def fraction_used(self) -> float:
        return self.spent_today_usd / self.budget_usd if self.budget_usd > 0 else 0.0
