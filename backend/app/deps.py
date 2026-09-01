"""Process-wide component wiring.

Phase 1 built this as a set of `lru_cache`d getters, since every store was
in-memory and constructible synchronously at any time. Phase 2's stores
need an `asyncpg.Pool`, which can only be opened with `await` — so wiring
now happens once, explicitly, in `initialize()` (called from
`app.main`'s FastAPI lifespan), and the `get_*` functions below just read
back what `initialize()` built. See docs/DECISIONS.md ("Deps wiring became
an explicit async initialize() in Phase 2").

Tests should NOT import from this module — construct fresh instances
instead (see backend/tests/), so tests stay isolated from each other and
from whether Postgres/Claude happen to be configured in the environment
running the suite.
"""
from __future__ import annotations

import logging
from typing import Any

from agent.provider.router import ModelRouter, build_claude_router

from app.audit.logger import AuditLogger
from app.audit.store import AuditStore, InMemoryAuditStore, PostgresAuditStore
from app.config import get_settings
from app.context import ContextEngine
from app.cost.store import InMemoryUsageStore, PostgresUsageStore, UsageStore
from app.cost.tracker import CostTracker
from app.db.pool import close_pool, init_pool
from app.events.bus import EventBus, get_event_bus
from app.knowledge.postgres_store import PostgresKnowledgeStore
from app.knowledge.service import KnowledgeService
from app.learning.pipeline import LearningPipeline
from app.memory.postgres_store import PostgresLongTermMemory, PostgresShortTermMemory, PostgresWorkingMemory
from app.memory.store import (
    InMemoryLongTermMemory,
    InMemoryShortTermMemory,
    InMemoryWorkingMemory,
    LongTermMemory,
    ShortTermMemory,
    WorkingMemory,
)
from app.orchestrator.claude_orchestrator import ClaudeOrchestrator
from app.orchestrator.interface import OrchestratorInterface
from app.orchestrator.stub_orchestrator import StubOrchestrator
from app.permissions.manager import ConfirmationManager
from app.planner.claude_planner import ClaudePlanner
from app.planner.stub_planner import StubPlanner
from app.proactive.learning import ProactiveLearningEngine
from app.profile.interest_engine import InterestEngine
from app.profile.interface import ProfileStore
from app.profile.postgres_store import PostgresProfileStore
from app.profile.workflow_detector import WorkflowDetector
from app.suggestions.postgres_store import PostgresSuggestionQueue
from app.suggestions.service import SuggestionService
from app.tasks.interface import TaskStore
from app.tasks.postgres_store import PostgresTaskStore
from app.tasks.store import InMemoryTaskStore
from app.tools.registry import ToolRegistry, default_registry
from app.evaluation.engine import EvaluationEngine

logger = logging.getLogger(__name__)

_state: dict[str, Any] = {}


async def initialize() -> None:
    """Called once from FastAPI's lifespan (see app/main.py). Idempotent —
    a second call is a no-op unless `reset_state()` was called first
    (tests can use that to force re-initialization, though tests should
    generally construct their own instances instead — see module
    docstring)."""
    if _state:
        return

    settings = get_settings()
    event_bus = get_event_bus()
    tool_registry = default_registry(".")
    confirmation_manager = ConfirmationManager(event_bus)

    pool = await init_pool() if settings.jarvis_use_postgres else None

    working_memory: WorkingMemory
    short_term_memory: ShortTermMemory
    long_term_memory: LongTermMemory
    task_store: TaskStore
    audit_store: AuditStore
    usage_store: UsageStore

    if pool is not None:
        working_memory = PostgresWorkingMemory(pool)
        short_term_memory = PostgresShortTermMemory(pool)
        long_term_memory = PostgresLongTermMemory(pool)
        task_store = PostgresTaskStore(pool)
        audit_store = PostgresAuditStore(pool)
        usage_store = PostgresUsageStore(pool)
    else:
        logger.warning(
            "PostgreSQL unavailable or disabled (JARVIS_USE_POSTGRES=%s) — "
            "falling back to Phase 1 in-memory stores. See docs/PHASE_2.md.",
            settings.jarvis_use_postgres,
        )
        working_memory = InMemoryWorkingMemory()
        short_term_memory = InMemoryShortTermMemory()
        long_term_memory = InMemoryLongTermMemory()
        task_store = InMemoryTaskStore()
        audit_store = InMemoryAuditStore()
        usage_store = InMemoryUsageStore()

    claude_ready = pool is not None and settings.jarvis_use_claude and bool(settings.anthropic_api_key)

    orchestrator: OrchestratorInterface
    context_engine: ContextEngine
    profile_store: ProfileStore | None = None
    model_router: ModelRouter | None = None
    knowledge_service: KnowledgeService | None = None
    interest_engine: InterestEngine | None = None
    suggestion_service: SuggestionService | None = None
    proactive_engine: ProactiveLearningEngine | None = None
    cost_tracker = CostTracker(usage_store, daily_budget_usd=settings.token_budget_daily_usd)
    evaluation_engine = EvaluationEngine(tool_registry)

    if claude_ready:
        profile_store = PostgresProfileStore(pool)
        knowledge_service = KnowledgeService(
            PostgresKnowledgeStore(pool), event_bus, similarity_threshold=settings.knowledge_similarity_threshold
        )
        interest_engine = InterestEngine(profile_store, event_bus)
        workflow_detector = WorkflowDetector(profile_store)
        learning_pipeline = LearningPipeline(
            knowledge_service=knowledge_service, interest_engine=interest_engine, workflow_detector=workflow_detector
        )
        suggestion_service = SuggestionService(PostgresSuggestionQueue(pool), event_bus)
        proactive_engine = ProactiveLearningEngine(
            interest_engine=interest_engine,
            knowledge_service=knowledge_service,
            suggestion_service=suggestion_service,
            enabled=settings.feature_proactive_learning,
        )

        context_engine = ContextEngine(
            working_memory, short_term_memory, long_term_memory, knowledge_service=knowledge_service, profile_store=profile_store
        )

        model_router = build_claude_router(
            api_key=settings.anthropic_api_key,
            primary_model=settings.jarvis_model_primary,
            fast_model=settings.jarvis_model_fast,
            fallback_model=settings.jarvis_model_fallback,
            max_tokens=settings.claude_max_tokens,
            timeout=settings.claude_timeout_seconds,
            max_retries=settings.claude_max_retries,
        )
        planner = ClaudePlanner(model_router, [t.name for t in tool_registry.list()])

        orchestrator = ClaudeOrchestrator(
            event_bus=event_bus,
            planner=planner,
            tool_registry=tool_registry,
            working_memory=working_memory,
            short_term_memory=short_term_memory,
            confirmation_manager=confirmation_manager,
            context_engine=context_engine,
            model_router=model_router,
            task_store=task_store,
            evaluation_engine=evaluation_engine,
            cost_tracker=cost_tracker,
            knowledge_service=knowledge_service,
            learning_pipeline=learning_pipeline,
            profile_store=profile_store,
            min_confidence_to_skip_claude=settings.knowledge_min_confidence_to_skip_claude,
        )
        logger.info("ClaudeOrchestrator active: Postgres connected and ANTHROPIC_API_KEY configured.")
    else:
        context_engine = ContextEngine(working_memory, short_term_memory, long_term_memory)
        orchestrator = StubOrchestrator(
            event_bus=event_bus,
            planner=StubPlanner(),
            tool_registry=tool_registry,
            working_memory=working_memory,
            short_term_memory=short_term_memory,
            confirmation_manager=confirmation_manager,
            context_engine=context_engine,
        )
        if pool is None:
            reason = "PostgreSQL unavailable/disabled"
        elif not settings.jarvis_use_claude:
            reason = "JARVIS_USE_CLAUDE=false"
        else:
            reason = "ANTHROPIC_API_KEY not set"
        logger.warning("Falling back to StubOrchestrator (Phase 1 behavior): %s.", reason)

    audit_logger = AuditLogger(event_bus, audit_store)
    audit_logger.start()

    _state.update(
        pool=pool,
        claude_ready=claude_ready,
        event_bus=event_bus,
        tool_registry=tool_registry,
        confirmation_manager=confirmation_manager,
        working_memory=working_memory,
        short_term_memory=short_term_memory,
        long_term_memory=long_term_memory,
        context_engine=context_engine,
        task_store=task_store,
        audit_store=audit_store,
        audit_logger=audit_logger,
        usage_store=usage_store,
        cost_tracker=cost_tracker,
        evaluation_engine=evaluation_engine,
        profile_store=profile_store,
        model_router=model_router,
        knowledge_service=knowledge_service,
        interest_engine=interest_engine,
        suggestion_service=suggestion_service,
        proactive_engine=proactive_engine,
        orchestrator=orchestrator,
    )


async def shutdown() -> None:
    await close_pool()
    _state.clear()


def reset_state() -> None:
    """Test-only: force the next initialize() call to rebuild everything."""
    _state.clear()


def _get(key: str) -> Any:
    if key not in _state:
        raise RuntimeError("app.deps.initialize() has not run yet — this is set up by app.main's FastAPI lifespan.")
    return _state[key]


def get_tool_registry() -> ToolRegistry:
    return _get("tool_registry")


def get_confirmation_manager() -> ConfirmationManager:
    return _get("confirmation_manager")


def get_working_memory() -> WorkingMemory:
    return _get("working_memory")


def get_short_term_memory() -> ShortTermMemory:
    return _get("short_term_memory")


def get_long_term_memory() -> LongTermMemory:
    return _get("long_term_memory")


def get_context_engine() -> ContextEngine:
    return _get("context_engine")


def get_orchestrator() -> OrchestratorInterface:
    return _get("orchestrator")


def get_task_store() -> TaskStore:
    return _get("task_store")


def get_cost_tracker() -> CostTracker:
    return _get("cost_tracker")


def get_knowledge_service() -> KnowledgeService | None:
    return _state.get("knowledge_service")


def get_profile_store() -> ProfileStore | None:
    return _state.get("profile_store")


def get_suggestion_service() -> SuggestionService | None:
    return _state.get("suggestion_service")


def get_proactive_engine() -> ProactiveLearningEngine | None:
    return _state.get("proactive_engine")


def is_claude_ready() -> bool:
    return bool(_state.get("claude_ready"))


__all__ = [
    "initialize",
    "shutdown",
    "reset_state",
    "get_event_bus",
    "get_tool_registry",
    "get_confirmation_manager",
    "get_working_memory",
    "get_short_term_memory",
    "get_long_term_memory",
    "get_context_engine",
    "get_orchestrator",
    "get_task_store",
    "get_cost_tracker",
    "get_knowledge_service",
    "get_profile_store",
    "get_suggestion_service",
    "get_proactive_engine",
    "is_claude_ready",
]
