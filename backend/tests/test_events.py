import pytest

from app.events.bus import EventBus
from app.events.models import Event, EventType


@pytest.mark.asyncio
async def test_publish_delivers_to_matching_subscriber():
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler, EventType.TASK_CREATED)
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
    await bus.publish(Event(type=EventType.TASK_COMPLETED, task_id="t1"))

    assert len(received) == 1
    assert received[0].type == EventType.TASK_CREATED


@pytest.mark.asyncio
async def test_wildcard_subscriber_gets_every_event():
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)  # no event_type => wildcard
    await bus.publish(Event(type=EventType.TASK_CREATED))
    await bus.publish(Event(type=EventType.TASK_COMPLETED))

    assert [e.type for e in received] == [EventType.TASK_CREATED, EventType.TASK_COMPLETED]


@pytest.mark.asyncio
async def test_subscribe_queue_and_unsubscribe():
    bus = EventBus()
    queue, unsubscribe = bus.subscribe_queue(EventType.TOOL_STARTED)

    await bus.publish(Event(type=EventType.TOOL_STARTED, payload={"tool_name": "x"}))
    event = await queue.get()
    assert event.payload["tool_name"] == "x"

    unsubscribe()
    await bus.publish(Event(type=EventType.TOOL_STARTED, payload={"tool_name": "y"}))
    assert queue.empty()


@pytest.mark.asyncio
async def test_broken_handler_does_not_break_the_bus():
    bus = EventBus()
    calls: list[str] = []

    async def broken(event: Event) -> None:
        raise RuntimeError("boom")

    async def fine(event: Event) -> None:
        calls.append("fine")

    bus.subscribe(broken)
    bus.subscribe(fine)
    await bus.publish(Event(type=EventType.TASK_CREATED))

    assert calls == ["fine"]


def test_event_json_safe_serialization():
    event = Event(type=EventType.TASK_FAILED, task_id="t1", payload={"error": "oops"})
    dumped = event.model_dump_json_safe()
    assert dumped["type"] == "task.failed"
    assert dumped["task_id"] == "t1"
    assert isinstance(dumped["timestamp"], str)
