"""CommunicationService: classification + the PolicyEngine gate for
outgoing replies. Reading/recording an incoming message never needs
approval (it's a passive, safe operation); *replying* does, based on the
detected intent (section 31). See channel.py for why nothing is ever
actually transmitted yet.
"""
from __future__ import annotations

import logging
import uuid

from app.communication.channel import CommunicationChannelAdapter
from app.communication.classifier import classify_category, classify_intent, risk_for_intent
from app.communication.models import Category, Communication, Direction
from app.communication.store import CommunicationStore, ContactStore
from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.policy.models import Decision, PolicyRequest
from app.policy.engine import PolicyEngine

logger = logging.getLogger(__name__)


class CommunicationService:
    def __init__(
        self,
        *,
        contacts: ContactStore,
        communications: CommunicationStore,
        policy_engine: PolicyEngine,
        channel: CommunicationChannelAdapter,
        event_bus: EventBus,
    ) -> None:
        self._contacts = contacts
        self._communications = communications
        self._policy = policy_engine
        self._channel = channel
        self._event_bus = event_bus

    async def handle_incoming(
        self, *, contact_id: str | None, channel: str, text: str, task_id: str | None = None
    ) -> Communication:
        category = classify_category(text)
        comm = await self._communications.create(
            Communication(
                id=str(uuid.uuid4()), direction=Direction.INCOMING, category=category,
                summary=text[:500], policy_action="AUTO", contact_id=contact_id, channel=channel, task_id=task_id,
            )
        )
        await self._event_bus.publish(
            Event(type=EventType.COMMUNICATION_RECEIVED, task_id=task_id, payload={"communication_id": comm.id, "category": category.value, "contact_id": contact_id})
        )
        return comm

    async def propose_reply(
        self, *, contact_id: str, channel: str, draft_text: str, task_id: str | None = None
    ) -> tuple[Communication, bool, str]:
        """Returns (communication_record, delivered, detail). `delivered`
        is always False in Phase 3 (see channel.py) unless a real adapter
        is wired in later — the policy decision itself is real."""
        contact = await self._contacts.get(contact_id)
        if contact is None or not contact.active:
            raise ValueError(f"no active contact with id {contact_id}")

        intent = classify_intent(draft_text)
        category = classify_category(draft_text)
        risk, reversible = risk_for_intent(intent)

        request = PolicyRequest(
            kind="communication",
            title=f"reply to {contact.name}",
            description=draft_text[:300],
            risk=risk,
            reversible=reversible,
            task_id=task_id,
            payload={"contact_id": contact_id, "intent": intent, "category": category.value},
            preapproval_key=f"communication:{intent}",
        )
        decision = await self._policy.evaluate(request)

        if decision.decision == Decision.ALLOW:
            policy_action = "ASK" if decision.approval_id else "AUTO"
        else:
            policy_action = "BLOCKED"

        comm = await self._communications.create(
            Communication(
                id=str(uuid.uuid4()), direction=Direction.OUTGOING, category=category, summary=draft_text[:500],
                policy_action=policy_action, contact_id=contact_id, channel=channel, task_id=task_id, approval_id=decision.approval_id,
            )
        )

        if decision.decision != Decision.ALLOW:
            return comm, False, decision.reason

        try:
            result = await self._channel.send(channel=channel, destination=contact.channel, message=draft_text)
        except NotImplementedError as exc:
            logger.info("Reply to %s approved but not transmitted (no real channel configured): %s", contact.name, exc)
            return comm, False, "approved, but no real transmission channel is configured yet"

        if result.delivered:
            await self._event_bus.publish(
                Event(type=EventType.COMMUNICATION_SENT, task_id=task_id, payload={"communication_id": comm.id, "contact_id": contact_id})
            )
        return comm, result.delivered, result.detail
