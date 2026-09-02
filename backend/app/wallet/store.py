from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncpg

from app.wallet.models import PolicyColor, WalletAccount, WalletTransaction

DEFAULT_WALLET_NAME = "jarvis-operational"


def _row_to_account(row: asyncpg.Record) -> WalletAccount:
    return WalletAccount(
        id=str(row["id"]),
        name=row["name"],
        balance_usd=float(row["balance_usd"]),
        weekly_limit_usd=float(row["weekly_limit_usd"]),
        monthly_limit_usd=float(row["monthly_limit_usd"]),
        per_transaction_limit_usd=float(row["per_transaction_limit_usd"]),
        approval_threshold_usd=float(row["approval_threshold_usd"]),
        approved_categories=list(row["approved_categories"]),
        blocked_categories=list(row["blocked_categories"]),
        approved_vendors=list(row["approved_vendors"]),
    )


def _row_to_transaction(row: asyncpg.Record) -> WalletTransaction:
    return WalletTransaction(
        id=str(row["id"]),
        wallet_id=str(row["wallet_id"]),
        amount_usd=float(row["amount_usd"]),
        vendor=row["vendor"],
        category=row["category"],
        purpose=row["purpose"],
        policy_decision=PolicyColor(row["policy_decision"]),
        status=row["status"],
        task_id=row["task_id"],
        approval_id=str(row["approval_id"]) if row["approval_id"] else None,
        balance_after=float(row["balance_after"]) if row["balance_after"] is not None else None,
        created_at=row["created_at"],
        executed_at=row["executed_at"],
    )


class WalletStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_or_create_account(self, name: str = DEFAULT_WALLET_NAME) -> WalletAccount:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM wallet_accounts WHERE name = $1", name)
            if row is None:
                row = await conn.fetchrow(
                    "INSERT INTO wallet_accounts (id, name) VALUES ($1, $2) RETURNING *", str(uuid.uuid4()), name
                )
        return _row_to_account(row)

    async def update_limits(
        self,
        wallet_id: str,
        *,
        weekly_limit_usd: float | None = None,
        monthly_limit_usd: float | None = None,
        per_transaction_limit_usd: float | None = None,
        approval_threshold_usd: float | None = None,
        approved_categories: list[str] | None = None,
        blocked_categories: list[str] | None = None,
        approved_vendors: list[str] | None = None,
    ) -> WalletAccount:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE wallet_accounts SET
                    weekly_limit_usd = COALESCE($2, weekly_limit_usd),
                    monthly_limit_usd = COALESCE($3, monthly_limit_usd),
                    per_transaction_limit_usd = COALESCE($4, per_transaction_limit_usd),
                    approval_threshold_usd = COALESCE($5, approval_threshold_usd),
                    approved_categories = COALESCE($6, approved_categories),
                    blocked_categories = COALESCE($7, blocked_categories),
                    approved_vendors = COALESCE($8, approved_vendors),
                    updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                wallet_id,
                weekly_limit_usd,
                monthly_limit_usd,
                per_transaction_limit_usd,
                approval_threshold_usd,
                approved_categories,
                blocked_categories,
                approved_vendors,
            )
        return _row_to_account(row)

    async def weekly_spent(self, wallet_id: str) -> float:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount_usd), 0) FROM wallet_transactions
                WHERE wallet_id = $1 AND status = 'EXECUTED' AND created_at >= date_trunc('week', now())
                """,
                wallet_id,
            )
        return float(value)

    async def monthly_spent(self, wallet_id: str) -> float:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT COALESCE(SUM(amount_usd), 0) FROM wallet_transactions
                WHERE wallet_id = $1 AND status = 'EXECUTED' AND created_at >= date_trunc('month', now())
                """,
                wallet_id,
            )
        return float(value)

    async def create_transaction(self, tx: WalletTransaction) -> WalletTransaction:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO wallet_transactions (id, wallet_id, amount_usd, vendor, category, purpose, task_id, policy_decision, status, approval_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
                """,
                tx.id,
                tx.wallet_id,
                tx.amount_usd,
                tx.vendor,
                tx.category,
                tx.purpose,
                tx.task_id,
                tx.policy_decision.value,
                tx.status,
                tx.approval_id,
            )
        return _row_to_transaction(row)

    async def execute(self, tx_id: str, wallet_id: str, amount_usd: float) -> float:
        """Deducts from the internal ledger and marks the transaction
        EXECUTED. This is the entire "execution layer" — see module
        docstring on why there is nothing beyond it."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                account_row = await conn.fetchrow(
                    "UPDATE wallet_accounts SET balance_usd = balance_usd - $2, updated_at = now() WHERE id = $1 RETURNING balance_usd",
                    wallet_id,
                    amount_usd,
                )
                await conn.execute(
                    "UPDATE wallet_transactions SET status = 'EXECUTED', balance_after = $2, executed_at = now() WHERE id = $1",
                    tx_id,
                    account_row["balance_usd"],
                )
        return float(account_row["balance_usd"])

    async def mark_status(self, tx_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE wallet_transactions SET status = $2 WHERE id = $1", tx_id, status)

    async def list_transactions(self, wallet_id: str, limit: int = 50) -> list[WalletTransaction]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM wallet_transactions WHERE wallet_id = $1 ORDER BY created_at DESC LIMIT $2", wallet_id, limit
            )
        return [_row_to_transaction(r) for r in rows]
