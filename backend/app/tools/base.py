"""Tool interface. Every tool (real or placeholder) implements this.

See /tools/README.md for the cross-cutting spec these implementations must
satisfy, and docs/DECISIONS.md for which tools are genuinely functional vs.
explicit `NotImplementedError` placeholders in Phase 1.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.permissions.models import PermissionLevel

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Raised by a tool's execute() on any failure. The orchestrator turns
    this into a tool.completed(success=False) event rather than letting it
    propagate as an unhandled exception."""


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error)


@dataclass
class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    permission_level: PermissionLevel = PermissionLevel.SAFE

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool. Implementations should catch their own expected
        failure modes and return `ToolResult.fail(...)`; only truly
        unexpected exceptions should propagate (the caller wraps them into
        a ToolResult.fail as a last resort)."""

    async def run(self, **kwargs: Any) -> ToolResult:
        """Entry point callers should use: execute() plus a safety net so a
        buggy tool can never crash the orchestrator."""
        try:
            return await self.execute(**kwargs)
        except ToolError as exc:
            return ToolResult.fail(str(exc))
        except Exception as exc:  # noqa: BLE001 - last-resort safety net
            logger.exception("Tool %s raised an unexpected exception", self.name)
            return ToolResult.fail(f"Unexpected error in tool '{self.name}': {exc}")
