"""Phase 1 orchestrator: exercises the full event/permission/tool lifecycle
with the StubPlanner. No real reasoning — see docs/PHASE_1.md. Kept
unchanged (not replaced) in Phase 2: it's still what `deps.py` falls back
to when Postgres/Claude aren't configured (docs/PHASE_2.md), and it's a
useful "prove the plumbing works with zero external dependencies" mode on
its own.

This is deliberately the piece with the most "moving parts" wired together
(events, memory, permissions, tools) because it's the seam every later
phase (a real planner, a real AIProvider) plugs into without changing the
API/WebSocket layer above it. Phase 2 added `ClaudeOrchestrator` alongside
this one, sharing the tool-execution loop via `plan_execution.py` instead
of duplicating it.
"""
from __future__ import annotations

import logging
import uuid

from app.context import ContextEngine
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.memory.store import ConversationTurn, ShortTermMemory, WorkingMemory
from app.orchestrator.interface import OrchestratorInterface
from app.orchestrator.plan_execution import execute_plan
from app.permissions.manager import ConfirmationManager
from app.planner.interface import PlannerInterface
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class StubOrchestrator(OrchestratorInterface):
    def __init__(
        self,
        *,
        event_bus: EventBus,
        planner: PlannerInterface,
        tool_registry: ToolRegistry,
        working_memory: WorkingMemory,
        short_term_memory: ShortTermMemory,
        confirmation_manager: ConfirmationManager,
        context_engine: ContextEngine,
    ) -> None:
        self._event_bus = event_bus
        self._planner = planner
        self._tools = tool_registry
        self._working_memory = working_memory
        self._short_term_memory = short_term_memory
        self._confirmations = confirmation_manager
        self._context = context_engine

    async def handle_message(self, *, session_id: str, project: str, text: str) -> str:
        await self._short_term_memory.append(session_id, ConversationTurn(role="user", content=text))
        await self._event_bus.publish(Event(type=EventType.USER_MESSAGE, payload={"session_id": session_id, "text": text}))

        task_id = str(uuid.uuid4())
        await self._event_bus.publish(Event(type=EventType.TASK_CREATED, task_id=task_id, payload={"request": text}))

        try:
            plan = await self._planner.plan(task_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Planning failed for task %s", task_id)
            await self._event_bus.publish(
                Event(type=EventType.TASK_FAILED, task_id=task_id, payload={"stage": "planning", "error": str(exc)})
            )
            return task_id

        # Stored as plain dicts, not the Plan dataclass: working memory is
        # meant to hold serializable state (see docs/DECISIONS.md, "Working
        # memory stores plain data, not live objects") so it works
        # identically against the in-memory and Postgres-backed stores.
        await self._working_memory.set(
            task_id, "plan", [{"description": s.description, "tool_name": s.tool_name} for s in plan.steps]
        )
        await self._event_bus.publish(
            Event(
                type=EventType.TASK_PLANNED,
                task_id=task_id,
                payload={"steps": [s.description for s in plan.steps]},
            )
        )

        await self._event_bus.publish(Event(type=EventType.TASK_STARTED, task_id=task_id, payload={}))

        outcome = await execute_plan(
            plan, tool_registry=self._tools, confirmation_manager=self._confirmations, event_bus=self._event_bus, task_id=task_id
        )
        if not outcome.success:
            await self._working_memory.clear(task_id)
            await self._event_bus.publish(
                Event(
                    type=EventType.TASK_FAILED,
                    task_id=task_id,
                    payload={"stage": outcome.failed_stage, "error": outcome.error, "tool_name": outcome.failed_tool_name},
                )
            )
            return task_id

        await self._working_memory.clear(task_id)
        response_text = f"Completed {len(plan.steps)} step(s) for: {text!r} (Phase 1 stub — no real reasoning yet)."
        await self._short_term_memory.append(session_id, ConversationTurn(role="assistant", content=response_text))
        await self._event_bus.publish(
            Event(type=EventType.TASK_COMPLETED, task_id=task_id, payload={"response": response_text})
        )
        return task_id
