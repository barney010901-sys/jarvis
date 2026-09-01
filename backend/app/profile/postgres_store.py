from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import asyncpg

from app.profile.interface import ProfileStore
from app.profile.models import Goal, Interest, Preference, Project, ProfileFact, Workflow


class PostgresProfileStore(ProfileStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- profile facts ---
    async def get_fact(self, key: str) -> ProfileFact | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM profile_facts WHERE key = $1", key)
        return ProfileFact(key=row["key"], value=json.loads(row["value"]), created_at=row["created_at"], updated_at=row["updated_at"]) if row else None

    async def set_fact(self, key: str, value: Any) -> ProfileFact:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profile_facts (key, value, updated_at) VALUES ($1, $2::jsonb, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                RETURNING *
                """,
                key,
                json.dumps(value),
            )
        return ProfileFact(key=row["key"], value=json.loads(row["value"]), created_at=row["created_at"], updated_at=row["updated_at"])

    # --- preferences ---
    async def get_preference(self, key: str) -> Preference | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM preferences WHERE key = $1", key)
        return Preference(key=row["key"], value=json.loads(row["value"]), created_at=row["created_at"], updated_at=row["updated_at"]) if row else None

    async def set_preference(self, key: str, value: Any) -> Preference:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO preferences (key, value, updated_at) VALUES ($1, $2::jsonb, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                RETURNING *
                """,
                key,
                json.dumps(value),
            )
        return Preference(key=row["key"], value=json.loads(row["value"]), created_at=row["created_at"], updated_at=row["updated_at"])

    async def list_preferences(self) -> list[Preference]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM preferences ORDER BY key")
        return [Preference(key=r["key"], value=json.loads(r["value"]), created_at=r["created_at"], updated_at=r["updated_at"]) for r in rows]

    # --- projects ---
    async def upsert_project(
        self, slug: str, name: str, goals: list[str] | None = None, technologies: list[str] | None = None
    ) -> Project:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO projects (id, slug, name, goals, technologies, updated_at, last_active_at)
                VALUES ($1, $2, $3, $4, $5, now(), now())
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    goals = CASE WHEN $4 = '{}' THEN projects.goals ELSE EXCLUDED.goals END,
                    technologies = CASE WHEN $5 = '{}' THEN projects.technologies ELSE EXCLUDED.technologies END,
                    updated_at = now(),
                    last_active_at = now()
                RETURNING *
                """,
                str(uuid.uuid4()),
                slug,
                name,
                goals or [],
                technologies or [],
            )
        return _row_to_project(row)

    async def get_project(self, slug: str) -> Project | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM projects WHERE slug = $1", slug)
        return _row_to_project(row) if row else None

    async def list_projects(self, status: str | None = None) -> list[Project]:
        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch("SELECT * FROM projects WHERE status = $1 ORDER BY last_active_at DESC", status)
            else:
                rows = await conn.fetch("SELECT * FROM projects ORDER BY last_active_at DESC")
        return [_row_to_project(r) for r in rows]

    async def touch_project(self, slug: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE projects SET last_active_at = now() WHERE slug = $1", slug)

    # --- goals ---
    async def create_goal(
        self, project_slug: str | None, title: str, description: str = "", target_date: date | None = None
    ) -> Goal:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO goals (id, project_slug, title, description, target_date)
                VALUES ($1, $2, $3, $4, $5) RETURNING *
                """,
                str(uuid.uuid4()),
                project_slug,
                title,
                description,
                target_date,
            )
        return _row_to_goal(row)

    async def list_goals(self, project_slug: str | None = None, status: str | None = None) -> list[Goal]:
        conditions = []
        params: list[object] = []
        if project_slug is not None:
            params.append(project_slug)
            conditions.append(f"project_slug = ${len(params)}")
        if status is not None:
            params.append(status)
            conditions.append(f"status = ${len(params)}")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM goals {where} ORDER BY created_at DESC", *params)
        return [_row_to_goal(r) for r in rows]

    async def update_goal_status(self, goal_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE goals SET status = $2, updated_at = now() WHERE id = $1", goal_id, status)

    # --- interests ---
    async def get_interest(self, topic: str, project_slug: str | None) -> Interest | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM interests WHERE topic = $1 AND project_slug IS NOT DISTINCT FROM $2", topic, project_slug
            )
        return _row_to_interest(row) if row else None

    async def upsert_interest(self, topic: str, project_slug: str | None, score: float, signal_count: int) -> Interest:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO interests (id, topic, project_slug, score, signal_count, last_seen_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (topic, project_slug) DO UPDATE SET
                    score = EXCLUDED.score, signal_count = EXCLUDED.signal_count, last_seen_at = now()
                RETURNING *
                """,
                str(uuid.uuid4()),
                topic,
                project_slug,
                score,
                signal_count,
            )
        return _row_to_interest(row)

    async def top_interests(self, project_slug: str | None = None, limit: int = 10) -> list[Interest]:
        async with self._pool.acquire() as conn:
            if project_slug is not None:
                rows = await conn.fetch(
                    "SELECT * FROM interests WHERE project_slug = $1 ORDER BY score DESC LIMIT $2", project_slug, limit
                )
            else:
                rows = await conn.fetch("SELECT * FROM interests ORDER BY score DESC LIMIT $1", limit)
        return [_row_to_interest(r) for r in rows]

    # --- workflows ---
    async def upsert_workflow(self, name: str, steps: list[str], project_slug: str | None) -> tuple[Workflow, bool]:
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM workflows WHERE name = $1 AND project_slug IS NOT DISTINCT FROM $2", name, project_slug
            )
            if existing:
                row = await conn.fetchrow(
                    "UPDATE workflows SET evidence_count = evidence_count + 1, updated_at = now() WHERE id = $1 RETURNING *",
                    existing["id"],
                )
                return _row_to_workflow(row), False

            row = await conn.fetchrow(
                """
                INSERT INTO workflows (id, name, steps, project_slug, evidence_count)
                VALUES ($1, $2, $3::jsonb, $4, 1) RETURNING *
                """,
                str(uuid.uuid4()),
                name,
                json.dumps(steps),
                project_slug,
            )
            return _row_to_workflow(row), True

    async def set_workflow_confirmed(self, workflow_id: str, confirmed: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE workflows SET confirmed = $2, updated_at = now() WHERE id = $1", workflow_id, confirmed)

    async def list_workflows(self, project_slug: str | None = None, confirmed_only: bool = False) -> list[Workflow]:
        conditions = []
        params: list[object] = []
        if project_slug is not None:
            params.append(project_slug)
            conditions.append(f"project_slug = ${len(params)}")
        if confirmed_only:
            conditions.append("confirmed = true")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM workflows {where} ORDER BY evidence_count DESC", *params)
        return [_row_to_workflow(r) for r in rows]


def _row_to_project(row: asyncpg.Record) -> Project:
    return Project(
        id=str(row["id"]),
        slug=row["slug"],
        name=row["name"],
        goals=list(row["goals"]),
        technologies=list(row["technologies"]),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_active_at=row["last_active_at"],
    )


def _row_to_goal(row: asyncpg.Record) -> Goal:
    return Goal(
        id=str(row["id"]),
        project_slug=row["project_slug"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        target_date=row["target_date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_interest(row: asyncpg.Record) -> Interest:
    return Interest(
        id=str(row["id"]),
        topic=row["topic"],
        project_slug=row["project_slug"],
        score=row["score"],
        signal_count=row["signal_count"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
    )


def _row_to_workflow(row: asyncpg.Record) -> Workflow:
    return Workflow(
        id=str(row["id"]),
        name=row["name"],
        steps=list(json.loads(row["steps"])),
        project_slug=row["project_slug"],
        evidence_count=row["evidence_count"],
        confirmed=row["confirmed"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
