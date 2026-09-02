from __future__ import annotations

import uuid

import asyncpg

from app.business.models import BusinessIdea, Customer, Experiment, Opportunity, RevenueRecord


def _row_to_idea(row: asyncpg.Record) -> BusinessIdea:
    return BusinessIdea(id=str(row["id"]), title=row["title"], hypothesis=row["hypothesis"], target_customer=row["target_customer"], status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"])


def _row_to_customer(row: asyncpg.Record) -> Customer:
    return Customer(id=str(row["id"]), name=row["name"], contact_id=str(row["contact_id"]) if row["contact_id"] else None, stage=row["stage"], notes=row["notes"], created_at=row["created_at"], updated_at=row["updated_at"])


def _row_to_opportunity(row: asyncpg.Record) -> Opportunity:
    return Opportunity(
        id=str(row["id"]), title=row["title"], description=row["description"],
        expected_value=row["expected_value"], probability=row["probability"], speed=row["speed"],
        scalability=row["scalability"], user_advantage=row["user_advantage"], long_term_value=row["long_term_value"],
        legal_risk=row["legal_risk"], financial_risk=row["financial_risk"], reputational_risk=row["reputational_risk"],
        execution_risk=row["execution_risk"], status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _row_to_experiment(row: asyncpg.Record) -> Experiment:
    return Experiment(id=str(row["id"]), stage=row["stage"], idea_id=str(row["idea_id"]) if row["idea_id"] else None, notes=row["notes"], created_at=row["created_at"], updated_at=row["updated_at"])


def _row_to_revenue(row: asyncpg.Record) -> RevenueRecord:
    return RevenueRecord(id=str(row["id"]), amount_usd=float(row["amount_usd"]), customer_id=str(row["customer_id"]) if row["customer_id"] else None, description=row["description"], created_at=row["created_at"])


class BusinessStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- ideas ---
    async def create_idea(self, idea: BusinessIdea) -> BusinessIdea:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO business_ideas (id, title, hypothesis, target_customer, status) VALUES ($1,$2,$3,$4,$5) RETURNING *",
                idea.id or str(uuid.uuid4()), idea.title, idea.hypothesis, idea.target_customer, idea.status,
            )
        return _row_to_idea(row)

    async def list_ideas(self, limit: int = 100) -> list[BusinessIdea]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM business_ideas ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_idea(r) for r in rows]

    # --- customers ---
    async def create_customer(self, customer: Customer) -> Customer:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO customers (id, name, contact_id, stage, notes) VALUES ($1,$2,$3,$4,$5) RETURNING *",
                customer.id or str(uuid.uuid4()), customer.name, customer.contact_id, customer.stage, customer.notes,
            )
        return _row_to_customer(row)

    async def update_customer_stage(self, customer_id: str, stage: str) -> Customer:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE customers SET stage = $2, updated_at = now() WHERE id = $1 RETURNING *", customer_id, stage
            )
        return _row_to_customer(row)

    async def list_customers(self, stage: str | None = None, limit: int = 100) -> list[Customer]:
        async with self._pool.acquire() as conn:
            if stage:
                rows = await conn.fetch("SELECT * FROM customers WHERE stage = $1 ORDER BY updated_at DESC LIMIT $2", stage, limit)
            else:
                rows = await conn.fetch("SELECT * FROM customers ORDER BY updated_at DESC LIMIT $1", limit)
        return [_row_to_customer(r) for r in rows]

    # --- opportunities ---
    async def create_opportunity(self, o: Opportunity) -> Opportunity:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO opportunities (
                    id, title, description, expected_value, probability, speed, scalability,
                    user_advantage, long_term_value, legal_risk, financial_risk, reputational_risk, execution_risk, status
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING *
                """,
                o.id or str(uuid.uuid4()), o.title, o.description, o.expected_value, o.probability, o.speed,
                o.scalability, o.user_advantage, o.long_term_value, o.legal_risk, o.financial_risk,
                o.reputational_risk, o.execution_risk, o.status,
            )
        return _row_to_opportunity(row)

    async def list_opportunities(self, limit: int = 100) -> list[Opportunity]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM opportunities ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_opportunity(r) for r in rows]

    # --- experiments ---
    async def create_experiment(self, e: Experiment) -> Experiment:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO experiments (id, idea_id, stage, notes) VALUES ($1,$2,$3,$4) RETURNING *",
                e.id or str(uuid.uuid4()), e.idea_id, e.stage, e.notes,
            )
        return _row_to_experiment(row)

    async def update_experiment_stage(self, experiment_id: str, stage: str) -> Experiment:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE experiments SET stage = $2, updated_at = now() WHERE id = $1 RETURNING *", experiment_id, stage
            )
        return _row_to_experiment(row)

    async def list_experiments(self, limit: int = 100) -> list[Experiment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM experiments ORDER BY updated_at DESC LIMIT $1", limit)
        return [_row_to_experiment(r) for r in rows]

    # --- revenue ---
    async def record_revenue(self, r: RevenueRecord) -> RevenueRecord:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO revenue_records (id, customer_id, amount_usd, description) VALUES ($1,$2,$3,$4) RETURNING *",
                r.id or str(uuid.uuid4()), r.customer_id, r.amount_usd, r.description,
            )
        return _row_to_revenue(row)

    async def total_revenue(self) -> float:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval("SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_records")
        return float(value)

    async def list_revenue(self, limit: int = 100) -> list[RevenueRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM revenue_records ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_revenue(r) for r in rows]
