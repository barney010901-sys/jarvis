"""Claude-backed planner (2A's "Planner → Structured plan" step). Asks the
"fast" model role for a short JSON plan; falls back to `StubPlanner` on any
failure — a planning hiccup should degrade the plan, not fail the whole
task. See docs/DECISIONS.md ("Planner failures fall back, they don't fail
the task").

Phase 3: takes the `ToolRegistry` (not just a list of names) so the
planning prompt can include each tool's description and input schema —
without that, Claude has no way to know a wallet transaction needs
`amount_usd`/`vendor`/`category`/`purpose` in `tool_args`.
"""
from __future__ import annotations

import json
import logging

from agent.provider.base import Message, ProviderError
from agent.provider.router import FAST, ModelRouter
from app.planner.interface import Plan, PlannerInterface, PlanStep
from app.planner.stub_planner import StubPlanner
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Jarvis's task planner. Given a user request and a list of "
    "available tools (each with a name, description, and JSON input "
    "schema), respond with ONLY a JSON array of 1-5 steps, each shaped "
    '{"description": string, "tool_name": string|null, "tool_args": object}. '
    'Set "tool_name" only when the step should invoke one of the listed '
    'tools, by exact name, and set "tool_args" to an object matching that '
    "tool's input schema (omit or use {} when the step needs no tool or the "
    "tool takes no arguments). No prose, no markdown code fences — the "
    "entire response must be valid JSON and nothing else."
)


class ClaudePlanner(PlannerInterface):
    def __init__(self, router: ModelRouter, tool_registry: ToolRegistry, *, fallback: PlannerInterface | None = None) -> None:
        self._router = router
        self._tools = tool_registry
        self._fallback = fallback or StubPlanner()

    async def plan(self, task_id: str, request: str) -> Plan:
        try:
            tool_specs = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in self._tools.list()
            ]
            prompt = f"Available tools:\n{json.dumps(tool_specs)}\n\nUser request: {request}"
            result = await self._router.complete(FAST, system=_SYSTEM_PROMPT, messages=[Message(role="user", content=prompt)])
            steps = _parse_steps(result.text)
            if not steps:
                raise ValueError("Claude returned an empty plan")
            return Plan(task_id=task_id, steps=steps)
        except (ProviderError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("ClaudePlanner failed for task %s (%s) — falling back to StubPlanner", task_id, exc)
            return await self._fallback.plan(task_id, request)


def _parse_steps(text: str) -> list[PlanStep]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Tolerate an accidental ```json ... ``` fence despite the prompt.
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of steps")
    return [
        PlanStep(description=str(item["description"]), tool_name=item.get("tool_name"), tool_args=dict(item.get("tool_args") or {}))
        for item in data
    ]
