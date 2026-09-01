from __future__ import annotations

import uuid

import asyncpg

from app.knowledge.interface import KnowledgeStore
from app.knowledge.models import KnowledgeCategory, KnowledgeRecord, KnowledgeStatus

# Below this, two pieces of text are considered unrelated. 0.12 is
# deliberately low — high recall matters more than precision here, since
# false positives are cheap to include as extra context (see
# ContextEngine) and only genuinely count against a caller when used for
# the 2E cost-hierarchy short-circuit, which layers its own confidence
# threshold on top (see KnowledgeService.find_high_confidence_answer).
SEARCH_SIMILARITY_THRESHOLD = 0.12


def _row_to_record(row: asyncpg.Record) -> KnowledgeRecord:
    return KnowledgeRecord(
        id=str(row["id"]),
        category=KnowledgeCategory(row["category"]),
        title=row["title"],
        content=row["content"],
        source=row["source"],
        source_type=row["source_type"],
        project=row["project"],
        tags=list(row["tags"]),
        confidence=row["confidence"],
        status=KnowledgeStatus(row["status"]),
        last_verified_at=row["last_verified_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        usage_count=row["usage_count"],
        last_used_at=row["last_used_at"],
    )


class PostgresKnowledgeStore(KnowledgeStore):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, record: KnowledgeRecord) -> KnowledgeRecord:
        record_id = record.id or str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge (
                    id, category, title, content, source, source_type, project, tags,
                    confidence, status, last_verified_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
                """,
                record_id,
                record.category.value,
                record.title,
                record.content,
                record.source,
                record.source_type,
                record.project,
                record.tags,
                record.confidence,
                record.status.value,
                record.last_verified_at,
            )
        return _row_to_record(row)

    async def get(self, knowledge_id: str) -> KnowledgeRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge WHERE id = $1", knowledge_id)
        return _row_to_record(row) if row else None

    async def search(
        self,
        *,
        project: str | None,
        query: str,
        category: KnowledgeCategory | None = None,
        status: KnowledgeStatus | None = KnowledgeStatus.ACTIVE,
        limit: int = 10,
    ) -> list[KnowledgeRecord]:
        # Trigram similarity, not ILIKE substring: a full natural-language
        # query ("I'm getting a CORS error") should match a short title
        # ("Fix CORS error") even though neither contains the other
        # verbatim. See docs/DECISIONS.md ("Knowledge search uses trigram
        # similarity, not substring matching").
        params: list[object] = [query]
        conditions = [f"(similarity(title, $1) > {SEARCH_SIMILARITY_THRESHOLD} OR similarity(content, $1) > {SEARCH_SIMILARITY_THRESHOLD})"]

        if project is not None:
            params.append(project)
            conditions.append(f"project = ${len(params)}")
        if category is not None:
            params.append(category.value)
            conditions.append(f"category = ${len(params)}")
        if status is not None:
            params.append(status.value)
            conditions.append(f"status = ${len(params)}")

        params.append(limit)
        sql = f"""
            SELECT * FROM knowledge
            WHERE {' AND '.join(conditions)}
            ORDER BY GREATEST(similarity(title, $1), similarity(content, $1)) DESC, updated_at DESC
            LIMIT ${len(params)}
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [_row_to_record(r) for r in rows]

    async def update(self, record: KnowledgeRecord) -> KnowledgeRecord:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE knowledge SET
                    title = $2, content = $3, source = $4, source_type = $5, project = $6,
                    tags = $7, confidence = $8, status = $9, last_verified_at = $10, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                record.id,
                record.title,
                record.content,
                record.source,
                record.source_type,
                record.project,
                record.tags,
                record.confidence,
                record.status.value,
                record.last_verified_at,
            )
        return _row_to_record(row)

    async def set_status(self, knowledge_id: str, status: KnowledgeStatus) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE knowledge SET status = $2, updated_at = now() WHERE id = $1", knowledge_id, status.value
            )

    async def record_usage(self, knowledge_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE knowledge SET usage_count = usage_count + 1, last_used_at = now() WHERE id = $1",
                knowledge_id,
            )

    async def adjust_confidence(self, knowledge_id: str, delta: float) -> float:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE knowledge
                SET confidence = LEAST(1.0, GREATEST(0.0, confidence + $2)), updated_at = now()
                WHERE id = $1
                RETURNING confidence
                """,
                knowledge_id,
                delta,
            )
        if row is None:
            raise KeyError(f"no knowledge record with id {knowledge_id}")
        return row["confidence"]

    async def list_by_project(
        self, project: str | None, category: KnowledgeCategory | None = None, limit: int = 50
    ) -> list[KnowledgeRecord]:
        conditions = ["status != 'ARCHIVED'"]
        params: list[object] = []
        if project is not None:
            params.append(project)
            conditions.append(f"project = ${len(params)}")
        else:
            conditions.append("project IS NULL")
        if category is not None:
            params.append(category.value)
            conditions.append(f"category = ${len(params)}")
        params.append(limit)
        sql = f"SELECT * FROM knowledge WHERE {' AND '.join(conditions)} ORDER BY updated_at DESC LIMIT ${len(params)}"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [_row_to_record(r) for r in rows]
