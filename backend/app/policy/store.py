"""Persisted policy statements (2 Phase 3, section 77 "Policy Memory") —
user-editable, auditable rules like "routine client follow-ups can be
automatic" or "never negotiate price without me". Keyed as
`"<rule_type>:<subkey>"` (e.g. `"communication:routine_reply"`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg


@dataclass
class Policy:
    key: str
    description: str
    rule_type: str
    config: dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _row_to_policy(row: asyncpg.Record) -> Policy:
    return Policy(
        key=row["key"],
        description=row["description"],
        rule_type=row["rule_type"],
        config=json.loads(row["config"]) if isinstance(row["config"], str) else dict(row["config"]),
        active=row["active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PolicyStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(self, key: str, *, description: str, rule_type: str, config: dict[str, Any] | None = None, active: bool = True) -> Policy:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO policies (key, description, rule_type, config, active, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, now())
                ON CONFLICT (key) DO UPDATE SET
                    description = EXCLUDED.description, rule_type = EXCLUDED.rule_type,
                    config = EXCLUDED.config, active = EXCLUDED.active, updated_at = now()
                RETURNING *
                """,
                key,
                description,
                rule_type,
                json.dumps(config or {}),
                active,
            )
        return _row_to_policy(row)

    async def get(self, key: str) -> Policy | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM policies WHERE key = $1", key)
        return _row_to_policy(row) if row else None

    async def list(self, rule_type: str | None = None) -> list[Policy]:
        async with self._pool.acquire() as conn:
            if rule_type:
                rows = await conn.fetch("SELECT * FROM policies WHERE rule_type = $1 ORDER BY key", rule_type)
            else:
                rows = await conn.fetch("SELECT * FROM policies ORDER BY key")
        return [_row_to_policy(r) for r in rows]

    async def delete(self, key: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM policies WHERE key = $1", key)

    async def is_auto_approved(self, key: str) -> bool:
        """Used for LEVEL_4/5 autonomy pre-approval lookups (see
        PolicyRequest.preapproval_key)."""
        policy = await self.get(key)
        return bool(policy and policy.active and policy.config.get("action") == "AUTO")
