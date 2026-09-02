"""Planner interface: turns a natural-language request into an ordered plan.

A real implementation (Phase 2+) will call the `AIProvider` from `/agent`
to produce steps and tool calls dynamically. Phase 1 ships `StubPlanner`,
a deterministic placeholder that proves the shape without any reasoning.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    description: str
    tool_name: str | None = None
    completed: bool = False
    # Phase 2 (2U): when a planner knows this step should produce a
    # specific file, the evaluation engine verifies it actually exists
    # rather than trusting the response. Optional — Phase 1 planners never
    # set this, and nothing breaks if it stays None.
    expected_file: str | None = None
    # Phase 3: arguments passed to `tool_name`'s execute() — e.g. a wallet
    # tool needs {"amount_usd": ..., "vendor": ...}. Optional and empty by
    # default so Phase 1/2 planners (which never set it) are unaffected;
    # see plan_execution.execute_plan(), which merges this over the
    # existing `project_root` default rather than replacing it.
    tool_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    task_id: str
    steps: list[PlanStep] = field(default_factory=list)

    def next_step(self) -> PlanStep | None:
        for step in self.steps:
            if not step.completed:
                return step
        return None

    def is_complete(self) -> bool:
        return all(step.completed for step in self.steps)


class PlannerInterface(ABC):
    @abstractmethod
    async def plan(self, task_id: str, request: str) -> Plan: ...
