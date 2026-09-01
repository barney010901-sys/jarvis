-- Jarvis memory schema (PostgreSQL). See memory/README.md.
--
-- Phase 1 does not connect to a real database yet (see docs/DECISIONS.md);
-- this file is the target shape `backend/app/memory/store.py`'s in-memory
-- implementation is designed against, so a future PostgresMemoryStore can
-- implement the same interfaces without redesigning them.

-- Uncomment once pgvector is available on the target instance:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- WORKING MEMORY
-- Current task/plan/tool-execution state. Ephemeral: cleared when a task
-- completes or fails (see StubOrchestrator.handle_message).
CREATE TABLE IF NOT EXISTS working_memory (
    task_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, key)
);

-- SHORT-TERM MEMORY
-- Recent conversation turns for the current session.
CREATE TABLE IF NOT EXISTS short_term_memory (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_short_term_memory_session ON short_term_memory (session_id, created_at);

-- LONG-TERM MEMORY
-- Durable facts: preferences, decisions, project notes. Keyed by project
-- so recall can be scoped (a decision about project A shouldn't surface
-- while working on project B).
CREATE TABLE IF NOT EXISTS long_term_memory (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project     TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    -- embedding vector(1536),  -- enable with pgvector; see memory/README.md
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_long_term_memory_project ON long_term_memory (project);
-- CREATE INDEX IF NOT EXISTS idx_long_term_memory_embedding
--     ON long_term_memory USING ivfflat (embedding vector_cosine_ops);
