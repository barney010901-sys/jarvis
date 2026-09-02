"""Self-modification proposals (Phase 4 Self-Coding/Self-Update Engine).

A `SelfModificationProposal` is the durable record of "Jarvis wants to
change its own code." It is always created with status PROPOSED, always
routed through `PolicyEngine` with `kind="self_modification"` — which is
hard-coded to never auto-approve (see `app/policy/engine.py`) — and can
only move to APPLIED after a human explicitly approves it via the
existing Approval Center / ConfirmationManager flow. See
docs/PHASE_4_AUDIT.md §17(b) for why this boundary exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class SelfModificationProposal:
    id: str
    title: str
    reason: str
    diff: str
    test_plan: str
    rollback_plan: str
    affected_components: list[str] = field(default_factory=list)
    risk: str = "unknown"
    status: ProposalStatus = ProposalStatus.PROPOSED
    approval_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    applied_at: datetime | None = None
