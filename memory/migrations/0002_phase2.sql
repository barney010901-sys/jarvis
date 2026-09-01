-- Phase 2 migration: knowledge, profile/project/goal/interest/workflow
-- memory, suggestions, task lifecycle, audit trail, token usage.
--
-- This is additive on top of memory/schema.sql (working_memory,
-- short_term_memory, long_term_memory), which is unchanged. See
-- docs/DECISIONS.md ("Phase 2 schema migration") for why this is a
-- separate numbered file rather than an edit to schema.sql.
--
-- Apply after schema.sql:
--   psql "$DATABASE_URL" -f memory/schema.sql
--   psql "$DATABASE_URL" -f memory/migrations/0002_phase2.sql
-- Every statement is idempotent (IF NOT EXISTS / ON CONFLICT) so re-running
-- this file is safe.

-- =========================================================================
-- KNOWLEDGE (2F/2G/2H/2I/2Q)
-- =========================================================================
CREATE TABLE IF NOT EXISTS knowledge (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category        TEXT NOT NULL CHECK (category IN (
                        'USER_PREFERENCES', 'PROJECT_KNOWLEDGE', 'TECHNICAL_KNOWLEDGE',
                        'WORKFLOWS', 'DECISIONS', 'SOLUTIONS', 'TOOL_KNOWLEDGE',
                        'ERROR_FIXES', 'DESIGN_SYSTEMS', 'SUCCESSFUL_TASKS',
                        'FUTURE_RELEVANT_KNOWLEDGE'
                    )),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'unknown',
    source_type     TEXT NOT NULL DEFAULT 'manual', -- e.g. claude_response, user_correction, heuristic, manual
    project         TEXT,                            -- NULL = global, not project-scoped
    tags            TEXT[] NOT NULL DEFAULT '{}',
    confidence      REAL NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'STALE', 'ARCHIVED')),
    last_verified_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    usage_count     INTEGER NOT NULL DEFAULT 0,
    last_used_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_knowledge_project_category ON knowledge (project, category);
CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge (status);
-- Cheap "already similar?" pre-filter before the app-level similarity check
-- (see backend/app/knowledge/similarity.py) — trigram index on title+content.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_knowledge_title_trgm ON knowledge USING gin (title gin_trgm_ops);

-- =========================================================================
-- PROFILE / PREFERENCES / PROJECTS / GOALS / INTERESTS / WORKFLOWS (2J/2K/2L/2M/2N)
-- Kept as separate tables per instruction: "do not mix these into one
-- giant memory table."
-- =========================================================================
CREATE TABLE IF NOT EXISTS profile_facts (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    goals           TEXT[] NOT NULL DEFAULT '{}',
    technologies    TEXT[] NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED', 'ARCHIVED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS goals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_slug    TEXT, -- soft reference to projects.slug; not a FK (see docs/DECISIONS.md, "Project references are soft, not FK-enforced")
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DONE', 'PAUSED', 'ABANDONED')),
    target_date     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_goals_project ON goals (project_slug);

CREATE TABLE IF NOT EXISTS interests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic           TEXT NOT NULL,
    project_slug    TEXT, -- soft reference to projects.slug; not a FK (see docs/DECISIONS.md, "Project references are soft, not FK-enforced")
    score           REAL NOT NULL DEFAULT 0,
    signal_count    INTEGER NOT NULL DEFAULT 0,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic, project_slug)
);
CREATE INDEX IF NOT EXISTS idx_interests_score ON interests (score DESC);

CREATE TABLE IF NOT EXISTS workflows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    steps           JSONB NOT NULL, -- ordered list of tool/step names
    project_slug    TEXT, -- soft reference to projects.slug; not a FK (see docs/DECISIONS.md, "Project references are soft, not FK-enforced")
    evidence_count  INTEGER NOT NULL DEFAULT 1,
    confirmed       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, project_slug)
);

-- =========================================================================
-- SUGGESTIONS (2P)
-- =========================================================================
CREATE TABLE IF NOT EXISTS suggestions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    priority        TEXT NOT NULL CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH')),
    title           TEXT NOT NULL,
    reason          TEXT NOT NULL,
    relevance       REAL NOT NULL DEFAULT 0,
    related_project TEXT,
    related_goal    UUID REFERENCES goals (id) ON DELETE SET NULL,
    source          TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.5,
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SHOWN', 'DISMISSED', 'ACCEPTED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_suggestions_status_priority ON suggestions (status, priority);

-- =========================================================================
-- TASK LIFECYCLE (2R)
-- =========================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY,
    session_id      TEXT NOT NULL,
    project         TEXT NOT NULL,
    request         TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN (
                        'CREATED', 'PLANNED', 'WAITING_FOR_CONFIRMATION', 'RUNNING',
                        'WAITING_FOR_TOOL', 'EVALUATING', 'COMPLETED',
                        'FAILED', 'CANCELLED', 'TIMEOUT'
                    )),
    plan            JSONB,
    result          JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks (project, created_at);

-- =========================================================================
-- AUDIT LOG (2T) — one row per event published on the EventBus. Populated
-- by backend/app/audit/logger.py, a wildcard subscriber; not written to
-- directly by feature code.
-- =========================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id                  BIGSERIAL PRIMARY KEY,
    task_id             TEXT,
    event_type          TEXT NOT NULL,
    component           TEXT NOT NULL,
    action              TEXT NOT NULL,
    result              TEXT,
    confirmation_state  TEXT,
    payload             JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_task ON audit_log (task_id, created_at);

-- =========================================================================
-- TOKEN / COST TRACKING (2E)
-- =========================================================================
CREATE TABLE IF NOT EXISTS token_usage (
    id                  BIGSERIAL PRIMARY KEY,
    task_id             TEXT,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    role                TEXT NOT NULL, -- 'fast' | 'primary' | 'fallback'
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd  NUMERIC(10, 6) NOT NULL DEFAULT 0,
    served_from_cache   BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage (created_at);

-- =========================================================================
-- KNOWLEDGE GRAPH / RELATIONSHIPS (2V) — deliberately simple: a generic
-- edge table, not a graph database. "PostgreSQL relationships are
-- sufficient for Phase 2."
-- =========================================================================
CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id          BIGSERIAL PRIMARY KEY,
    from_type   TEXT NOT NULL, -- e.g. 'project', 'goal', 'knowledge', 'interest', 'workflow', 'task'
    from_id     TEXT NOT NULL,
    to_type     TEXT NOT NULL,
    to_id       TEXT NOT NULL,
    relation    TEXT NOT NULL, -- e.g. 'informed_by', 'produced', 'belongs_to'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (from_type, from_id, to_type, to_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_rel_from ON knowledge_relationships (from_type, from_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_rel_to ON knowledge_relationships (to_type, to_id);
