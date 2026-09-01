"""Phase 2 orchestrator: real Claude reasoning, wired through the exact
flow in the task spec (2A):

  user message -> context -> memory -> planner -> structured plan ->
  Claude -> tool/task execution -> result -> evaluation ->
  memory/knowledge update -> response

Implements `OrchestratorInterface` alongside `StubOrchestrator` (not
instead of it — see docs/DECISIONS.md, "ClaudeOrchestrator is additive").
Shares `execute_plan` with StubOrchestrator so the tool/confirmation loop
exists in exactly one place.
"""
from __future__ import annotations

import logging
import uuid

from agent.provider.base import Message, ProviderError, ProviderResult
from agent.provider.router import ModelRouter, PRIMARY

from app.context import ContextEngine
from app.cost.tracker import CostTracker
from app.evaluation.engine import EvaluationEngine, EvaluationVerdict
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.knowledge.service import KnowledgeService
from app.learning.pipeline import LearningPipeline
from app.memory.store import ConversationTurn, ShortTermMemory, WorkingMemory
from app.orchestrator.interface import OrchestratorInterface
from app.orchestrator.plan_execution import execute_plan
from app.permissions.manager import ConfirmationManager
from app.planner.interface import PlannerInterface
from app.profile.interface import ProfileStore
from app.prompts_loader import load_prompt
from app.tasks.interface import TaskStore
from app.tasks.models import TaskRecord, TaskStatus
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ClaudeOrchestrator(OrchestratorInterface):
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
        model_router: ModelRouter,
        task_store: TaskStore,
        evaluation_engine: EvaluationEngine,
        cost_tracker: CostTracker,
        knowledge_service: KnowledgeService,
        learning_pipeline: LearningPipeline,
        profile_store: ProfileStore | None = None,
        min_confidence_to_skip_claude: float = 0.85,
        primary_role: str = PRIMARY,
    ) -> None:
        self._event_bus = event_bus
        self._planner = planner
        self._tools = tool_registry
        self._working_memory = working_memory
        self._short_term_memory = short_term_memory
        self._confirmations = confirmation_manager
        self._context = context_engine
        self._router = model_router
        self._task_store = task_store
        self._evaluation = evaluation_engine
        self._cost = cost_tracker
        self._knowledge = knowledge_service
        self._learning = learning_pipeline
        self._profile = profile_store
        self._min_confidence_to_skip_claude = min_confidence_to_skip_claude
        self._primary_role = primary_role

    async def handle_message(self, *, session_id: str, project: str, text: str) -> str:
        await self._short_term_memory.append(session_id, ConversationTurn(role="user", content=text))
        await self._event_bus.publish(Event(type=EventType.USER_MESSAGE, payload={"session_id": session_id, "text": text}))

        known_topics: list[str] = []
        if self._profile is not None:
            proj = await self._profile.get_project(project)
            if proj:
                known_topics = proj.technologies
                await self._profile.touch_project(project)
        await self._learning.on_user_message(project=project, text=text, known_topics=known_topics)

        task_id = str(uuid.uuid4())
        await self._task_store.create(TaskRecord(id=task_id, session_id=session_id, project=project, request=text))
        await self._event_bus.publish(Event(type=EventType.TASK_CREATED, task_id=task_id, payload={"request": text}))

        # --- 2E cost hierarchy: skip Claude entirely if we already know a
        # sufficiently-confident answer. ---
        known_answer = await self._knowledge.find_high_confidence_answer(
            project=project, query=text, min_confidence=self._min_confidence_to_skip_claude
        )
        if known_answer is not None:
            await self._cost.record_avoided_request(task_id=task_id, reason=f"matched knowledge {known_answer.id}")
            response_text = known_answer.content
            await self._short_term_memory.append(session_id, ConversationTurn(role="assistant", content=response_text))
            await self._task_store.set_status(
                task_id, TaskStatus.COMPLETED, result={"response": response_text, "served_from_knowledge": True}
            )
            await self._event_bus.publish(
                Event(type=EventType.TASK_COMPLETED, task_id=task_id, payload={"response": response_text, "served_from_knowledge": True})
            )
            return task_id

        # --- context ---
        context_bundle = await self._context.build(task_id=task_id, session_id=session_id, project=project, query=text)
        await self._event_bus.publish(
            Event(
                type=EventType.CONTEXT_UPDATED,
                task_id=task_id,
                payload={"included": context_bundle.included, "history_truncated": context_bundle.history_truncated},
            )
        )

        # --- planner ---
        try:
            plan = await self._planner.plan(task_id, text)
        except Exception as exc:  # noqa: BLE001 - planning must degrade, not crash the request
            logger.exception("Planning failed for task %s", task_id)
            await self._task_store.set_status(task_id, TaskStatus.FAILED, error=str(exc))
            await self._event_bus.publish(
                Event(type=EventType.TASK_FAILED, task_id=task_id, payload={"stage": "planning", "error": str(exc)})
            )
            return task_id

        plan_dicts = [{"description": s.description, "tool_name": s.tool_name} for s in plan.steps]
        await self._working_memory.set(task_id, "plan", plan_dicts)
        await self._task_store.set_status(task_id, TaskStatus.PLANNED, plan=plan_dicts)
        await self._event_bus.publish(
            Event(type=EventType.TASK_PLANNED, task_id=task_id, payload={"steps": [s.description for s in plan.steps]})
        )

        await self._task_store.set_status(task_id, TaskStatus.RUNNING)
        await self._event_bus.publish(Event(type=EventType.TASK_STARTED, task_id=task_id, payload={}))

        outcome = await execute_plan(
            plan, tool_registry=self._tools, confirmation_manager=self._confirmations, event_bus=self._event_bus, task_id=task_id
        )
        if not outcome.success:
            await self._working_memory.clear(task_id)
            await self._task_store.set_status(task_id, TaskStatus.FAILED, error=outcome.error)
            await self._event_bus.publish(
                Event(
                    type=EventType.TASK_FAILED,
                    task_id=task_id,
                    payload={"stage": outcome.failed_stage, "error": outcome.error, "tool_name": outcome.failed_tool_name},
                )
            )
            return task_id

        # --- reasoning: stream the real response, forwarding chunks live ---
        system_prompt = load_prompt("system_prompt.md").replace("{context}", context_bundle.text or "(no additional context)")
        chunks: list[str] = []
        try:
            async for chunk in self._router.stream(self._primary_role, system=system_prompt, messages=[Message(role="user", content=text)]):
                chunks.append(chunk)
                await self._event_bus.publish(Event(type=EventType.TASK_DELTA, task_id=task_id, payload={"text": chunk}))
        except ProviderError as exc:
            await self._working_memory.clear(task_id)
            await self._task_store.set_status(task_id, TaskStatus.FAILED, error=str(exc))
            await self._event_bus.publish(
                Event(type=EventType.TASK_FAILED, task_id=task_id, payload={"stage": "reasoning", "error": str(exc)})
            )
            return task_id

        response_text = "".join(chunks).strip()
        used_provider = self._router.last_used_provider
        if used_provider is not None:
            synthetic_result = ProviderResult(text=response_text, usage=used_provider.last_usage, model=used_provider.model)
            await self._cost.record_provider_usage(
                synthetic_result, provider=used_provider.name, role=self._router.last_used_role or self._primary_role, task_id=task_id
            )

        # --- evaluation (2U): don't trust "done" just because Claude said so ---
        await self._task_store.set_status(task_id, TaskStatus.EVALUATING)
        await self._event_bus.publish(Event(type=EventType.TASK_EVALUATING, task_id=task_id, payload={}))
        evaluation = await self._evaluation.evaluate(plan_steps=plan.steps, tool_results=outcome.tool_results, response_text=response_text)

        # --- learning (2H/2I/2L/2N) ---
        await self._learning.on_task_completed(
            project=project, request=text, plan_steps=plan.steps, evaluation=evaluation, response_text=response_text
        )

        await self._working_memory.clear(task_id)
        await self._short_term_memory.append(session_id, ConversationTurn(role="assistant", content=response_text))

        if evaluation.verdict == EvaluationVerdict.FAILED:
            await self._task_store.set_status(
                task_id, TaskStatus.FAILED, error="evaluation failed", result={"response": response_text, "verdict": evaluation.verdict.value}
            )
            await self._event_bus.publish(
                Event(
                    type=EventType.TASK_FAILED,
                    task_id=task_id,
                    payload={"stage": "evaluation", "verdict": evaluation.verdict.value, "response": response_text},
                )
            )
        else:
            await self._task_store.set_status(task_id, TaskStatus.COMPLETED, result={"response": response_text, "verdict": evaluation.verdict.value})
            await self._event_bus.publish(
                Event(type=EventType.TASK_COMPLETED, task_id=task_id, payload={"response": response_text, "verdict": evaluation.verdict.value})
            )

        return task_id
