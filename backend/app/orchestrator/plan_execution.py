"""Shared plan-step execution loop: tool lookup, permission gating, and
event publishing. Used by both `StubOrchestrator` (Phase 1) and
`ClaudeOrchestrator` (Phase 2) so the tool/confirmation logic exists in
exactly one place — see docs/DECISIONS.md ("Plan execution is shared, not
duplicated between orchestrators").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.permissions.manager import ConfirmationManager, ConfirmationRejected
from app.permissions.models import PermissionLevel
from app.planner.interface import Plan
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


@dataclass
class PlanExecutionOutcome:
    success: bool
    tool_results: list[ToolResult] = field(default_factory=list)
    failed_stage: str | None = None
    failed_tool_name: str | None = None
    error: str | None = None


async def execute_plan(
    plan: Plan,
    *,
    tool_registry: ToolRegistry,
    confirmation_manager: ConfirmationManager,
    event_bus: EventBus,
    task_id: str,
) -> PlanExecutionOutcome:
    tool_results: list[ToolResult] = []
    step = plan.next_step()

    while step is not None:
        if step.tool_name:
            tool = tool_registry.get(step.tool_name)
            if tool is None:
                return PlanExecutionOutcome(
                    success=False, tool_results=tool_results, failed_stage="tool_lookup", error=f"unknown tool '{step.tool_name}'"
                )

            if tool.permission_level == PermissionLevel.SENSITIVE:
                try:
                    await confirmation_manager.request_confirmation(tool_name=tool.name, description=step.description, task_id=task_id)
                except ConfirmationRejected:
                    return PlanExecutionOutcome(
                        success=False, tool_results=tool_results, failed_stage="confirmation", error="user rejected the sensitive action"
                    )

            await event_bus.publish(Event(type=EventType.TOOL_STARTED, task_id=task_id, payload={"tool_name": tool.name}))
            result = await tool.run(project_root=".")
            tool_results.append(result)
            await event_bus.publish(
                Event(type=EventType.TOOL_COMPLETED, task_id=task_id, payload={"tool_name": tool.name, "success": result.success, "error": result.error})
            )
            if not result.success:
                return PlanExecutionOutcome(
                    success=False, tool_results=tool_results, failed_stage="tool_execution", failed_tool_name=tool.name, error=result.error
                )

        step.completed = True
        step = plan.next_step()

    return PlanExecutionOutcome(success=True, tool_results=tool_results)
