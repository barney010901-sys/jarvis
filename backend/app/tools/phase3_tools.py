"""Phase 3 tools: wallet spending, communication replies, capability
research, business opportunities, system health — registered into the
SAME `ToolRegistry` used since Phase 1 (see docs/DECISIONS.md, "Phase 3
capabilities are tools, not a parallel orchestrator path"). This is how
Claude actually gets to use the wallet/communication/business/capability
services through the existing planner -> tool-execution flow, rather than
special-casing new code paths into the orchestrator.

Each tool here is a thin adapter over its service — all the real logic
(policy gating, classification, scoring) lives in the service modules;
these classes only translate `Tool.execute(**kwargs)` into a service call.
"""
from __future__ import annotations

from typing import Any

from app.business.service import BusinessService
from app.capabilities.service import CapabilityDiscoveryService
from app.communication.service import CommunicationService
from app.health.service import HealthService
from app.permissions.models import PermissionLevel
from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry
from app.wallet.service import WalletService


class WalletProposeTransactionTool(Tool):
    def __init__(self, service: WalletService) -> None:
        super().__init__(
            name="wallet.propose_transaction",
            description="Propose an operational expense from Jarvis's wallet (e.g. a hosting bill, a new API subscription). Gated by the wallet's policy/limits — may require explicit user approval.",
            input_schema={
                "type": "object",
                "properties": {
                    "amount_usd": {"type": "number"},
                    "vendor": {"type": "string"},
                    "category": {"type": "string"},
                    "purpose": {"type": "string"},
                },
                "required": ["amount_usd", "vendor", "category", "purpose"],
            },
            permission_level=PermissionLevel.SENSITIVE,
        )
        self._service = service

    async def execute(self, **kwargs: Any) -> ToolResult:
        result = await self._service.propose_transaction(
            amount_usd=float(kwargs["amount_usd"]), vendor=kwargs["vendor"], category=kwargs["category"],
            purpose=kwargs["purpose"], task_id=kwargs.get("task_id"),
        )
        if not result.approved:
            return ToolResult.fail(result.reason)
        return ToolResult.ok({"transaction_id": result.transaction_id, "balance_usd": result.balance_usd, "policy_decision": result.policy_decision.value})


class CommunicationProposeReplyTool(Tool):
    def __init__(self, service: CommunicationService) -> None:
        super().__init__(
            name="communication.propose_reply",
            description="Draft and (if policy allows) approve a reply to an authorized contact. Never actually transmits — see docs/DECISIONS.md.",
            input_schema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "draft_text": {"type": "string"},
                },
                "required": ["contact_id", "channel", "draft_text"],
            },
            permission_level=PermissionLevel.SENSITIVE,
        )
        self._service = service

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            comm, delivered, detail = await self._service.propose_reply(
                contact_id=kwargs["contact_id"], channel=kwargs["channel"], draft_text=kwargs["draft_text"], task_id=kwargs.get("task_id")
            )
        except ValueError as exc:
            return ToolResult.fail(str(exc))
        if comm.policy_action == "BLOCKED":
            return ToolResult.fail(detail)
        return ToolResult.ok({"communication_id": comm.id, "policy_action": comm.policy_action, "delivered": delivered, "detail": detail})


class CapabilityResearchTool(Tool):
    def __init__(self, service: CapabilityDiscoveryService) -> None:
        super().__init__(
            name="capabilities.search_github",
            description="Search public GitHub repositories for a tool/library/API that could close a capability gap. Read-only research — never installs anything.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "purpose": {"type": "string"}},
                "required": ["query", "purpose"],
            },
            permission_level=PermissionLevel.SAFE,
        )
        self._service = service

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            results = await self._service.search_github(kwargs["query"], purpose=kwargs["purpose"], limit=int(kwargs.get("limit", 5)))
        except Exception as exc:  # noqa: BLE001 - network/GitHub errors surface as a failed tool call, not a crash
            return ToolResult.fail(f"GitHub search failed: {exc}")
        return ToolResult.ok(
            {"candidates": [{"name": c.name, "source": c.source, "verification_status": c.verification_status.value} for c in results]}
        )


class BusinessOpportunitiesTool(Tool):
    def __init__(self, service: BusinessService) -> None:
        super().__init__(
            name="business.list_opportunities",
            description="List tracked business opportunities ranked by expected value, adjusted for risk. Read-only.",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer"}}},
            permission_level=PermissionLevel.SAFE,
        )
        self._service = service

    async def execute(self, **kwargs: Any) -> ToolResult:
        ranked = await self._service.ranked_opportunities(limit=int(kwargs.get("limit", 10)))
        return ToolResult.ok({"opportunities": [{"title": o.title, "score": round(score, 2), "status": o.status} for o, score in ranked]})


class SystemHealthTool(Tool):
    def __init__(self, service: HealthService) -> None:
        super().__init__(
            name="system.health_check",
            description="Run Jarvis's self-diagnostics across backend components (database, Claude, tools, GitHub reachability, etc.). Read-only.",
            input_schema={"type": "object", "properties": {}},
            permission_level=PermissionLevel.SAFE,
        )
        self._service = service

    async def execute(self, **kwargs: Any) -> ToolResult:
        checks = await self._service.check_all()
        return ToolResult.ok({"components": [{"component": c.component, "status": c.status.value, "detail": c.detail} for c in checks]})


def register_phase3_tools(
    registry: ToolRegistry,
    *,
    wallet_service: WalletService | None = None,
    communication_service: CommunicationService | None = None,
    capability_service: CapabilityDiscoveryService | None = None,
    business_service: BusinessService | None = None,
    health_service: HealthService | None = None,
) -> None:
    """Registers whichever Phase 3 tools have their backing service
    available — e.g. in the Phase 1/2 fallback stack (no Postgres/Claude),
    none of these are registered at all, and Claude simply never sees them
    as options."""
    if wallet_service is not None:
        registry.register(WalletProposeTransactionTool(wallet_service))
    if communication_service is not None:
        registry.register(CommunicationProposeReplyTool(communication_service))
    if capability_service is not None:
        registry.register(CapabilityResearchTool(capability_service))
    if business_service is not None:
        registry.register(BusinessOpportunitiesTool(business_service))
    if health_service is not None:
        registry.register(SystemHealthTool(health_service))
