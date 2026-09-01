"""Phase 1 orchestrator: exercises the full event/permission/tool lifecycle
with the StubPlanner. No real reasoning — see docs/PHASE_1.md.

This is deliberately the piece with the most "moving parts" wired together
(events, memory, permissions, tools) because it's the seam every later
phase (a real planner, a real AIProvider) plugs into without changing the
API/WebSocket layer above it.
"""
from __future__ import annotations

import logging
import uuid

from app.context import ContextEngine
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.memory.store import ConversationTurn, ShortTermMemory, WorkingMemory
from app.orchestrator.interface import OrchestratorInterface
from app.permissions.manager import ConfirmationManager, ConfirmationRejected
from app.permissions.models import PermissionLevel
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

        await self._working_memory.set(task_id, "plan", plan)
        await self._event_bus.publish(
            Event(
                type=EventType.TASK_PLANNED,
                task_id=task_id,
                payload={"steps": [s.description for s in plan.steps]},
            )
        )

        await self._event_bus.publish(Event(type=EventType.TASK_STARTED, task_id=task_id, payload={}))

        step = plan.next_step()
        while step is not None:
            if step.tool_name:
                tool = self._tools.get(step.tool_name)
                if tool is None:
                    await self._event_bus.publish(
                        Event(
                            type=EventType.TASK_FAILED,
                            task_id=task_id,
                            payload={"stage": "tool_lookup", "error": f"unknown tool '{step.tool_name}'"},
                        )
                    )
                    return task_id

                if tool.permission_level == PermissionLevel.SENSITIVE:
                    try:
                        await self._confirmations.request_confirmation(
                            tool_name=tool.name,
                            description=step.description,
                            task_id=task_id,
                        )
                    except ConfirmationRejected:
                        await self._event_bus.publish(
                            Event(
                                type=EventType.TASK_FAILED,
                                task_id=task_id,
                                payload={"stage": "confirmation", "error": "user rejected the sensitive action"},
                            )
                        )
                        return task_id

                await self._event_bus.publish(
                    Event(type=EventType.TOOL_STARTED, task_id=task_id, payload={"tool_name": tool.name})
                )
                result = await tool.run(project_root=".")
                await self._event_bus.publish(
                    Event(
                        type=EventType.TOOL_COMPLETED,
                        task_id=task_id,
                        payload={"tool_name": tool.name, "success": result.success, "error": result.error},
                    )
                )
                if not result.success:
                    await self._event_bus.publish(
                        Event(
                            type=EventType.TASK_FAILED,
                            task_id=task_id,
                            payload={"stage": "tool_execution", "tool_name": tool.name, "error": result.error},
                        )
                    )
                    return task_id

            step.completed = True
            step = plan.next_step()

        await self._working_memory.clear(task_id)
        response_text = f"Completed {len(plan.steps)} step(s) for: {text!r} (Phase 1 stub — no real reasoning yet)."
        await self._short_term_memory.append(session_id, ConversationTurn(role="assistant", content=response_text))
        await self._event_bus.publish(
            Event(type=EventType.TASK_COMPLETED, task_id=task_id, payload={"response": response_text})
        )
        return task_id
