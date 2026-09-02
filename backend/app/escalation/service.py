"""Unavailable-user mode + escalation (sections 34-36). Never invents a
contact: escalation only ever reaches a `Contact` the user explicitly
configured with role PRIMARY/SECONDARY/EMERGENCY (section 35).
Transmission goes through the same not-yet-implemented channel adapter as
`CommunicationService` — the decision/disclosure-construction/audit logic
is real; nothing is actually sent over a real channel yet.
"""
from __future__ import annotations

import logging
import uuid

from app.communication.channel import CommunicationChannelAdapter
from app.communication.models import ContactRole
from app.communication.store import ContactStore
from app.escalation.models import EscalationDecision, EscalationEvent, Urgency
from app.escalation.store import EscalationStore
from app.events.bus import EventBus
from app.events.models import Event, EventType

logger = logging.getLogger(__name__)

_ESCALATION_ROLE_PRIORITY = (ContactRole.PRIMARY, ContactRole.SECONDARY, ContactRole.EMERGENCY)


class EscalationService:
    def __init__(
        self,
        *,
        contacts: ContactStore,
        store: EscalationStore,
        channel: CommunicationChannelAdapter,
        event_bus: EventBus,
        user_display_name: str = "the user",
    ) -> None:
        self._contacts = contacts
        self._store = store
        self._channel = channel
        self._event_bus = event_bus
        self._user_display_name = user_display_name

    async def evaluate(
        self, *, reason: str, urgency: Urgency, user_available: bool, task_id: str | None = None
    ) -> EscalationDecision:
        if user_available:
            return EscalationDecision(action="NOT_NEEDED", reason="user is available")

        if urgency == Urgency.LOW:
            return EscalationDecision(action="WAIT", reason="low urgency — waiting for the user")

        if urgency == Urgency.MEDIUM:
            return EscalationDecision(action="QUEUE", reason="medium urgency — queued to notify the user later")

        # HIGH urgency: find an authorized escalation contact, preferring
        # PRIMARY, then SECONDARY, then EMERGENCY. Never invents one.
        contacts = await self._contacts.list(active_only=True)
        by_role = {c.role: c for c in contacts if c.role in _ESCALATION_ROLE_PRIORITY}
        contact = next((by_role[role] for role in _ESCALATION_ROLE_PRIORITY if role in by_role), None)

        if contact is None:
            event = await self._store.create(
                EscalationEvent(id=str(uuid.uuid4()), contact_id=None, reason=reason, urgency=urgency, disclosure="", task_id=task_id, result="NO_AUTHORIZED_CONTACT")
            )
            return EscalationDecision(action="NO_AUTHORIZED_CONTACT", reason="no PRIMARY/SECONDARY/EMERGENCY contact is configured", event_id=event.id)

        disclosure = (
            f"{contact.name}, {self._user_display_name} is currently unavailable. Jarvis received an "
            f"important, time-sensitive matter: {reason}. Could you please let them know?"
        )
        event = await self._store.create(
            EscalationEvent(id=str(uuid.uuid4()), contact_id=contact.id, reason=reason, urgency=urgency, disclosure=disclosure, task_id=task_id, result="PENDING")
        )

        try:
            result = await self._channel.send(channel=contact.channel, destination=contact.channel, message=disclosure)
            delivered, detail = result.delivered, result.detail
        except NotImplementedError as exc:
            delivered, detail = False, str(exc)

        final_result = "SENT" if delivered else "LOGGED_NOT_SENT"
        await self._store.set_result(event.id, final_result)
        await self._event_bus.publish(
            Event(
                type=EventType.ESCALATION_TRIGGERED,
                task_id=task_id,
                payload={"escalation_id": event.id, "contact_id": contact.id, "urgency": urgency.value, "delivered": delivered, "detail": detail},
            )
        )
        return EscalationDecision(action="ESCALATED", reason=detail, contact=contact, message=disclosure, event_id=event.id, delivered=delivered)
