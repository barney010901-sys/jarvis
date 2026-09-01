"""asyncpg connection pool, one per process.

This is the only place that opens a connection to `settings.database_url`.
Everything that needs Postgres (memory, knowledge, profile, tasks, audit,
cost tracking) takes a `Pool` in its constructor rather than importing this
module directly, except `app.deps`, which is where the pool is actually
constructed and handed out (see docs/DECISIONS.md, "Phase 2 database
wiring").
"""
from __future__ import annotations

import logging

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool | None:
    """Attempt to open the pool. Returns None (and logs a warning) if
    Postgres isn't reachable, so callers can fall back to the in-memory
    stores instead of crashing the whole backend — see deps.py."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            timeout=5,
            command_timeout=10,
        )
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("Connected to PostgreSQL.")
        return _pool
    except Exception:  # noqa: BLE001 - any connection failure should degrade, not crash
        logger.warning(
            "Could not connect to PostgreSQL at %s — falling back to in-memory stores. "
            "See docs/PHASE_2.md.",
            _redact(settings.database_url),
            exc_info=True,
        )
        _pool = None
        return None


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool | None:
    return _pool


def pool_is_ready() -> bool:
    return _pool is not None


def _redact(dsn: str) -> str:
    # Never log credentials, even on a connection failure.
    if "@" in dsn:
        scheme, _, rest = dsn.partition("://")
        _, _, host_part = rest.partition("@")
        return f"{scheme}://***:***@{host_part}"
    return dsn
