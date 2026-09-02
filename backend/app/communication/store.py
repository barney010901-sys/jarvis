from __future__ import annotations

import uuid

import asyncpg

from app.communication.models import Category, Communication, Contact, ContactRole, Direction


def _row_to_contact(row: asyncpg.Record) -> Contact:
    return Contact(
        id=str(row["id"]),
        name=row["name"],
        relationship=row["relationship"],
        role=ContactRole(row["role"]),
        channel=row["channel"],
        allowed_categories=list(row["allowed_categories"]),
        disclosure_limit=row["disclosure_limit"],
        active=row["active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_communication(row: asyncpg.Record) -> Communication:
    return Communication(
        id=str(row["id"]),
        direction=Direction(row["direction"]),
        category=Category(row["category"]),
        summary=row["summary"],
        policy_action=row["policy_action"],
        contact_id=str(row["contact_id"]) if row["contact_id"] else None,
        channel=row["channel"],
        task_id=row["task_id"],
        approval_id=str(row["approval_id"]) if row["approval_id"] else None,
        created_at=row["created_at"],
    )


class ContactStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, contact: Contact) -> Contact:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO contacts (id, name, relationship, role, channel, allowed_categories, disclosure_limit, active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *
                """,
                contact.id or str(uuid.uuid4()),
                contact.name,
                contact.relationship,
                contact.role.value,
                contact.channel,
                contact.allowed_categories,
                contact.disclosure_limit,
                contact.active,
            )
        return _row_to_contact(row)

    async def get(self, contact_id: str) -> Contact | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM contacts WHERE id = $1", contact_id)
        return _row_to_contact(row) if row else None

    async def list(self, *, role: ContactRole | None = None, active_only: bool = True) -> list[Contact]:
        conditions = []
        params: list[object] = []
        if active_only:
            conditions.append("active = true")
        if role is not None:
            params.append(role.value)
            conditions.append(f"role = ${len(params)}")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM contacts {where} ORDER BY name", *params)
        return [_row_to_contact(r) for r in rows]

    async def set_active(self, contact_id: str, active: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE contacts SET active = $2, updated_at = now() WHERE id = $1", contact_id, active)


class CommunicationStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, comm: Communication) -> Communication:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO communications (id, contact_id, channel, direction, category, summary, policy_action, task_id, approval_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *
                """,
                comm.id or str(uuid.uuid4()),
                comm.contact_id,
                comm.channel,
                comm.direction.value,
                comm.category.value,
                comm.summary,
                comm.policy_action,
                comm.task_id,
                comm.approval_id,
            )
        return _row_to_communication(row)

    async def list_recent(self, *, contact_id: str | None = None, limit: int = 50) -> list[Communication]:
        async with self._pool.acquire() as conn:
            if contact_id:
                rows = await conn.fetch(
                    "SELECT * FROM communications WHERE contact_id = $1 ORDER BY created_at DESC LIMIT $2", contact_id, limit
                )
            else:
                rows = await conn.fetch("SELECT * FROM communications ORDER BY created_at DESC LIMIT $1", limit)
        return [_row_to_communication(r) for r in rows]
