"""Token/cost tracking + budget hierarchy (2E).

The cost hierarchy itself — "prefer local logic / cache / database /
memory / knowledge / cheap model over the primary model" — is enforced by
the orchestrator (it asks KnowledgeService for a high-confidence answer
before ever calling a provider; see ClaudeOrchestrator). CostTracker's job
is narrower: record what was actually spent, answer "are we near/over
budget", and keep light in-process counters for the things 2E asks to
observe (cache/memory/knowledge hits, avoidable requests) so they're
visible without re-deriving them from the event log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent.provider.base import ProviderResult
from agent.provider.costs import estimate_cost
from app.cost.models import BudgetState, BudgetStatus, UsageRecord
from app.cost.store import UsageStore, start_of_today_utc

logger = logging.getLogger(__name__)

NEAR_LIMIT_FRACTION = 0.8


@dataclass
class UsageCounters:
    """Process-lifetime counters — reset on restart. Not the system of
    record (token_usage / audit_log tables are); this is for quick
    observability (e.g. a debug endpoint), not billing or history."""

    requests_to_primary: int = 0
    requests_to_fast: int = 0
    requests_to_fallback: int = 0
    cache_hits: int = 0
    memory_hits: int = 0
    knowledge_hits: int = 0
    avoidable_requests_avoided: int = 0


class CostTracker:
    def __init__(self, store: UsageStore, *, daily_budget_usd: float) -> None:
        self._store = store
        self._daily_budget_usd = daily_budget_usd
        self.counters = UsageCounters()

    async def record_provider_usage(
        self,
        result: ProviderResult,
        *,
        provider: str,
        role: str,
        task_id: str | None = None,
    ) -> UsageRecord:
        cost = estimate_cost(result.model, result.usage.input_tokens, result.usage.output_tokens)
        usage = UsageRecord(
            provider=provider,
            model=result.model,
            role=role,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            estimated_cost_usd=cost,
            task_id=task_id,
        )
        await self._store.record(usage)
        if role == "fast":
            self.counters.requests_to_fast += 1
        elif role == "fallback":
            self.counters.requests_to_fallback += 1
        else:
            self.counters.requests_to_primary += 1
        return usage

    async def record_avoided_request(self, *, task_id: str | None, reason: str) -> None:
        """Called when the orchestrator skips calling a provider entirely
        because local logic/knowledge already had a sufficiently-confident
        answer — the concrete realization of 2E's "avoid asking Claude
        something JARVIS already knows" for observability."""
        self.counters.avoidable_requests_avoided += 1
        self.counters.knowledge_hits += 1
        await self._store.record(
            UsageRecord(provider="none", model="none", role="skipped", task_id=task_id, served_from_cache=True)
        )
        logger.info("Avoided a provider call for task %s: %s", task_id, reason)

    def record_memory_hit(self) -> None:
        self.counters.memory_hits += 1

    async def budget_status(self) -> BudgetStatus:
        spent = await self._store.total_cost_since(start_of_today_utc())
        if self._daily_budget_usd <= 0:
            state = BudgetState.OK
        elif spent >= self._daily_budget_usd:
            state = BudgetState.EXCEEDED
        elif spent >= self._daily_budget_usd * NEAR_LIMIT_FRACTION:
            state = BudgetState.NEAR_LIMIT
        else:
            state = BudgetState.OK
        return BudgetStatus(state=state, spent_today_usd=spent, budget_usd=self._daily_budget_usd)
