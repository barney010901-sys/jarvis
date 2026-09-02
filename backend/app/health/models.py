from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_TESTED = "NOT_TESTED"


@dataclass
class ComponentHealth:
    component: str
    status: HealthStatus
    detail: str
