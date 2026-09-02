from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from app.business.models import BusinessIdea, Customer, Experiment, Opportunity, RevenueRecord
from app.business.scoring import score_opportunity
from app.business.service import BusinessService
from app.business.store import BusinessStore
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
        await conn.execute("TRUNCATE business_ideas, customers, opportunities, experiments, revenue_records CASCADE")
        await conn.execute("TRUNCATE wallet_transactions, wallet_accounts CASCADE")
    await p.close()


@pytest.mark.asyncio
async def test_idea_and_experiment_lifecycle(pool):
    store = BusinessStore(pool)
    idea = await store.create_idea(BusinessIdea(id=str(uuid.uuid4()), title="Automated invoicing for freelancers", hypothesis="freelancers hate manual invoicing"))
    experiment = await store.create_experiment(Experiment(id=str(uuid.uuid4()), idea_id=idea.id, stage="HYPOTHESIS"))

    updated = await store.update_experiment_stage(experiment.id, "MVP")
    assert updated.stage == "MVP"

    ideas = await store.list_ideas()
    assert any(i.id == idea.id for i in ideas)


@pytest.mark.asyncio
async def test_customer_pipeline_progression(pool):
    store = BusinessStore(pool)
    customer = await store.create_customer(Customer(id=str(uuid.uuid4()), name="Acme Corp"))
    assert customer.stage == "LEAD"

    for stage in ("CONTACTED", "QUALIFIED", "PROPOSAL", "ACTIVE", "PAID"):
        customer = await store.update_customer_stage(customer.id, stage)
    assert customer.stage == "PAID"


def test_score_opportunity_rewards_high_value_low_risk():
    high_value_low_risk = Opportunity(
        id="a", title="a", expected_value=10000, probability=0.9, speed=0.9, scalability=0.9, user_advantage=0.9, long_term_value=0.9,
        legal_risk=0.0, financial_risk=0.0, reputational_risk=0.0, execution_risk=0.0,
    )
    low_value_high_risk = Opportunity(
        id="b", title="b", expected_value=10000, probability=0.9, speed=0.9, scalability=0.9, user_advantage=0.9, long_term_value=0.9,
        legal_risk=0.5, financial_risk=0.5, reputational_risk=0.0, execution_risk=0.0,
    )
    assert score_opportunity(high_value_low_risk) > score_opportunity(low_value_high_risk)


@pytest.mark.asyncio
async def test_ranked_opportunities_orders_by_score(pool):
    store = BusinessStore(pool)
    await store.create_opportunity(Opportunity(id=str(uuid.uuid4()), title="risky", expected_value=1000, legal_risk=0.9, financial_risk=0.9))
    await store.create_opportunity(Opportunity(id=str(uuid.uuid4()), title="safe", expected_value=1000, legal_risk=0.0, financial_risk=0.0))

    service = BusinessService(store)
    ranked = await service.ranked_opportunities()
    assert ranked[0][0].title == "safe"


@pytest.mark.asyncio
async def test_sustainability_summary_survive_stage_with_no_revenue(pool):
    store = BusinessStore(pool)
    service = BusinessService(store, WalletStore(pool))
    summary = await service.sustainability_summary()
    assert summary.stage == "SURVIVE"


@pytest.mark.asyncio
async def test_sustainability_summary_reaches_surplus_stage(pool):
    store = BusinessStore(pool)
    await store.record_revenue(RevenueRecord(id=str(uuid.uuid4()), amount_usd=500.0, description="first paid project"))

    service = BusinessService(store, WalletStore(pool))
    summary = await service.sustainability_summary()
    assert summary.revenue_total_usd == 500.0
    assert summary.monthly_operating_cost_usd == 0.0
    assert summary.stage == "SURPLUS"
