from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    REAL = "REAL"
    MOCKED = "MOCKED"
    PARTIALLY_IMPLEMENTED = "PARTIALLY_IMPLEMENTED"
    NOT_TESTED = "NOT_TESTED"


@dataclass
class Capability:
    id: str
    name: str
    type: str  # 'tool' | 'library' | 'api' | 'mcp_server' | 'service'
    purpose: str
    source: str
    version: str | None = None
    permissions: list[str] = field(default_factory=list)
    risk: str = "unknown"
    reversibility: str = "unknown"
    cost_estimate_usd: float | None = None
    success_rate: float | None = None
    confidence: float = 0.3
    verification_status: VerificationStatus = VerificationStatus.NOT_TESTED
    metadata: dict[str, Any] = field(default_factory=dict)
    # Phase 4 (Capability Registry, additive to the Phase 3 discovery
    # table above — see docs/PHASE_4_AUDIT.md §17c):
    usage_count: int = 0
    success_count: int = 0
    owner: str | None = None  # e.g. an agent name, once agents exist
    status: str = "active"  # 'active' | 'disabled' | 'deprecated'
    composed_of: list[str] = field(default_factory=list)  # component capability ids, for type='composite'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success_rate_observed(self) -> float | None:
        """Usage-derived success rate — distinct from the `success_rate`
        field above, which a capability may arrive with pre-filled (e.g.
        from external metadata) before Jarvis has ever actually used it."""
        if self.usage_count == 0:
            return None
        return self.success_count / self.usage_count
