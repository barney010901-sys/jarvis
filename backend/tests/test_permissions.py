import asyncio

import pytest

from app.events.bus import EventBus
from app.events.models import EventType
from app.permissions.manager import ConfirmationManager, ConfirmationRejected


@pytest.mark.asyncio
async def test_confirmation_approved_resolves_true():
    bus = EventBus()
    manager = ConfirmationManager(bus)

    async def approve_soon():
        await asyncio.sleep(0)
        pending = manager.list_pending()[0]
        await manager.approve(pending.id)

    result, _ = await asyncio.gather(
        manager.request_confirmation(tool_name="github.create_issue", description="test"),
        approve_soon(),
    )
    assert result is True


@pytest.mark.asyncio
async def test_confirmation_rejected_raises():
    bus = EventBus()
    manager = ConfirmationManager(bus)

    async def reject_soon():
        await asyncio.sleep(0)
        pending = manager.list_pending()[0]
        await manager.reject(pending.id, reason="no thanks")

    with pytest.raises(ConfirmationRejected):
        await asyncio.gather(
            manager.request_confirmation(tool_name="github.create_issue", description="test"),
            reject_soon(),
        )


@pytest.mark.asyncio
async def test_confirmation_required_event_is_published():
    bus = EventBus()
    queue, _ = bus.subscribe_queue(EventType.CONFIRMATION_REQUIRED)
    manager = ConfirmationManager(bus)

    async def approve_soon():
        event = await queue.get()
        await manager.approve(event.payload["confirmation_id"])

    result, _ = await asyncio.gather(
        manager.request_confirmation(tool_name="browser.navigate", description="test", task_id="t1"),
        approve_soon(),
    )
    assert result is True
