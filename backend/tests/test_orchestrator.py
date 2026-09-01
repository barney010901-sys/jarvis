import pytest

from app.context import ContextEngine
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.memory.store import (
    InMemoryLongTermMemory,
    InMemoryShortTermMemory,
    InMemoryWorkingMemory,
)
from app.orchestrator.stub_orchestrator import StubOrchestrator
from app.permissions.manager import ConfirmationManager
from app.planner.stub_planner import StubPlanner
from app.tools.registry import default_registry


def make_orchestrator(tmp_path):
    bus = EventBus()
    working = InMemoryWorkingMemory()
    short_term = InMemoryShortTermMemory()
    long_term = InMemoryLongTermMemory()
    orchestrator = StubOrchestrator(
        event_bus=bus,
        planner=StubPlanner(),
        tool_registry=default_registry(str(tmp_path)),
        working_memory=working,
        short_term_memory=short_term,
        confirmation_manager=ConfirmationManager(bus),
        context_engine=ContextEngine(working, short_term, long_term),
    )
    return bus, orchestrator, short_term


@pytest.mark.asyncio
async def test_handle_message_emits_expected_event_sequence(tmp_path):
    bus, orchestrator, _ = make_orchestrator(tmp_path)
    events: list[Event] = []

    async def record(event: Event) -> None:
        events.append(event)

    bus.subscribe(record)

    task_id = await orchestrator.handle_message(session_id="s1", project="p1", text="build a landing page")

    types = [e.type for e in events]
    assert types == [
        EventType.USER_MESSAGE,
        EventType.TASK_CREATED,
        EventType.TASK_PLANNED,
        EventType.TASK_STARTED,
        EventType.TOOL_STARTED,
        EventType.TOOL_COMPLETED,
        EventType.TASK_COMPLETED,
    ]
    assert all(e.task_id in (None, task_id) for e in events)
    assert events[-1].payload["response"]


@pytest.mark.asyncio
async def test_handle_message_records_conversation_turns(tmp_path):
    bus, orchestrator, short_term = make_orchestrator(tmp_path)
    await orchestrator.handle_message(session_id="s1", project="p1", text="hello jarvis")

    turns = await short_term.recent("s1")
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[0].content == "hello jarvis"
