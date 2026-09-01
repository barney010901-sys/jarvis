from __future__ import annotations

from app.planner.interface import Plan, PlannerInterface, PlanStep


class StubPlanner(PlannerInterface):
    """Deterministic placeholder planner.

    Always returns the same three-step "inspect / act / report" shape
    regardless of the request, so the orchestrator, memory, and event
    plumbing can be exercised without any real reasoning. Replace with an
    AIProvider-backed planner in Phase 2.
    """

    async def plan(self, task_id: str, request: str) -> Plan:
        return Plan(
            task_id=task_id,
            steps=[
                PlanStep(description=f"Inspect project context for: {request!r}", tool_name="project.inspect"),
                PlanStep(description="Determine the necessary action (placeholder — no reasoning yet)"),
                PlanStep(description="Report completion back to the user"),
            ],
        )
