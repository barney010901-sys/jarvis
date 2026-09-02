"""Tests for the Tool adapters Claude actually calls
(backend/app/tools/phase3_tools.py) — the underlying services already have
their own thorough tests; this file only verifies the thin translation
from Tool.execute(**kwargs) to each service call, against real Postgres.
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.business.service import BusinessService
from app.business.store import BusinessStore
from app.communication.channel import NotConfiguredChannelAdapter
from app.communication.models import Contact, ContactRole
from app.communication.service import CommunicationService
from app.communication.store import CommunicationStore, ContactStore
from app.events.bus import EventBus
from app.health.service import HealthService
from app.permissions.manager import ConfirmationManager
from app.permissions.models import PermissionLevel
from app.policy.approvals import ApprovalStore
from app.policy.engine import PolicyEngine
from app.policy.store import PolicyStore
from app.tools.phase3_tools import (
    BusinessOpportunitiesTool,
    CommunicationProposeReplyTool,
    SystemHealthTool,
    WalletProposeTransactionTool,
    register_phase3_tools,
)
from app.tools.registry import ToolRegistry, default_registry
from app.wallet.service import WalletService
from app.wallet.store import WalletStore

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
        await conn.execute("TRUNCATE wallet_transactions, wallet_accounts, contacts, communications, approvals CASCADE")
        await conn.execute("TRUNCATE business_ideas, customers, opportunities, experiments, revenue_records CASCADE")
    await p.close()


def make_policy_engine(pool):
    event_bus = EventBus()
    return PolicyEngine(policy_store=PolicyStore(pool), approval_store=ApprovalStore(pool), confirmation_manager=ConfirmationManager(event_bus), event_bus=event_bus), event_bus


@pytest.mark.asyncio
async def test_wallet_tool_executes_a_green_transaction(pool):
    policy, event_bus = make_policy_engine(pool)
    store = WalletStore(pool)
    account = await store.get_or_create_account()
    await store.update_limits(account.id, approved_categories=["hosting"])

    tool = WalletProposeTransactionTool(WalletService(store, policy, event_bus))
    assert tool.permission_level == PermissionLevel.SENSITIVE

    result = await tool.run(amount_usd=5.0, vendor="digitalocean", category="hosting", purpose="VPS", project_root=".")
    assert result.success
    assert result.data["policy_decision"] == "GREEN"


@pytest.mark.asyncio
async def test_communication_tool_returns_failure_for_unknown_contact(pool):
    policy, event_bus = make_policy_engine(pool)
    service = CommunicationService(
        contacts=ContactStore(pool), communications=CommunicationStore(pool), policy_engine=policy,
        channel=NotConfiguredChannelAdapter(), event_bus=event_bus,
    )
    tool = CommunicationProposeReplyTool(service)
    result = await tool.run(contact_id=str(uuid.uuid4()), channel="email", draft_text="hi", project_root=".")
    assert not result.success


@pytest.mark.asyncio
async def test_communication_tool_succeeds_for_routine_reply(pool):
    policy, event_bus = make_policy_engine(pool)
    contacts = ContactStore(pool)
    contact = await contacts.create(Contact(id=str(uuid.uuid4()), name="Alice", role=ContactRole.CLIENT, channel="email"))
    service = CommunicationService(contacts=contacts, communications=CommunicationStore(pool), policy_engine=policy, channel=NotConfiguredChannelAdapter(), event_bus=event_bus)

    tool = CommunicationProposeReplyTool(service)
    result = await tool.run(contact_id=contact.id, channel="email", draft_text="Thanks, got it!", project_root=".")
    assert result.success
    assert result.data["policy_action"] == "AUTO"
    assert result.data["delivered"] is False


@pytest.mark.asyncio
async def test_business_opportunities_tool_lists_ranked_results(pool):
    from app.business.models import Opportunity

    store = BusinessStore(pool)
    await store.create_opportunity(Opportunity(id=str(uuid.uuid4()), title="Best", expected_value=1000, legal_risk=0.0))
    await store.create_opportunity(Opportunity(id=str(uuid.uuid4()), title="Worst", expected_value=1000, legal_risk=0.9, financial_risk=0.9))

    tool = BusinessOpportunitiesTool(BusinessService(store))
    result = await tool.run(project_root=".")
    assert result.success
    assert result.data["opportunities"][0]["title"] == "Best"


@pytest.mark.asyncio
async def test_system_health_tool_reports_real_status(pool):
    event_bus = EventBus()
    tool = SystemHealthTool(HealthService(pool=pool, claude_configured=False, event_bus=event_bus, tool_registry=default_registry(".")))
    result = await tool.run(project_root=".")
    assert result.success
    components = {c["component"]: c["status"] for c in result.data["components"]}
    assert components["database"] == "HEALTHY"


@pytest.mark.asyncio
async def test_register_phase3_tools_only_registers_available_services(pool):
    registry = ToolRegistry()
    policy, event_bus = make_policy_engine(pool)
    wallet_service = WalletService(WalletStore(pool), policy, event_bus)

    register_phase3_tools(registry, wallet_service=wallet_service)  # only wallet provided

    names = {t.name for t in registry.list()}
    assert "wallet.propose_transaction" in names
    assert "communication.propose_reply" not in names
    assert "business.list_opportunities" not in names
