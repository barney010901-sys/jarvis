"""Phase 3 REST surface for the Android command-center screens (sections
59-73). Thin routing glue only — every real decision/check/audit lives in
the domain service modules (app/policy, app/wallet, app/communication,
app/escalation, app/business, app/capabilities, app/health). All
endpoints require the bearer token except where noted.

If a domain service isn't configured (no Postgres/Claude — see
docs/DECISIONS.md), its endpoints return 503 rather than crashing or
faking data.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependency import require_bearer_token
from app.communication.models import Contact, ContactRole
from app.deps import (
    get_approval_store,
    get_audit_store,
    get_business_service,
    get_business_store,
    get_capability_service,
    get_capability_store,
    get_communication_service,
    get_contact_store,
    get_escalation_service,
    get_health_service,
    get_knowledge_service,
    get_long_term_memory,
    get_policy_engine,
    get_profile_store,
    get_suggestion_service,
    get_task_store,
    get_wallet_service,
    get_wallet_store,
)
from app.escalation.models import Urgency
from app.policy.models import AutonomyLevel
from app.suggestions.models import Priority

router = APIRouter(dependencies=[Depends(require_bearer_token)])


def _require(service: Any, name: str) -> Any:
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name} is not configured — Postgres and/or Claude are unavailable in this deployment")
    return service


# --- Dashboard (section 64) ---


@router.get("/dashboard")
async def dashboard() -> dict[str, Any]:
    health = await get_health_service().check_all()
    result: dict[str, Any] = {
        "system_health": [{"component": c.component, "status": c.status.value, "detail": c.detail} for c in health],
    }

    suggestions = get_suggestion_service()
    if suggestions is not None:
        pending = await suggestions.list_actionable(min_priority=Priority.MEDIUM)
        result["suggestions"] = [{"id": s.id, "title": s.title, "priority": s.priority.value, "reason": s.reason} for s in pending]
    else:
        result["suggestions"] = []

    approvals = get_approval_store()
    if approvals is not None:
        pending_approvals = await approvals.list_pending()
        result["pending_approvals"] = [{"id": a.id, "kind": a.kind, "title": a.title, "risk": a.risk} for a in pending_approvals]
    else:
        result["pending_approvals"] = []

    wallet_store = get_wallet_store()
    if wallet_store is not None:
        account = await wallet_store.get_or_create_account()
        weekly_spent = await wallet_store.weekly_spent(account.id)
        result["wallet"] = {"balance_usd": account.balance_usd, "weekly_spent": weekly_spent, "weekly_limit": account.weekly_limit_usd}
    else:
        result["wallet"] = None

    business = get_business_service()
    if business is not None:
        summary = await business.sustainability_summary()
        result["business"] = {"revenue_total_usd": summary.revenue_total_usd, "surplus_usd": summary.surplus_usd, "stage": summary.stage}
    else:
        result["business"] = None

    return result


# --- System health (section 63) ---


@router.get("/system/health")
async def system_health() -> dict[str, Any]:
    checks = await get_health_service().check_all()
    return {"components": [{"component": c.component, "status": c.status.value, "detail": c.detail} for c in checks]}


# --- Approval Center (section 70) ---
# Approve/reject reuse the existing POST /confirmations/{id}/approve|reject
# (an approval's id IS the underlying confirmation id — see
# app/policy/engine.py) — no second endpoint pair for the same gate.


@router.get("/approvals")
async def list_approvals(status: str | None = Query(default=None)) -> dict[str, Any]:
    store = _require(get_approval_store(), "approvals")
    items = await store.list_pending() if status == "PENDING" else await store.list_recent()
    return {"approvals": [
        {"id": a.id, "kind": a.kind, "title": a.title, "description": a.description, "risk": a.risk,
         "cost_usd": a.cost_usd, "status": a.status, "task_id": a.task_id, "requested_at": a.requested_at.isoformat()}
        for a in items
    ]}


# --- Audit Center (section 71) ---


@router.get("/audit")
async def list_audit(task_id: str | None = Query(default=None), component: str | None = Query(default=None), limit: int = Query(default=100, le=500)) -> dict[str, Any]:
    store = get_audit_store()
    entries = await store.list_for_task(task_id, limit=limit) if task_id else await store.list_recent(component=component, limit=limit)
    return {"entries": [
        {"event_type": e.event_type, "component": e.component, "action": e.action, "task_id": e.task_id,
         "result": e.result, "confirmation_state": e.confirmation_state, "created_at": e.created_at.isoformat()}
        for e in entries
    ]}


# --- Memory + Knowledge search (section 72) ---


@router.get("/memory/search")
async def search_memory(q: str = Query(...), project: str = Query(default="default"), limit: int = Query(default=10, le=50)) -> dict[str, Any]:
    long_term = get_long_term_memory()
    facts = await long_term.search(project, q, limit=limit)
    result: dict[str, Any] = {"memories": [{"id": f.id, "content": f.content, "tags": f.tags} for f in facts]}

    knowledge = get_knowledge_service()
    if knowledge is not None:
        records = await knowledge.retrieve_relevant(project=project, query=q, limit=limit)
        result["knowledge"] = [
            {"id": r.id, "category": r.category.value, "title": r.title, "content": r.content, "confidence": r.confidence, "status": r.status.value}
            for r in records
        ]
    else:
        result["knowledge"] = []
    return result


# --- Task Center (section 13) ---


@router.get("/tasks")
async def list_tasks(session_id: str | None = Query(default=None), limit: int = Query(default=50, le=200)) -> dict[str, Any]:
    store = get_task_store()
    tasks = await store.list_recent(session_id=session_id, limit=limit)
    return {"tasks": [
        {"id": t.id, "project": t.project, "request": t.request, "status": t.status.value, "error": t.error,
         "created_at": t.created_at.isoformat(), "completed_at": t.completed_at.isoformat() if t.completed_at else None}
        for t in tasks
    ]}


# --- Project / Goal Center (sections 11-12) ---


@router.get("/projects")
async def list_projects() -> dict[str, Any]:
    profile = _require(get_profile_store(), "profile")
    projects = await profile.list_projects()
    return {"projects": [
        {"slug": p.slug, "name": p.name, "status": p.status, "goals": p.goals, "technologies": p.technologies, "last_active_at": p.last_active_at.isoformat()}
        for p in projects
    ]}


@router.get("/projects/{slug}/goals")
async def list_project_goals(slug: str) -> dict[str, Any]:
    profile = _require(get_profile_store(), "profile")
    goals = await profile.list_goals(project_slug=slug)
    return {"goals": [{"id": g.id, "title": g.title, "description": g.description, "status": g.status} for g in goals]}


# --- Wallet Center (sections 40-45, 62) ---


class WalletTransactionRequest(BaseModel):
    amount_usd: float
    vendor: str
    category: str
    purpose: str


@router.get("/wallet")
async def wallet_overview() -> dict[str, Any]:
    store = _require(get_wallet_store(), "wallet")
    account = await store.get_or_create_account()
    weekly_spent = await store.weekly_spent(account.id)
    monthly_spent = await store.monthly_spent(account.id)
    transactions = await store.list_transactions(account.id, limit=50)
    return {
        "balance_usd": account.balance_usd,
        "weekly_limit_usd": account.weekly_limit_usd,
        "weekly_spent_usd": weekly_spent,
        "monthly_limit_usd": account.monthly_limit_usd,
        "monthly_spent_usd": monthly_spent,
        "per_transaction_limit_usd": account.per_transaction_limit_usd,
        "approved_categories": account.approved_categories,
        "blocked_categories": account.blocked_categories,
        "approved_vendors": account.approved_vendors,
        "transactions": [
            {"id": t.id, "amount_usd": t.amount_usd, "vendor": t.vendor, "category": t.category, "purpose": t.purpose,
             "policy_decision": t.policy_decision.value, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in transactions
        ],
    }


class WalletLimitsRequest(BaseModel):
    weekly_limit_usd: float | None = None
    monthly_limit_usd: float | None = None
    per_transaction_limit_usd: float | None = None
    approval_threshold_usd: float | None = None
    approved_categories: list[str] | None = None
    blocked_categories: list[str] | None = None
    approved_vendors: list[str] | None = None


@router.post("/wallet/limits")
async def update_wallet_limits(body: WalletLimitsRequest) -> dict[str, Any]:
    store = _require(get_wallet_store(), "wallet")
    account = await store.get_or_create_account()
    updated = await store.update_limits(account.id, **body.model_dump(exclude_none=True))
    return {"weekly_limit_usd": updated.weekly_limit_usd, "monthly_limit_usd": updated.monthly_limit_usd, "per_transaction_limit_usd": updated.per_transaction_limit_usd}


@router.post("/wallet/transactions")
async def propose_wallet_transaction(body: WalletTransactionRequest) -> dict[str, Any]:
    service = _require(get_wallet_service(), "wallet")
    result = await service.propose_transaction(amount_usd=body.amount_usd, vendor=body.vendor, category=body.category, purpose=body.purpose)
    return {"approved": result.approved, "transaction_id": result.transaction_id, "reason": result.reason, "balance_usd": result.balance_usd, "policy_decision": result.policy_decision.value}


# --- Business Center (sections 46-52) ---


@router.get("/business/summary")
async def business_summary() -> dict[str, Any]:
    service = _require(get_business_service(), "business")
    summary = await service.sustainability_summary()
    return {"revenue_total_usd": summary.revenue_total_usd, "monthly_operating_cost_usd": summary.monthly_operating_cost_usd, "surplus_usd": summary.surplus_usd, "stage": summary.stage}


@router.get("/business/opportunities")
async def business_opportunities(limit: int = Query(default=20, le=100)) -> dict[str, Any]:
    service = _require(get_business_service(), "business")
    ranked = await service.ranked_opportunities(limit=limit)
    return {"opportunities": [
        {"id": o.id, "title": o.title, "description": o.description, "score": round(score, 2), "status": o.status}
        for o, score in ranked
    ]}


@router.get("/business/customers")
async def business_customers() -> dict[str, Any]:
    store = _require(get_business_store(), "business")
    customers = await store.list_customers()
    return {"customers": [{"id": c.id, "name": c.name, "stage": c.stage, "notes": c.notes} for c in customers]}


# --- Capability discovery (sections 18-20) ---


@router.get("/capabilities")
async def list_capabilities() -> dict[str, Any]:
    store = _require(get_capability_store(), "capabilities")
    items = await store.list()
    return {"capabilities": [
        {"id": c.id, "name": c.name, "type": c.type, "purpose": c.purpose, "source": c.source, "verification_status": c.verification_status.value}
        for c in items
    ]}


class CapabilitySearchRequest(BaseModel):
    query: str
    purpose: str
    limit: int = 5


@router.post("/capabilities/search")
async def search_capabilities(body: CapabilitySearchRequest) -> dict[str, Any]:
    service = _require(get_capability_service(), "capabilities")
    try:
        results = await service.search_github(body.query, purpose=body.purpose, limit=body.limit)
    except Exception as exc:  # noqa: BLE001 - a network/API failure is a 502, not a crash
        raise HTTPException(status_code=502, detail=f"GitHub search failed: {exc}") from exc
    return {"capabilities": [{"id": c.id, "name": c.name, "source": c.source, "verification_status": c.verification_status.value} for c in results]}


# --- Contacts + Escalation settings (sections 33-39) ---


class ContactRequest(BaseModel):
    name: str
    relationship: str = ""
    role: ContactRole = ContactRole.OTHER
    channel: str = "unknown"
    allowed_categories: list[str] = []
    disclosure_limit: str = "minimum necessary"


@router.get("/contacts")
async def list_contacts() -> dict[str, Any]:
    store = _require(get_contact_store(), "contacts")
    contacts = await store.list(active_only=False)
    return {"contacts": [
        {"id": c.id, "name": c.name, "relationship": c.relationship, "role": c.role.value, "channel": c.channel, "active": c.active}
        for c in contacts
    ]}


@router.post("/contacts")
async def create_contact(body: ContactRequest) -> dict[str, Any]:
    store = _require(get_contact_store(), "contacts")
    contact = await store.create(
        Contact(id=str(uuid.uuid4()), name=body.name, relationship=body.relationship, role=body.role, channel=body.channel,
                allowed_categories=body.allowed_categories, disclosure_limit=body.disclosure_limit)
    )
    return {"id": contact.id, "name": contact.name, "role": contact.role.value}


class EscalationTestRequest(BaseModel):
    reason: str
    urgency: Urgency = Urgency.HIGH
    user_available: bool = False


@router.post("/escalation/evaluate")
async def evaluate_escalation(body: EscalationTestRequest) -> dict[str, Any]:
    service = _require(get_escalation_service(), "escalation")
    decision = await service.evaluate(reason=body.reason, urgency=body.urgency, user_available=body.user_available)
    return {"action": decision.action, "reason": decision.reason, "contact": decision.contact.name if decision.contact else None, "delivered": decision.delivered}


# --- Autonomy settings (sections 28-29, 61) ---


@router.get("/settings/autonomy")
async def get_autonomy() -> dict[str, Any]:
    engine = _require(get_policy_engine(), "policy engine")
    level = await engine.autonomy_level()
    return {"level": level.value, "name": level.name}


class AutonomyRequest(BaseModel):
    level: int


@router.post("/settings/autonomy")
async def set_autonomy(body: AutonomyRequest) -> dict[str, Any]:
    engine = _require(get_policy_engine(), "policy engine")
    try:
        level = AutonomyLevel(body.level)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid autonomy level: {body.level}") from exc
    await engine.set_autonomy_level(level)
    return {"level": level.value, "name": level.name}
