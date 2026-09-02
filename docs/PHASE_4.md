# Phase 4 — Progress report (foundation increment 4B–4E)

This is **not** a "Phase 4 complete" report — Phase 4's spec names 30
subsystems and this increment builds 4 of them (the foundation layer:
Core Orchestrator extension, Capability Registry, Tool Registry
extension, Permissions/Resource/Autonomy). See `docs/PHASE_4_AUDIT.md`
for the full audit, dependency list, and recommended order for
everything not yet built, and this file's "Next" section for what a
future increment should tackle first.

## What was required before any code

Per the spec's own "FIRST ACTION": a complete audit of Phase 1-3 before
writing anything (`docs/PHASE_4_AUDIT.md`, 21 sections, verified against
the actual repository and live test runs — not recalled from memory).
The audit surfaced three points needing an explicit decision rather than
an assumption; all three are resolved:

1. **Phase 3's `AutonomyLevel` vs. Phase 4's autonomy scale** — kept
   separate (`AutonomyMode`, new), composing with the unchanged
   `PolicyEngine`. Proceeded additively per the audit's proposal.
2. **Self-modification safety boundary** — **user confirmed 2026-09-02**:
   self-modification always requires explicit human confirmation, at any
   autonomy level, no exceptions. Implemented as a hard carve-out in
   `PolicyEngine._auto_approved()`, not a default.
3. **Permission model extension approach** — proceeded additively
   (new columns/fields, existing SAFE/SENSITIVE behavior unchanged).

## What was built

### `backend/app/selfcode/` — Self-modification proposals

`SelfModificationProposal` (title/reason/diff/test_plan/rollback_plan/
affected_components/risk/status) is the durable record of "Jarvis wants
to change its own code." `SelfCodeService.propose()` always creates the
row and always calls `PolicyEngine.evaluate(kind="self_modification")` —
which is now hard-coded to return `Decision.ASK` (never auto-approved),
verified by `test_selfcode.py::test_propose_always_asks_even_at_max_autonomy_level`
(proves the property directly: proposes at `LEVEL_5_SAFE_AUTOMATION`,
still asks). `apply()`/`rollback()` raise `NotImplementedError` — no
sandbox/snapshot infrastructure exists yet (§16/§17b of the audit), and
faking "applied" would violate this project's REAL/MOCKED/NOT_TESTED
discipline. Reuses the existing Approval Center/`ConfirmationManager` —
no second approval mechanism.

### `backend/app/capabilities/` (extended) — Capability Registry

The Phase 3 discovery table (`capabilities`) gained `usage_count`,
`success_count`, `owner`, `status`, `composed_of` columns (migration
`0004_phase4.sql`, all additive). `CapabilityDiscoveryService` gained:
- `register_internal()` — register an existing internal capability
  (idempotent by a stable `internal:<name>` source key).
- `compose()` — record a composite capability from component ids.
- `search()` — ILIKE text search over name/purpose.
- `record_usage()` — increment usage/success counts.

`CapabilityUsageTracker` is a new `EventBus` wildcard subscriber (same
pattern as `AuditLogger`) that calls `record_usage()` automatically for
any registered capability whose `metadata.tool_name` matches a
`TOOL_COMPLETED` event — zero changes to `plan_execution.py` or either
orchestrator.

### `backend/app/autonomy/` — AutonomyMode + resource budgets

`AutonomyMode` (OBSERVE/ADVISE/ASSIST/AUTONOMOUS/SUPERVISED_AUTONOMY/
HUMAN_GATED), stored via the existing `preferences` table under a new
key (`autonomy_mode`), default `AUTONOMOUS`. `ResourceBudgetService` is
an opt-in money/API-call/action/time budget tracker
(`resource_budgets` table) — separate from, and not a replacement for,
the wallet's own hard financial limits. A scope+kind with no configured
limit is treated as unlimited and untracked (Postgres `NUMERIC` has no
infinity to store as a limit).

### REST surface

`backend/app/api/phase4_routes.py`: `/selfcode/proposals` (POST/GET),
`/capability-registry/{search,register,compose}`, `/autonomy/mode`
(GET/POST), `/autonomy/budgets` (POST) + `/autonomy/budgets/{scope}/{kind}`
(GET). Same conventions as Phase 3: bearer-token gated, 503 (not a crash)
when a service isn't configured.

## Database

`memory/migrations/0004_phase4.sql` — one widened CHECK constraint
(`approvals.kind` gains `'self_modification'`), five new columns on
`capabilities`, and two new tables (`self_modification_proposals`,
`resource_budgets`). Applied and verified idempotent against both local
`jarvis` and `jarvis_test` Postgres 16 databases (re-run confirmed
no-op on the second pass).

## Tests

154 tests total (was 138 at the end of Phase 3):
```
backend: 142 passed, 1 skipped   (7.2s, Postgres reachable)
backend: 40 passed, 103 skipped  (Postgres deliberately unreachable — graceful degradation confirmed)
agent:    11 passed
```
15 new backend tests: `test_selfcode.py` (5, including the core safety
property test above), `test_capability_registry.py` (5),
`test_autonomy.py` (5). All construct services directly against real
Postgres, per this repo's existing test convention — no new pattern
introduced.

## Android / APK

No Android source file changed in this increment (Phase 4 so far is
backend-only foundation work). Verified anyway, per the instruction to
test all 4 phases:
- `npx tsc --noEmit` — clean.
- `./gradlew assembleDebug` (same command verified in the Phase 3 APK
  delivery) — rebuilt successfully; targets `compileSdk`/`targetSdk` 36
  (Android 16), already the project's configuration since Phase 3, not
  something this increment changed.
- APK path: `android/android/app/build/outputs/apk/debug/app-debug.apk`
  (same path, same build command as documented in the Phase 3 delivery
  and the local-build instructions given after the GitHub Actions/Release
  path proved unavailable in this session).

## REAL / MOCKED / PARTIAL / NOT TESTED

| Area | Status |
|---|---|
| Self-modification proposal creation, policy gate, audit | REAL |
| Self-modification hard-never-auto-approved property | REAL, directly tested |
| Self-modification `apply()`/`rollback()` | NOT IMPLEMENTED (honest `NotImplementedError`, no sandbox exists) |
| Capability Registry (register/compose/search/usage tracking) | REAL |
| `CapabilityUsageTracker` (event-driven usage stats) | REAL |
| `AutonomyMode` (get/set, persisted) | REAL |
| `ResourceBudgetService` (limit/consume/exceeded) | REAL |
| Everything else in the Phase 4 spec (Agent Runtime, Workflow Engine, Research/Learning/Prediction/Decision Engines, Economic Engine, Business OS breadth, self-healing/testing/update execution, Command Center, monitoring/observability, 20+ more) | NOT BUILT — see docs/PHASE_4_AUDIT.md §16/§19 |

## Known limitations

Same sandbox limitations as Phase 3 (no Docker daemon, no Android
emulator/device, GitHub search network-blocked by this session's proxy)
— unchanged, not re-verified here since nothing in this increment touches
them. New to this increment: no scheduler/background execution exists
yet, so `AutonomyMode`/budgets are data models a future engine will
consult — nothing autonomous runs continuously yet (see
docs/PHASE_4_AUDIT.md §1 on the "no persistent host" finding, which still
applies unchanged).

## Technical debt

- `ResourceBudgetService.consume()` is check-then-update, not atomic —
  fine for this single-process, single-owner deployment, documented as a
  real limitation for any future multi-worker deployment.
- `CapabilityUsageTracker._resolve()` does a full table scan on every
  cache miss (bounded to 500 rows) rather than an indexed lookup —
  acceptable at today's capability-table size, worth revisiting once a
  registry has hundreds of entries.

## Next recommendations (recommendations only — not started automatically)

Following the audit's §19 order:
1. **Agent Runtime (4F)** — the biggest genuinely-new subsystem; nothing
   in Phase 1-3 has an "Agent" concept to extend.
2. **Task Engine / Workflow Engine (4G-4H)** — needs a real
   scheduler/background execution model first (see audit §1/§10/§16)
   before "continuous operation" means anything beyond a manual trigger.
3. **Self-Diagnostics → Self-Healing (4O-4P)** — natural next steps once
   an Agent Runtime exists to act on diagnoses; still gated on real
   sandbox infrastructure before Self-Coding (4Q) can move past proposal
   creation into actual `apply()`.

Do not start another Phase 4 sub-phase automatically — check in first,
per the same protocol this increment followed.
