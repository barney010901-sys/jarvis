"""Business engine service: ranked opportunities (section 49) and a
sustainability summary (section 51). Expenses come from `WalletStore`
(the wallet is the one expense ledger — see models.py).

The full SURVIVE -> SUSTAIN -> PROFIT -> SURPLUS -> QUALITY_OF_LIFE ->
REINVEST -> SCALE progression (section 51) is simplified here to four
observable stages (SURVIVE/SUSTAIN/PROFIT/SURPLUS) — the later three
stages describe what a user or Jarvis *chooses to do* with surplus, which
isn't something this deterministic summary can measure. See
docs/PHASE_3.md ("known limitations").
"""
from __future__ import annotations

from dataclasses import dataclass

from app.business.models import Opportunity
from app.business.scoring import score_opportunity
from app.business.store import BusinessStore
from app.wallet.store import WalletStore


@dataclass
class SustainabilitySummary:
    revenue_total_usd: float
    monthly_operating_cost_usd: float
    surplus_usd: float
    stage: str


class BusinessService:
    def __init__(self, store: BusinessStore, wallet_store: WalletStore | None = None) -> None:
        self._store = store
        self._wallet = wallet_store

    async def ranked_opportunities(self, limit: int = 20) -> list[tuple[Opportunity, float]]:
        opportunities = await self._store.list_opportunities(limit=limit)
        scored = [(o, score_opportunity(o)) for o in opportunities]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored

    async def sustainability_summary(self) -> SustainabilitySummary:
        revenue = await self._store.total_revenue()
        operating_cost = 0.0
        if self._wallet is not None:
            account = await self._wallet.get_or_create_account()
            operating_cost = await self._wallet.monthly_spent(account.id)
        surplus = revenue - operating_cost
        return SustainabilitySummary(
            revenue_total_usd=revenue, monthly_operating_cost_usd=operating_cost, surplus_usd=surplus, stage=self._stage(revenue, operating_cost, surplus)
        )

    @staticmethod
    def _stage(revenue: float, cost: float, surplus: float) -> str:
        if revenue <= 0 or surplus < 0:
            return "SURVIVE"
        if surplus == 0:
            return "SUSTAIN"
        if surplus <= cost:
            return "PROFIT"
        return "SURPLUS"
