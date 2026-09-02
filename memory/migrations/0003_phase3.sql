-- Phase 3 migration: policy/approvals, capability discovery, communication,
-- escalation, operational wallet, business engine.
--
-- Additive on top of schema.sql + 0002_phase2.sql (unchanged). See
-- docs/DECISIONS.md ("Phase 3 schema migration") for why this is a
-- separate numbered file. Idempotent (IF NOT EXISTS / ON CONFLICT) — safe
-- to re-run.
--
-- Apply after 0002_phase2.sql:
--   psql "$DATABASE_URL" -f memory/schema.sql
--   psql "$DATABASE_URL" -f memory/migrations/0002_phase2.sql
--   psql "$DATABASE_URL" -f memory/migrations/0003_phase3.sql

-- =========================================================================
-- POLICY + APPROVALS (28, 70) — the centralized gate every external/
-- sensitive action passes through. `approvals` mirrors the existing
-- ConfirmationManager's confirmation_id (see backend/app/policy/engine.py)
-- so the Approval Center has one durable, richer record of every ASK
-- decision without a second confirmation mechanism.
-- =========================================================================
CREATE TABLE IF NOT EXISTS policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    rule_type   TEXT NOT NULL, -- e.g. 'communication', 'wallet', 'autonomy', 'escalation'
    config      JSONB NOT NULL DEFAULT '{}',
    active      BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
    id              UUID PRIMARY KEY, -- shared with ConfirmationManager's confirmation_id when applicable
    kind            TEXT NOT NULL CHECK (kind IN (
                        'tool_install', 'wallet_transaction', 'communication',
                        'destructive_operation', 'capability_install', 'other'
                    )),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    risk            TEXT NOT NULL DEFAULT 'unknown', -- e.g. 'low', 'medium', 'high'
    cost_usd        NUMERIC(10, 2),
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    task_id         TEXT,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status, requested_at);

-- =========================================================================
-- CAPABILITY DISCOVERY (18, 19, 20, 21) — persisted candidates beyond the
-- in-process ToolRegistry (backend/app/tools/registry.py, unchanged).
-- =========================================================================
CREATE TABLE IF NOT EXISTS capabilities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    type                TEXT NOT NULL, -- 'tool' | 'library' | 'api' | 'mcp_server' | 'service'
    purpose             TEXT NOT NULL,
    source              TEXT NOT NULL, -- e.g. a GitHub URL
    version             TEXT,
    permissions         TEXT[] NOT NULL DEFAULT '{}',
    risk                TEXT NOT NULL DEFAULT 'unknown',
    reversibility       TEXT NOT NULL DEFAULT 'unknown', -- 'reversible' | 'irreversible' | 'unknown'
    cost_estimate_usd   NUMERIC(10, 2),
    success_rate        REAL,
    confidence          REAL NOT NULL DEFAULT 0.3,
    verification_status TEXT NOT NULL DEFAULT 'NOT_TESTED' CHECK (verification_status IN (
                            'REAL', 'MOCKED', 'PARTIALLY_IMPLEMENTED', 'NOT_TESTED'
                        )),
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_capabilities_type ON capabilities (type);

-- =========================================================================
-- COMMUNICATION + ESCALATION (33-39) — contacts double as escalation
-- contacts via `role`. No message content is ever sent through a real
-- channel by this schema/service layer; see backend/app/communication's
-- module docstring for the explicit NotImplementedError transmission
-- adapter boundary.
-- =========================================================================
CREATE TABLE IF NOT EXISTS contacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    relationship        TEXT NOT NULL DEFAULT '',
    role                TEXT NOT NULL DEFAULT 'OTHER' CHECK (role IN ('PRIMARY', 'SECONDARY', 'EMERGENCY', 'CLIENT', 'OTHER')),
    channel             TEXT NOT NULL DEFAULT 'unknown',
    allowed_categories  TEXT[] NOT NULL DEFAULT '{}',
    disclosure_limit    TEXT NOT NULL DEFAULT 'minimum necessary',
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS communications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      UUID REFERENCES contacts (id) ON DELETE SET NULL,
    channel         TEXT NOT NULL DEFAULT 'unknown',
    direction       TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    category        TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (category IN (
                        'PERSONAL', 'CLIENT', 'BUSINESS', 'IMPORTANT', 'LOW_PRIORITY', 'UNKNOWN'
                    )),
    summary         TEXT NOT NULL,
    policy_action   TEXT NOT NULL CHECK (policy_action IN ('AUTO', 'ASK', 'BLOCKED')),
    task_id         TEXT,
    approval_id     UUID REFERENCES approvals (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_communications_contact ON communications (contact_id, created_at);

CREATE TABLE IF NOT EXISTS escalation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      UUID REFERENCES contacts (id) ON DELETE SET NULL,
    reason          TEXT NOT NULL,
    urgency         TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (urgency IN ('LOW', 'MEDIUM', 'HIGH')),
    disclosure      TEXT NOT NULL, -- the exact minimum-necessary message constructed
    task_id         TEXT,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    result          TEXT NOT NULL DEFAULT 'PENDING'
);

-- =========================================================================
-- OPERATIONAL WALLET (40-45, 62, 76) — a real, deterministic internal
-- ledger with enforced limits. There is no real payment-rail integration
-- (no bank/card/crypto API): `execute()` only ever adjusts this ledger.
-- =========================================================================
CREATE TABLE IF NOT EXISTS wallet_accounts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT UNIQUE NOT NULL DEFAULT 'jarvis-operational',
    balance_usd             NUMERIC(12, 2) NOT NULL DEFAULT 0,
    weekly_limit_usd        NUMERIC(10, 2) NOT NULL DEFAULT 25,
    monthly_limit_usd       NUMERIC(10, 2) NOT NULL DEFAULT 75,
    per_transaction_limit_usd NUMERIC(10, 2) NOT NULL DEFAULT 15,
    approval_threshold_usd  NUMERIC(10, 2) NOT NULL DEFAULT 5,
    approved_categories     TEXT[] NOT NULL DEFAULT '{}',
    blocked_categories      TEXT[] NOT NULL DEFAULT '{gambling,loans,cryptocurrency_speculation,personal_purchase}',
    approved_vendors        TEXT[] NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id       UUID NOT NULL REFERENCES wallet_accounts (id) ON DELETE CASCADE,
    amount_usd      NUMERIC(10, 2) NOT NULL,
    vendor          TEXT NOT NULL,
    category        TEXT NOT NULL,
    purpose         TEXT NOT NULL,
    task_id         TEXT,
    policy_decision TEXT NOT NULL CHECK (policy_decision IN ('GREEN', 'YELLOW', 'RED')),
    status          TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN (
                        'PROPOSED', 'APPROVED', 'REJECTED', 'EXECUTED', 'FAILED'
                    )),
    approval_id     UUID REFERENCES approvals (id) ON DELETE SET NULL,
    balance_after   NUMERIC(12, 2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet_created ON wallet_transactions (wallet_id, created_at);

-- =========================================================================
-- BUSINESS ENGINE (46-52) — ideas, customer pipeline, ranked
-- opportunities, experiments, revenue. Expenses are tracked via
-- wallet_transactions (category = business-related) rather than a
-- duplicate ledger.
-- =========================================================================
CREATE TABLE IF NOT EXISTS business_ideas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    hypothesis      TEXT NOT NULL DEFAULT '',
    target_customer TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'IDEA',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    contact_id      UUID REFERENCES contacts (id) ON DELETE SET NULL,
    stage           TEXT NOT NULL DEFAULT 'LEAD' CHECK (stage IN (
                        'LEAD', 'CONTACTED', 'INTERESTED', 'QUALIFIED', 'PROPOSAL',
                        'APPROVED', 'ACTIVE', 'DELIVERED', 'PAID', 'REPEAT'
                    )),
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS opportunities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    expected_value      REAL NOT NULL DEFAULT 0,
    probability         REAL NOT NULL DEFAULT 0.5,
    speed               REAL NOT NULL DEFAULT 0.5,
    scalability         REAL NOT NULL DEFAULT 0.5,
    user_advantage      REAL NOT NULL DEFAULT 0.5,
    long_term_value     REAL NOT NULL DEFAULT 0.5,
    legal_risk          REAL NOT NULL DEFAULT 0,
    financial_risk      REAL NOT NULL DEFAULT 0,
    reputational_risk   REAL NOT NULL DEFAULT 0,
    execution_risk      REAL NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'IDENTIFIED',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idea_id         UUID REFERENCES business_ideas (id) ON DELETE SET NULL,
    stage           TEXT NOT NULL DEFAULT 'IDEA' CHECK (stage IN (
                        'IDEA', 'HYPOTHESIS', 'MVP', 'TEST', 'OUTREACH', 'FEEDBACK',
                        'FIRST_CUSTOMER', 'DELIVERY', 'PAYMENT', 'EVALUATION'
                    )),
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revenue_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID REFERENCES customers (id) ON DELETE SET NULL,
    amount_usd      NUMERIC(10, 2) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
