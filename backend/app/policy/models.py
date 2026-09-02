"""The centralized policy vocabulary (2 Phase 3, section 28/29): every
external or sensitive action is expressed as a `PolicyRequest` and
resolved to exactly one `Decision` by `PolicyEngine.evaluate()`. Domain
services (wallet, communication, escalation, capability install) own
their own risk classification; the engine owns the generic
ask/log/gate mechanism so there's exactly one place that decides.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ASK = "ASK"


class AutonomyLevel(int, Enum):
    LEVEL_1_SUGGEST = 1
    LEVEL_2_PREPARE = 2
    LEVEL_3_ASK = 3
    LEVEL_4_EXECUTE_APPROVED = 4
    LEVEL_5_SAFE_AUTOMATION = 5


DEFAULT_AUTONOMY_LEVEL = AutonomyLevel.LEVEL_3_ASK


@dataclass
class PolicyRequest:
    kind: str  # 'wallet_transaction' | 'communication' | 'tool_install' | 'destructive_operation' | 'capability_install' | 'other'
    title: str
    description: str
    risk: str = "medium"  # 'low' | 'medium' | 'high'
    reversible: bool = True
    hard_block: bool = False  # RED: never even ask (e.g. blocked category/vendor)
    task_id: str | None = None
    cost_usd: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    # For LEVEL_4/5 auto-approval lookups, e.g. "communication:routine_reply"
    # or "wallet:software_subscription". None disables the pre-approval check.
    preapproval_key: str | None = None


@dataclass
class PolicyResult:
    decision: Decision
    reason: str
    approval_id: str | None = None
