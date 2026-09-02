from __future__ import annotations

import uuid

import asyncpg

from app.selfcode.models import ProposalStatus, SelfModificationProposal


def _row_to_proposal(row: asyncpg.Record) -> SelfModificationProposal:
    return SelfModificationProposal(
        id=str(row["id"]),
        approval_id=str(row["approval_id"]) if row["approval_id"] else None,
        title=row["title"],
        reason=row["reason"],
        diff=row["diff"],
        affected_components=list(row["affected_components"]),
        risk=row["risk"],
        test_plan=row["test_plan"],
        rollback_plan=row["rollback_plan"],
        status=ProposalStatus(row["status"]),
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
        applied_at=row["applied_at"],
    )


class SelfModificationStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, p: SelfModificationProposal) -> SelfModificationProposal:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO self_modification_proposals (
                    id, title, reason, diff, affected_components, risk, test_plan, rollback_plan, status
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
                """,
                p.id or str(uuid.uuid4()), p.title, p.reason, p.diff, p.affected_components,
                p.risk, p.test_plan, p.rollback_plan, p.status.value,
            )
        return _row_to_proposal(row)

    async def get(self, proposal_id: str) -> SelfModificationProposal | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM self_modification_proposals WHERE id = $1", proposal_id)
        return _row_to_proposal(row) if row else None

    async def list(self, *, limit: int = 100) -> list[SelfModificationProposal]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM self_modification_proposals ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_proposal(r) for r in rows]

    async def set_approval(self, proposal_id: str, approval_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE self_modification_proposals SET approval_id = $2 WHERE id = $1", proposal_id, approval_id)

    async def set_status(self, proposal_id: str, status: ProposalStatus, *, resolved: bool = False, applied: bool = False) -> None:
        async with self._pool.acquire() as conn:
            if applied:
                await conn.execute(
                    "UPDATE self_modification_proposals SET status = $2, resolved_at = now(), applied_at = now() WHERE id = $1",
                    proposal_id, status.value,
                )
            elif resolved:
                await conn.execute(
                    "UPDATE self_modification_proposals SET status = $2, resolved_at = now() WHERE id = $1", proposal_id, status.value
                )
            else:
                await conn.execute("UPDATE self_modification_proposals SET status = $2 WHERE id = $1", proposal_id, status.value)
