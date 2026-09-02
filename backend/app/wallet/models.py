"""The operational wallet (sections 40-45). CRITICAL: this is a real,
deterministic internal ledger with enforced limits — it is NOT connected
to any real bank/card/crypto rail. `WalletStore.execute()` only ever
adjusts the `wallet_accounts.balance_usd` column; there is no
`WalletExecutionAdapter` that moves real money, because no payment
processor credentials exist. See docs/DECISIONS.md ("The wallet is a real
ledger, not a real payment rail").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PolicyColor(str, Enum):
    GREEN = "GREEN"   # pre-approved, within limits -> auto (subject to autonomy level)
    YELLOW = "YELLOW"  # new vendor/category or near/over a limit -> ask
    RED = "RED"        # blocked category/vendor -> never execute, never ask


@dataclass
class WalletAccount:
    id: str
    name: str
    balance_usd: float
    weekly_limit_usd: float
    monthly_limit_usd: float
    per_transaction_limit_usd: float
    approval_threshold_usd: float
    approved_categories: list[str] = field(default_factory=list)
    blocked_categories: list[str] = field(default_factory=list)
    approved_vendors: list[str] = field(default_factory=list)


@dataclass
class WalletTransaction:
    id: str
    wallet_id: str
    amount_usd: float
    vendor: str
    category: str
    purpose: str
    policy_decision: PolicyColor
    status: str = "PROPOSED"  # PROPOSED | APPROVED | REJECTED | EXECUTED | FAILED
    task_id: str | None = None
    approval_id: str | None = None
    balance_after: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime | None = None


@dataclass
class WalletTransactionResult:
    approved: bool
    transaction_id: str
    reason: str
    balance_usd: float
    policy_decision: PolicyColor
