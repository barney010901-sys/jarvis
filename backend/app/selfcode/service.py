"""SelfCodeService: the only path by which a change to Jarvis's own code
can be proposed. `propose()` always creates a durable proposal and always
routes it through `PolicyEngine` with `kind="self_modification"` — which
is hard-coded to never auto-approve regardless of autonomy level or mode
(see `app/policy/engine.py`). Approval happens through the existing
Approval Center / ConfirmationManager, exactly like every other ASK
decision — there is no separate approval mechanism for self-modification.

`apply()`/`rollback()` deliberately raise `NotImplementedError`: this
sandbox has no isolated execution environment or snapshot/rollback
tooling yet (see docs/PHASE_4_AUDIT.md §16/§17b), and per that same
audit's Self-Update Protocol, that tooling must exist and be tested
*before* an approved proposal is ever actually applied to the running
system. Faking "applied" would violate the project's own REAL/MOCKED/
NOT_TESTED discipline — so an APPROVED proposal today is a real, audited
decision record, not yet an executed change.
"""
from __future__ import annotations

import logging
import uuid

from app.events.bus import EventBus
from app.policy.engine import PolicyEngine
from app.policy.models import Decision, PolicyRequest
from app.selfcode.models import ProposalStatus, SelfModificationProposal
from app.selfcode.store import SelfModificationStore

logger = logging.getLogger(__name__)


class SelfCodeService:
    def __init__(self, store: SelfModificationStore, policy_engine: PolicyEngine, event_bus: EventBus) -> None:
        self._store = store
        self._policy = policy_engine
        self._event_bus = event_bus

    async def propose(
        self,
        *,
        title: str,
        reason: str,
        diff: str,
        test_plan: str,
        rollback_plan: str,
        affected_components: list[str] | None = None,
        risk: str = "unknown",
        task_id: str | None = None,
    ) -> SelfModificationProposal:
        proposal = await self._store.create(
            SelfModificationProposal(
                id=str(uuid.uuid4()),
                title=title,
                reason=reason,
                diff=diff,
                test_plan=test_plan,
                rollback_plan=rollback_plan,
                affected_components=affected_components or [],
                risk=risk,
            )
        )

        result = await self._policy.evaluate(
            PolicyRequest(
                kind="self_modification",
                title=title,
                description=reason,
                risk=risk,
                reversible=False,  # code changes are never treated as auto-reversible
                task_id=task_id,
                payload={
                    "proposal_id": proposal.id,
                    "affected_components": affected_components or [],
                    "test_plan": test_plan,
                    "rollback_plan": rollback_plan,
                },
            )
        )

        if result.approval_id:
            await self._store.set_approval(proposal.id, result.approval_id)

        if result.decision == Decision.ALLOW:
            await self._store.set_status(proposal.id, ProposalStatus.APPROVED, resolved=True)
            logger.info("self-modification proposal %s approved by user — NOT applied (no sandbox/rollback infra yet)", proposal.id)
        else:
            await self._store.set_status(proposal.id, ProposalStatus.REJECTED, resolved=True)

        return await self._store.get(proposal.id)  # type: ignore[return-value]

    async def list_proposals(self, *, limit: int = 100) -> list[SelfModificationProposal]:
        return await self._store.list(limit=limit)

    async def apply(self, proposal_id: str) -> None:
        proposal = await self._store.get(proposal_id)
        if proposal is None:
            raise ValueError(f"no such proposal: {proposal_id}")
        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError(f"proposal {proposal_id} is not APPROVED (status={proposal.status.value}) — cannot apply")
        raise NotImplementedError(
            "Applying a self-modification proposal to the running system requires an isolated "
            "sandbox and snapshot/rollback tooling that does not exist yet in this build — see "
            "docs/PHASE_4_AUDIT.md §16/§17(b). The proposal is recorded and APPROVED; it is not "
            "executed. Build and test that infrastructure (Phase 4Q+) before implementing this."
        )

    async def rollback(self, proposal_id: str) -> None:
        raise NotImplementedError(
            "Rollback requires the same snapshot infrastructure as apply() — not implemented yet, "
            "see docs/PHASE_4_AUDIT.md §16/§17(b)."
        )
