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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
