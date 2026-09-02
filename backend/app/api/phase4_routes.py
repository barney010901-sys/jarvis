"""Phase 4 REST surface (foundation increment 4B-4E): self-modification
proposals, capability registry search/registration, and autonomy
mode/resource budgets. Same conventions as phase3_routes.py: thin routing
only, 503 (not a crash or fake data) when a service isn't configured.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependency import require_bearer_token
from app.autonomy.budget_models import BudgetKind
from app.autonomy.models import AutonomyMode
from app.deps import (
    get_autonomy_mode_service,
    get_capability_service,
    get_resource_budget_service,
    get_selfcode_service,
)

router = APIRouter(dependencies=[Depends(require_bearer_token)])


def _require(service: Any, name: str) -> Any:
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name} is not configured — Postgres and/or Claude are unavailable in this deployment")
    return service


# --- Self-modification proposals ---
# NOTE: like /wallet/transactions in Phase 3, POST /selfcode/proposals
# awaits the full policy decision (including the confirmation gate) before
# returning — approve/reject via the existing POST /confirmations/{id}/...
# endpoint. See docs/PHASE_4_AUDIT.md §17(b): self_modification is NEVER
# auto-approved, so this endpoint always waits for a human response.


class SelfModificationProposalRequest(BaseModel):
    title: str
    reason: str
    diff: str
    test_plan: str
    rollback_plan: str
    affected_components: list[str] = []
    risk: str = "unknown"


@router.post("/selfcode/proposals")
async def propose_self_modification(body: SelfModificationProposalRequest) -> dict[str, Any]:
    service = _require(get_selfcode_service(), "selfcode")
    proposal = await service.propose(
        title=body.title, reason=body.reason, diff=body.diff, test_plan=body.test_plan,
        rollback_plan=body.rollback_plan, affected_components=body.affected_components, risk=body.risk,
    )
    return {
        "id": proposal.id, "title": proposal.title, "status": proposal.status.value,
        "approval_id": proposal.approval_id,
    }


@router.get("/selfcode/proposals")
async def list_self_modification_proposals() -> dict[str, Any]:
    service = _require(get_selfcode_service(), "selfcode")
    proposals = await service.list_proposals()
    return {
        "proposals": [
            {
                "id": p.id, "title": p.title, "reason": p.reason, "risk": p.risk,
                "status": p.status.value, "approval_id": p.approval_id,
                "affected_components": p.affected_components,
                "created_at": p.created_at.isoformat(), "resolved_at": p.resolved_at.isoformat() if p.resolved_at else None,
            }
            for p in proposals
        ]
    }


# --- Capability registry ---


class RegisterCapabilityRequest(BaseModel):
    name: str
    type: str
    purpose: str
    owner: str | None = None


class ComposeCapabilityRequest(BaseModel):
    name: str
    purpose: str
    component_ids: list[str]
    owner: str | None = None


@router.get("/capability-registry/search")
async def search_capability_registry(q: str) -> dict[str, Any]:
    service = _require(get_capability_service(), "capabilities")
    results = await service.search(q)
    return {"results": [{"id": c.id, "name": c.name, "type": c.type, "purpose": c.purpose, "usage_count": c.usage_count, "success_rate_observed": c.success_rate_observed} for c in results]}


@router.post("/capability-registry/register")
async def register_capability(body: RegisterCapabilityRequest) -> dict[str, Any]:
    service = _require(get_capability_service(), "capabilities")
    capability = await service.register_internal(name=body.name, type=body.type, purpose=body.purpose, owner=body.owner)
    return {"id": capability.id, "name": capability.name, "status": capability.status}


@router.post("/capability-registry/compose")
async def compose_capability(body: ComposeCapabilityRequest) -> dict[str, Any]:
    service = _require(get_capability_service(), "capabilities")
    capability = await service.compose(name=body.name, purpose=body.purpose, component_ids=body.component_ids, owner=body.owner)
    return {"id": capability.id, "name": capability.name, "composed_of": capability.composed_of}


# --- Autonomy mode + resource budgets ---


class AutonomyModeRequest(BaseModel):
    mode: str  # one of AutonomyMode's names, e.g. "AUTONOMOUS"


@router.get("/autonomy/mode")
async def get_autonomy_mode() -> dict[str, Any]:
    service = _require(get_autonomy_mode_service(), "autonomy")
    mode = await service.get_mode()
    return {"mode": mode.name, "value": int(mode)}


@router.post("/autonomy/mode")
async def set_autonomy_mode(body: AutonomyModeRequest) -> dict[str, Any]:
    service = _require(get_autonomy_mode_service(), "autonomy")
    try:
        mode = AutonomyMode[body.mode.upper()]
    except KeyError:
        raise HTTPException(status_code=422, detail=f"unknown autonomy mode: {body.mode!r}")
    await service.set_mode(mode)
    return {"mode": mode.name, "value": int(mode)}


class BudgetLimitRequest(BaseModel):
    scope: str
    kind: str
    limit_amount: float


@router.post("/autonomy/budgets")
async def set_budget_limit(body: BudgetLimitRequest) -> dict[str, Any]:
    service = _require(get_resource_budget_service(), "autonomy")
    try:
        kind = BudgetKind(body.kind)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown budget kind: {body.kind!r}")
    budget = await service.set_limit(body.scope, kind, body.limit_amount)
    return {"scope": budget.scope, "kind": budget.kind.value, "limit_amount": budget.limit_amount, "used_amount": budget.used_amount}


@router.get("/autonomy/budgets/{scope}/{kind}")
async def get_budget_remaining(scope: str, kind: str) -> dict[str, Any]:
    service = _require(get_resource_budget_service(), "autonomy")
    try:
        budget_kind = BudgetKind(kind)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown budget kind: {kind!r}")
    remaining = await service.remaining(scope, budget_kind)
    if remaining is None:
        return {"scope": scope, "kind": kind, "configured": False, "remaining": None}
    return {"scope": scope, "kind": kind, "configured": True, "remaining": remaining}
