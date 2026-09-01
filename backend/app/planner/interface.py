"""Planner interface: turns a natural-language request into an ordered plan.

A real implementation (Phase 2+) will call the `AIProvider` from `/agent`
to produce steps and tool calls dynamically. Phase 1 ships `StubPlanner`,
a deterministic placeholder that proves the shape without any reasoning.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PlanStep:
    description: str
    tool_name: str | None = None
    completed: bool = False


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
