"""Process-wide component wiring (FastAPI dependency singletons).

Every `get_*` here is `lru_cache`d so the API layer, the WebSocket layer,
and the orchestrator all share the same EventBus/memory/confirmation-
manager instances. Tests should NOT import from this module — construct
fresh instances instead, so tests stay isolated from each other (see
`backend/tests/conftest.py`).
"""
from __future__ import annotations

from functools import lru_cache

from app.context import ContextEngine
from app.events.bus import EventBus, get_event_bus
from app.memory.store import (
    InMemoryLongTermMemory,
    InMemoryShortTermMemory,
    InMemoryWorkingMemory,
)
from app.orchestrator.interface import OrchestratorInterface
from app.orchestrator.stub_orchestrator import StubOrchestrator
from app.permissions.manager import ConfirmationManager
from app.planner.stub_planner import StubPlanner
from app.tools.registry import ToolRegistry, default_registry


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return default_registry(".")


@lru_cache
def get_confirmation_manager() -> ConfirmationManager:
    return ConfirmationManager(get_event_bus())


@lru_cache
def get_working_memory() -> InMemoryWorkingMemory:
    return InMemoryWorkingMemory()


@lru_cache
def get_short_term_memory() -> InMemoryShortTermMemory:
    return InMemoryShortTermMemory()


@lru_cache
def get_long_term_memory() -> InMemoryLongTermMemory:
    return InMemoryLongTermMemory()


@lru_cache
def get_context_engine() -> ContextEngine:
    return ContextEngine(get_working_memory(), get_short_term_memory(), get_long_term_memory())


@lru_cache
def get_orchestrator() -> OrchestratorInterface:
    return StubOrchestrator(
        event_bus=get_event_bus(),
        planner=StubPlanner(),
        tool_registry=get_tool_registry(),
        working_memory=get_working_memory(),
        short_term_memory=get_short_term_memory(),
        confirmation_manager=get_confirmation_manager(),
        context_engine=get_context_engine(),
    )


def reset_singletons() -> None:
    """Test-only helper: clear every cached singleton between tests that
    need a clean process-wide state."""
    for fn in (
        get_event_bus,
        get_tool_registry,
        get_confirmation_manager,
        get_working_memory,
        get_short_term_memory,
        get_long_term_memory,
        get_context_engine,
        get_orchestrator,
    ):
        fn.cache_clear()  # type: ignore[attr-defined]


__all__ = [
    "EventBus",
    "get_tool_registry",
    "get_confirmation_manager",
    "get_working_memory",
    "get_short_term_memory",
    "get_long_term_memory",
    "get_context_engine",
    "get_orchestrator",
    "reset_singletons",
]
