"""The ONE centralized policy engine (section 28). Every external or
sensitive action — wallet spending, outbound communication, installing a
discovered capability, a destructive operation — is expressed as a
`PolicyRequest` and resolved here:

    REQUEST -> RISK -> PERMISSION -> POLICY -> LIMIT -> CONTEXT -> ALLOW/DENY/ASK

"RISK"/"LIMIT" are computed by the calling domain service (it knows its
own numbers — a wallet transaction's limit check looks nothing like a
communication's); this engine owns "PERMISSION" (autonomy level),
"POLICY" (the `policies` table / pre-approval lookup), and the ASK gate
itself, which reuses the existing `ConfirmationManager` — there is no
second confirmation mechanism (see docs/DECISIONS.md).
"""
from __future__ import annotations

import logging
import uuid

from app.events.bus import EventBus
from app.permissions.manager import ConfirmationManager, ConfirmationRejected
from app.policy.approvals import Approval, ApprovalStore
from app.policy.models import DEFAULT_AUTONOMY_LEVEL, AutonomyLevel, Decision, PolicyRequest, PolicyResult
from app.policy.store import PolicyStore
from app.profile.interface import ProfileStore

logger = logging.getLogger(__name__)

_AUTONOMY_PREFERENCE_KEY = "autonomy_level"


class PolicyEngine:
    def __init__(
        self,
        *,
        policy_store: PolicyStore,
        approval_store: ApprovalStore,
        confirmation_manager: ConfirmationManager,
        event_bus: EventBus,
        profile_store: ProfileStore | None = None,
    ) -> None:
        self._policies = policy_store
        self._approvals = approval_store
        self._confirmations = confirmation_manager
        self._event_bus = event_bus
        self._profile = profile_store

    async def autonomy_level(self) -> AutonomyLevel:
        if self._profile is None:
            return DEFAULT_AUTONOMY_LEVEL
        pref = await self._profile.get_preference(_AUTONOMY_PREFERENCE_KEY)
        if pref is None:
            return DEFAULT_AUTONOMY_LEVEL
        try:
            return AutonomyLevel(int(pref.value))
        except (TypeError, ValueError):
            return DEFAULT_AUTONOMY_LEVEL

    async def set_autonomy_level(self, level: AutonomyLevel) -> None:
        if self._profile is None:
            raise RuntimeError("no ProfileStore configured — cannot persist autonomy level")
        await self._profile.set_preference(_AUTONOMY_PREFERENCE_KEY, int(level))

    async def evaluate(self, request: PolicyRequest) -> PolicyResult:
        # RED: categorically forbidden — never even ask (blocked category/
        # vendor, or a domain service classified this as outright unsafe).
        if request.hard_block:
            logger.warning("PolicyEngine DENY (hard_block): %s — %s", request.kind, request.title)
            return PolicyResult(Decision.DENY, reason="blocked by policy: this category/action is never permitted")

        autonomy = await self.autonomy_level()
        if await self._auto_approved(request, autonomy):
            return PolicyResult(Decision.ALLOW, reason=f"auto-approved at autonomy level {autonomy.name}")

        return await self._ask(request)

    async def _auto_approved(self, request: PolicyRequest, autonomy: AutonomyLevel) -> bool:
        # Phase 4: a proposal to modify Jarvis's own running code is never
        # auto-approved, at ANY autonomy level — confirmed by the user
        # 2026-09-02, see docs/PHASE_4_AUDIT.md §17(b). This is a hard
        # carve-out, not a default, so no autonomy-level setting (present
        # or future) can silently bypass it.
        if request.kind == "self_modification":
            return False

        # LEVEL_1 (suggest-only) and LEVEL_2 (prepare-only) never auto-execute.
        if autonomy in (AutonomyLevel.LEVEL_1_SUGGEST, AutonomyLevel.LEVEL_2_PREPARE):
            return False

        low_and_reversible = request.risk == "low" and request.reversible

        if autonomy == AutonomyLevel.LEVEL_3_ASK:
            return low_and_reversible

        if autonomy == AutonomyLevel.LEVEL_4_EXECUTE_APPROVED:
            if low_and_reversible:
                return True
            return await self._has_preapproval(request)

        if autonomy == AutonomyLevel.LEVEL_5_SAFE_AUTOMATION:
            if request.risk in ("low", "medium") and request.reversible:
                return True
            return await self._has_preapproval(request)

        return False

    async def _has_preapproval(self, request: PolicyRequest) -> bool:
        if not request.preapproval_key:
            return False
        return await self._policies.is_auto_approved(request.preapproval_key)

    async def _ask(self, request: PolicyRequest) -> PolicyResult:
        approval_id = str(uuid.uuid4())
        await self._approvals.create(
            Approval(
                id=approval_id,
                kind=request.kind,
                title=request.title,
                description=request.description,
                risk=request.risk,
                payload=request.payload,
                cost_usd=request.cost_usd,
                task_id=request.task_id,
            )
        )

        try:
            await self._confirmations.request_confirmation(
                tool_name=f"policy.{request.kind}",
                description=request.description,
                task_id=request.task_id,
                details={**request.payload, "approval_id": approval_id, "cost_usd": request.cost_usd},
            )
        except ConfirmationRejected:
            await self._approvals.set_status(approval_id, "REJECTED")
            return PolicyResult(Decision.DENY, reason="user rejected the request", approval_id=approval_id)

        await self._approvals.set_status(approval_id, "APPROVED")
        return PolicyResult(Decision.ALLOW, reason="user approved the request", approval_id=approval_id)
