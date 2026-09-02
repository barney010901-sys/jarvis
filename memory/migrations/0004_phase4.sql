-- Phase 4 (2026-09-02): additive foundation for the Capability Registry,
-- self-modification safety gate, and resource budgets. Every statement
-- here is additive/idempotent (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF
-- NOT EXISTS) — no existing table is dropped, no existing row is touched,
-- and no existing column changes meaning. See docs/PHASE_4_AUDIT.md for
-- why each piece exists and docs/DECISIONS.md for the reasoning.

-- Widen the Phase 3 approvals taxonomy so a self-modification proposal
-- can go through the exact same Approval Center / ConfirmationManager
-- flow as every other ASK decision — no second approval mechanism.
-- Widening a CHECK constraint's allowed values doesn't touch existing
-- rows (all of which already satisfy the wider constraint).
ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_kind_check;
ALTER TABLE approvals ADD CONSTRAINT approvals_kind_check CHECK (kind IN (
    'tool_install', 'wallet_transaction', 'communication',
    'destructive_operation', 'capability_install', 'self_modification', 'other'
));

-- Capability Registry: extends the Phase 3 `capabilities` table (already
-- discovery-oriented) with the usage/ownership/composition metadata a
-- registry needs, rather than creating a second capability table.
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS usage_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS owner TEXT;
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS composed_of TEXT[] NOT NULL DEFAULT '{}';

-- Self-modification proposals (section "Self-Coding Engine" / "Self-Update
-- Protocol"): every proposed change to Jarvis's own code is a durable row
-- here. `approval_id` links it to the shared `approvals`/ConfirmationManager
-- gate. `applied_at` is only ever set once real sandbox/snapshot tooling
-- exists (see docs/PHASE_4_AUDIT.md §16/§17b) — until then `apply()` in
-- code raises NotImplementedError, matching the existing GitHubTool/
-- BrowserTool pattern of "real interface, honest not-yet-implemented
-- execution."
CREATE TABLE IF NOT EXISTS self_modification_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_id         UUID REFERENCES approvals(id),
    title               TEXT NOT NULL,
    reason              TEXT NOT NULL,
    diff                TEXT NOT NULL,
    affected_components TEXT[] NOT NULL DEFAULT '{}',
    risk                TEXT NOT NULL DEFAULT 'unknown',
    test_plan           TEXT NOT NULL,
    rollback_plan       TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN (
                            'PROPOSED', 'APPROVED', 'REJECTED', 'APPLIED', 'ROLLED_BACK'
                        )),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    applied_at          TIMESTAMPTZ
);

-- Resource budgets (section "Resource Management" / "Autonomy Budget"):
-- a scope ('global', or 'objective:<id>' once objectives exist) x kind
-- ('money_usd' | 'api_calls' | 'actions' | 'time_seconds') limit/usage
-- pair. Domain services may consult this before spending; nothing in
-- Phase 1-3 is required to change to use it (opt-in, additive).
CREATE TABLE IF NOT EXISTS resource_budgets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('money_usd', 'api_calls', 'actions', 'time_seconds')),
    limit_amount    NUMERIC(14, 2) NOT NULL,
    used_amount     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    period_start    TIMESTAMPTZ NOT NULL DEFAULT now(),
    period_end      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope, kind, period_start)
);
