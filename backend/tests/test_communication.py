"""REAL integration tests against a live PostgreSQL instance. The channel
adapter is the real `NotConfiguredChannelAdapter` — it genuinely raises
NotImplementedError, which is exactly the behavior under test (nothing is
ever silently "sent").
"""
from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest

from app.communication.channel import NotConfiguredChannelAdapter
from app.communication.models import Category, Contact, ContactRole
from app.communication.service import CommunicationService
from app.communication.store import CommunicationStore, ContactStore
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.permissions.manager import ConfirmationManager
from app.policy.approvals import ApprovalStore
from app.policy.engine import PolicyEngine
from app.policy.store import PolicyStore

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
        await conn.execute("TRUNCATE communications, contacts, approvals CASCADE")
    await p.close()


async def _wait_for_pending(confirmations, timeout: float = 2.0):
    elapsed = 0.0
    while not confirmations.list_pending():
        await asyncio.sleep(0.01)
        elapsed += 0.01
        if elapsed > timeout:
            raise TimeoutError("no pending confirmation appeared in time")
    return confirmations.list_pending()[0]


def make_service(pool):
    event_bus = EventBus()
    confirmations = ConfirmationManager(event_bus)
    policy = PolicyEngine(policy_store=PolicyStore(pool), approval_store=ApprovalStore(pool), confirmation_manager=confirmations, event_bus=event_bus)
    contacts = ContactStore(pool)
    service = CommunicationService(
        contacts=contacts, communications=CommunicationStore(pool), policy_engine=policy, channel=NotConfiguredChannelAdapter(), event_bus=event_bus
    )
    return service, contacts, confirmations, event_bus


@pytest.mark.asyncio
async def test_handle_incoming_classifies_and_publishes_event(pool):
    service, contacts, _, event_bus = make_service(pool)
    received: list[Event] = []

    async def record(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(record, EventType.COMMUNICATION_RECEIVED)

    comm = await service.handle_incoming(contact_id=None, channel="email", text="Here is the invoice for last month.")
    assert comm.category == Category.CLIENT
    assert len(received) == 1


@pytest.mark.asyncio
async def test_propose_reply_routine_auto_approves_but_is_not_transmitted(pool):
    service, contacts, confirmations, _ = make_service(pool)
    contact = await contacts.create(Contact(id=str(uuid.uuid4()), name="Alice", role=ContactRole.CLIENT, channel="email"))

    comm, delivered, detail = await service.propose_reply(contact_id=contact.id, channel="email", draft_text="Thanks, got it!")

    assert comm.policy_action == "AUTO"
    assert confirmations.list_pending() == []
    assert delivered is False
    assert "no real transmission channel" in detail


@pytest.mark.asyncio
async def test_propose_reply_contract_intent_asks_for_approval(pool):
    service, contacts, confirmations, _ = make_service(pool)
    contact = await contacts.create(Contact(id=str(uuid.uuid4()), name="Bob", role=ContactRole.CLIENT, channel="email"))

    async def approve_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.approve(pending.id)

    (comm, delivered, detail), _ = await asyncio.gather(
        service.propose_reply(contact_id=contact.id, channel="email", draft_text="Here is the signed contract, please review the agreement terms."),
        approve_soon(),
    )
    assert comm.policy_action == "ASK"
    assert delivered is False  # still not transmitted, but WAS approved


@pytest.mark.asyncio
async def test_propose_reply_rejected_is_blocked(pool):
    service, contacts, confirmations, _ = make_service(pool)
    contact = await contacts.create(Contact(id=str(uuid.uuid4()), name="Carol", role=ContactRole.CLIENT, channel="email"))

    async def reject_soon():
        pending = await _wait_for_pending(confirmations)
        await confirmations.reject(pending.id)

    (comm, delivered, detail), _ = await asyncio.gather(
        service.propose_reply(contact_id=contact.id, channel="email", draft_text="I guarantee we will hit that deadline no matter what."),
        reject_soon(),
    )
    assert comm.policy_action == "BLOCKED"
    assert delivered is False


@pytest.mark.asyncio
async def test_propose_reply_requires_an_active_contact(pool):
    service, contacts, _, _ = make_service(pool)
    with pytest.raises(ValueError):
        await service.propose_reply(contact_id=str(uuid.uuid4()), channel="email", draft_text="hi")
