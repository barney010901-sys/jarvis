from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.communication.channel import NotConfiguredChannelAdapter
from app.communication.models import Contact, ContactRole
from app.communication.store import ContactStore
from app.escalation.models import Urgency
from app.escalation.service import EscalationService
from app.escalation.store import EscalationStore
from app.events.bus import EventBus
from app.events.models import Event, EventType

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test")


@pytest.fixture
async def pool():
    try:
        p = await asyncpg.create_pool(dsn=TEST_DATABASE_URL, min_size=1, max_size=4, timeout=3)
        async with p.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} — see docs/PHASE_2.md for setup")
    yield p
    async with p.acquire() as conn:
        await conn.execute("TRUNCATE escalation_events, contacts CASCADE")
    await p.close()


def make_service(pool, event_bus=None):
    return EscalationService(
        contacts=ContactStore(pool), store=EscalationStore(pool), channel=NotConfiguredChannelAdapter(),
        event_bus=event_bus or EventBus(), user_display_name="the user",
    )


@pytest.mark.asyncio
async def test_no_escalation_when_user_available(pool):
    service = make_service(pool)
    decision = await service.evaluate(reason="client question", urgency=Urgency.HIGH, user_available=True)
    assert decision.action == "NOT_NEEDED"


@pytest.mark.asyncio
async def test_low_urgency_waits(pool):
    service = make_service(pool)
    decision = await service.evaluate(reason="minor note", urgency=Urgency.LOW, user_available=False)
    assert decision.action == "WAIT"


@pytest.mark.asyncio
async def test_medium_urgency_queues(pool):
    service = make_service(pool)
    decision = await service.evaluate(reason="follow-up needed", urgency=Urgency.MEDIUM, user_available=False)
    assert decision.action == "QUEUE"


@pytest.mark.asyncio
async def test_high_urgency_with_no_configured_contact_does_not_invent_one(pool):
    service = make_service(pool)
    decision = await service.evaluate(reason="urgent client issue", urgency=Urgency.HIGH, user_available=False)
    assert decision.action == "NO_AUTHORIZED_CONTACT"
    assert decision.contact is None


@pytest.mark.asyncio
async def test_high_urgency_escalates_to_configured_primary_contact(pool):
    contacts = ContactStore(pool)
    primary = await contacts.create(Contact(id=str(uuid.uuid4()), name="Mila", role=ContactRole.PRIMARY, channel="sms"))

    event_bus = EventBus()
    received: list[Event] = []

    async def record(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(record, EventType.ESCALATION_TRIGGERED)
    service = make_service(pool, event_bus)

    decision = await service.evaluate(reason="an important client needs to speak with the user urgently", urgency=Urgency.HIGH, user_available=False)

    assert decision.action == "ESCALATED"
    assert decision.contact.id == primary.id
    assert decision.delivered is False  # no real channel configured
    assert "Mila" in decision.message
    assert "important client needs to speak" in decision.message
    assert len(received) == 1

    history = await EscalationStore(pool).list_recent()
    assert history[0].result == "LOGGED_NOT_SENT"


@pytest.mark.asyncio
async def test_prefers_primary_over_secondary_contact(pool):
    contacts = ContactStore(pool)
    await contacts.create(Contact(id=str(uuid.uuid4()), name="Secondary Sam", role=ContactRole.SECONDARY, channel="sms"))
    await contacts.create(Contact(id=str(uuid.uuid4()), name="Primary Pat", role=ContactRole.PRIMARY, channel="sms"))

    service = make_service(pool)
    decision = await service.evaluate(reason="urgent", urgency=Urgency.HIGH, user_available=False)
    assert decision.contact.name == "Primary Pat"
