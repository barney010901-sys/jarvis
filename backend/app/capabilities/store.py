from __future__ import annotations

import json
import uuid

import asyncpg

from app.capabilities.models import Capability, VerificationStatus


def _row_to_capability(row: asyncpg.Record) -> Capability:
    return Capability(
        id=str(row["id"]),
        name=row["name"],
        type=row["type"],
        purpose=row["purpose"],
        source=row["source"],
        version=row["version"],
        permissions=list(row["permissions"]),
        risk=row["risk"],
        reversibility=row["reversibility"],
        cost_estimate_usd=float(row["cost_estimate_usd"]) if row["cost_estimate_usd"] is not None else None,
        success_rate=row["success_rate"],
        confidence=row["confidence"],
        verification_status=VerificationStatus(row["verification_status"]),
        metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"]),
        usage_count=row["usage_count"],
        success_count=row["success_count"],
        owner=row["owner"],
        status=row["status"],
        composed_of=list(row["composed_of"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class CapabilityStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, c: Capability) -> Capability:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO capabilities (
                    id, name, type, purpose, source, version, permissions, risk, reversibility,
                    cost_estimate_usd, success_rate, confidence, verification_status, metadata,
                    owner, status, composed_of
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,$15,$16,$17) RETURNING *
                """,
                c.id or str(uuid.uuid4()), c.name, c.type, c.purpose, c.source, c.version, c.permissions,
                c.risk, c.reversibility, c.cost_estimate_usd, c.success_rate, c.confidence,
                c.verification_status.value, json.dumps(c.metadata),
                c.owner, c.status, c.composed_of,
            )
        return _row_to_capability(row)

    async def get(self, capability_id: str) -> Capability | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM capabilities WHERE id = $1", capability_id)
        return _row_to_capability(row) if row else None

    async def search(self, query: str, *, limit: int = 20) -> list[Capability]:
        """Text search over name/purpose (section 28: "search existing
        capabilities"). ILIKE, not embeddings — see docs/DECISIONS.md,
        "Knowledge search uses trigram similarity" for the same honest
        tradeoff made elsewhere in this codebase."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM capabilities
                WHERE status = 'active' AND (name ILIKE $1 OR purpose ILIKE $1)
                ORDER BY usage_count DESC, updated_at DESC
                LIMIT $2
                """,
                f"%{query}%", limit,
            )
        return [_row_to_capability(r) for r in rows]

    async def record_usage(self, capability_id: str, *, success: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE capabilities
                SET usage_count = usage_count + 1,
                    success_count = success_count + CASE WHEN $2 THEN 1 ELSE 0 END,
                    updated_at = now()
                WHERE id = $1
                """,
                capability_id, success,
            )

    async def set_status(self, capability_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE capabilities SET status = $2, updated_at = now() WHERE id = $1", capability_id, status)

    async def set_verification_status(self, capability_id: str, status: VerificationStatus) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE capabilities SET verification_status = $2, updated_at = now() WHERE id = $1", capability_id, status.value
            )

    async def list(self, *, type: str | None = None, limit: int = 100) -> list[Capability]:
        async with self._pool.acquire() as conn:
            if type:
                rows = await conn.fetch("SELECT * FROM capabilities WHERE type = $1 ORDER BY updated_at DESC LIMIT $2", type, limit)
            else:
                rows = await conn.fetch("SELECT * FROM capabilities ORDER BY updated_at DESC LIMIT $1", limit)
        return [_row_to_capability(r) for r in rows]

    async def find_by_source(self, source: str) -> Capability | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM capabilities WHERE source = $1", source)
        return _row_to_capability(row) if row else None
