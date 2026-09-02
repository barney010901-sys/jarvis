"""Business engine records (sections 46-49). Expenses are NOT modeled here
— they're wallet_transactions (see app/wallet), so cost tracking has one
ledger, not two.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

CUSTOMER_STAGES = (
    "LEAD", "CONTACTED", "INTERESTED", "QUALIFIED", "PROPOSAL",
    "APPROVED", "ACTIVE", "DELIVERED", "PAID", "REPEAT",
)
EXPERIMENT_STAGES = (
    "IDEA", "HYPOTHESIS", "MVP", "TEST", "OUTREACH", "FEEDBACK",
    "FIRST_CUSTOMER", "DELIVERY", "PAYMENT", "EVALUATION",
)


@dataclass
class BusinessIdea:
    id: str
    title: str
    hypothesis: str = ""
    target_customer: str = ""
    status: str = "IDEA"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Customer:
    id: str
    name: str
    contact_id: str | None = None
    stage: str = "LEAD"
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Opportunity:
    id: str
    title: str
    description: str = ""
    expected_value: float = 0.0
    probability: float = 0.5
    speed: float = 0.5
    scalability: float = 0.5
    user_advantage: float = 0.5
    long_term_value: float = 0.5
    legal_risk: float = 0.0
    financial_risk: float = 0.0
    reputational_risk: float = 0.0
    execution_risk: float = 0.0
    status: str = "IDENTIFIED"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Experiment:
    id: str
    stage: str = "IDEA"
    idea_id: str | None = None
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RevenueRecord:
    id: str
    amount_usd: float
    customer_id: str | None = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
