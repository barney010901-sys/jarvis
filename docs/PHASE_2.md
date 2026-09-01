# Phase 2 — Intelligence + Memory + Claude

Real Claude integration, model routing, PostgreSQL-backed memory, an
extended context engine, token/cost tracking, a knowledge system with
deduplication and learning, a structured user/project/interest/goal
profile, proactive (but non-intrusive) learning, explicit task lifecycle,
deterministic evaluation, and an audit trail — built as an **evolution** of
the Phase 1 architecture (docs/PHASE_1.md), not a rewrite. Every Phase 1
component either still exists unchanged (`StubOrchestrator`,
`StubPlanner`, in-memory stores, the event bus, the tool registry, the
Android app's chat/voice/confirmation UI) or was extended in place
(`ContextEngine`, `PlanStep`, `EventType`, `AIProvider`).

## Files changed

- `backend/app/config.py` — Phase 2 settings (model routing, budget,
  feature flags), additive.
- `backend/app/events/models.py` — added `EventType` values (`context.
  updated`, `task.evaluating`, `knowledge.created`, `knowledge.updated`,
  `interest.detected`, `suggestion.created`, `task.delta`).
- `backend/app/memory/store.py` — added `LongTermMemory.delete()`.
- `backend/app/orchestrator/stub_orchestrator.py` — refactored to share
  `plan_execution.execute_plan()` (identical behavior; its own tests still
  pass unchanged).
- `backend/app/orchestrator/__init__.py`, `backend/app/context/__init__.py`
  — export the new additions.
- `backend/app/planner/interface.py` — added optional `PlanStep.
  expected_file`.
- `backend/app/context/engine.py` — extended `ContextEngine` with optional
  `knowledge_service`/`profile_store`, new `ContextBundle` return type,
  local history summarization/truncation, dedup of long-term facts.
- `backend/app/deps.py` — rewritten from `lru_cache` getters to an
  explicit async `initialize()` (see docs/DECISIONS.md); same public
  getter names.
- `backend/app/main.py` — added a FastAPI `lifespan` calling `deps.
  initialize()`/`shutdown()`.
- `backend/requirements.txt` — added `asyncpg`.
- `backend/pytest.ini` — `pythonpath` now includes the repo root (for
  `agent`).
- `backend/.env.example` — Phase 2 environment variables.
- `backend/Dockerfile`, `docker/docker-compose.yml` — build context moved
  to the repo root (needed for the `agent` package); Postgres init mounts
  both `schema.sql` and the new migration in order.
- `agent/provider/base.py` — added `complete()`, `Usage`, `ProviderResult`,
  `ProviderError` alongside the unchanged `stream()`.
- `agent/provider/claude_provider.py` — real retries/timeouts, `complete()`
  implementation, `last_usage` tracking.
- `agent/provider/__init__.py` — exports the new names.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` — updated/extended (not
  replaced) for Phase 2.
- `README.md` — status line.

## Files created

**Database**
- `memory/migrations/0002_phase2.sql` — knowledge, profile_facts,
  preferences, projects, goals, interests, workflows, suggestions, tasks,
  audit_log, token_usage, knowledge_relationships. Idempotent; documented
  in `memory/README.md`.

**Agent**
- `agent/provider/router.py` — `ModelRouter` (fast/primary/fallback
  roles), `build_claude_router()`.
- `agent/provider/costs.py` — approximate per-token pricing table.
- `agent/provider/fake_provider.py` — deterministic `AIProvider` test
  double.
- `agent/tests/test_router.py` — router/fallback/cost-estimate tests.

**Backend — new packages**
- `backend/app/db/` — asyncpg pool (`pool.py`).
- `backend/app/knowledge/` — models, interface, Postgres store,
  similarity, service.
- `backend/app/profile/` — models, interface, Postgres store, interest
  engine, workflow detector.
- `backend/app/suggestions/` — models, interface, Postgres store, service.
- `backend/app/proactive/` — `learning.py` (`ProactiveLearningEngine`).
- `backend/app/cost/` — models, store (in-memory + Postgres), tracker.
- `backend/app/tasks/` — models, interface, in-memory store, Postgres
  store.
- `backend/app/evaluation/` — `engine.py` (`EvaluationEngine`).
- `backend/app/audit/` — store (in-memory + Postgres), `logger.py`
  (`AuditLogger`).
- `backend/app/learning/` — `correction_detector.py`, `pipeline.py`
  (`LearningPipeline`).
- `backend/app/orchestrator/claude_orchestrator.py` — `ClaudeOrchestrator`.
- `backend/app/orchestrator/plan_execution.py` — shared tool-execution
  loop.
- `backend/app/planner/claude_planner.py` — `ClaudePlanner`.
- `backend/app/prompts_loader.py` — loads `/prompts/*.md`.
- `backend/app/memory/postgres_store.py` — Postgres-backed
  `WorkingMemory`/`ShortTermMemory`/`LongTermMemory`.

**Backend — new tests** (all in `backend/tests/`)
- `test_postgres_memory.py`, `test_knowledge.py`, `test_profile.py`,
  `test_suggestions_and_proactive.py`, `test_cost_tracker.py`,
  `test_context_engine.py`, `test_tasks_evaluation_audit.py`,
  `test_claude_orchestrator.py`.

**Android**
- No new files; `src/api/events.ts`, `src/hooks/useChatMessages.ts`,
  `src/components/TaskProgressPanel.tsx` extended for the new event
  types and `task.delta` streaming.

## Architecture changes

See `docs/ARCHITECTURE.md` ("Phase 2 additions") for the module map and
`docs/DECISIONS.md` for the reasoning behind each one. In one sentence per
theme:

- **Orchestration**: `ClaudeOrchestrator` added alongside
  `StubOrchestrator` (not replacing it), sharing `execute_plan()`.
- **Planning**: `ClaudePlanner` added alongside `StubPlanner`, falling back
  to it on any failure.
- **Memory**: Postgres-backed implementations of the exact same three
  interfaces from Phase 1.
- **Context**: `ContextEngine` extended in place with knowledge/profile
  sources and local history summarization.
- **New capabilities** (knowledge, profile, suggestions, proactive
  learning, cost tracking, task lifecycle, evaluation, audit) are new
  modules, composed by `ClaudeOrchestrator` and `LearningPipeline` — none
  of them replace or duplicate an existing Phase 1 system.

## Database migrations

1. `memory/schema.sql` (Phase 1, unchanged) — `working_memory`,
   `short_term_memory`, `long_term_memory`.
2. `memory/migrations/0002_phase2.sql` (new) — everything else. Documented
   inline and in `memory/README.md`. Idempotent (`CREATE TABLE IF NOT
   EXISTS`, `CREATE INDEX IF NOT EXISTS`). Applied in this exact order
   against a real local PostgreSQL 16 instance during development; see
   "Tests performed" below.

No destructive changes — nothing from Phase 1's schema was altered or
dropped.

## Environment variables (new, all in `backend/.env.example`)

```
JARVIS_MODEL_PRIMARY, JARVIS_MODEL_FAST, JARVIS_MODEL_FALLBACK
CLAUDE_MAX_TOKENS, CLAUDE_TIMEOUT_SECONDS, CLAUDE_MAX_RETRIES
TOKEN_BUDGET_DAILY_USD
KNOWLEDGE_SIMILARITY_THRESHOLD, KNOWLEDGE_MIN_CONFIDENCE_TO_SKIP_CLAUDE
JARVIS_USE_POSTGRES, JARVIS_USE_CLAUDE
FEATURE_MODEL_ROUTING, FEATURE_AUTO_KNOWLEDGE_EXTRACTION,
FEATURE_CONTEXT_COMPRESSION, FEATURE_PROACTIVE_SUGGESTIONS,
FEATURE_PROACTIVE_LEARNING
```

`DATABASE_URL` and `ANTHROPIC_API_KEY` already existed in Phase 1 as
unused placeholders; they're load-bearing now.

## Commands to run

```bash
# 1. Database (once, in order)
psql "$DATABASE_URL" -f memory/schema.sql
psql "$DATABASE_URL" -f memory/migrations/0002_phase2.sql

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set JARVIS_API_TOKEN, DATABASE_URL, ANTHROPIC_API_KEY
PYTHONPATH=.. uvicorn app.main:app --reload

# 3. Tests
cd backend
PYTHONPATH=.. pytest                                    # 36 pass, rest skip without Postgres
TEST_DATABASE_URL=postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test PYTHONPATH=.. pytest   # all 72
cd ../agent && PYTHONPATH=.. pytest                     # 11

# 4. Android (unchanged from Phase 1)
cd android && npm install && npm start
```

## Tests performed (this session, in this sandbox)

A real local PostgreSQL 16 server was installed and run (no Docker daemon
available in this sandbox — see "Not tested" below) for all Postgres
integration tests.

- **Backend**: 72/72 pass with a reachable test Postgres
  (`TEST_DATABASE_URL`); 36/72 pass and 36 cleanly `pytest.skip()` (never
  fail or fake a pass) without one — verified both ways.
- **Agent**: 11/11 pass (no DB dependency).
- **Live boot, Postgres connected, Claude disabled** (`JARVIS_USE_CLAUDE=
  false`, real `DATABASE_URL`): started via real `uvicorn`, hit `/health`
  and `POST /messages`, then confirmed via `psql` directly against the
  database that the conversation turns were actually persisted —
  `StubOrchestrator` running on real Postgres-backed memory, not a mock.
- **Live boot, Postgres unreachable** (`DATABASE_URL` pointed at a closed
  port): confirmed the backend logs the connection failure, falls back to
  the Phase 1 in-memory stack, and keeps serving `/health` and `/messages`
  successfully rather than crashing.
- **Android**: `npx tsc --noEmit` clean, `expo-doctor` 21/21, `expo export
  --platform android` bundles (931 modules) — all re-verified after the
  `task.delta`/new-event-type changes.
- **`docker compose config`**: validated the compose file (build context,
  volumes, env) parses correctly; the actual image was **not** built (no
  Docker daemon in this sandbox — see below).

## REAL components

- PostgreSQL-backed working/short-term/long-term memory, knowledge store,
  profile store (facts/preferences/projects/goals/interests/workflows),
  suggestion queue, task lifecycle store, audit log, and token-usage
  store — all exercised against a real local PostgreSQL 16 instance.
- Knowledge deduplication (`difflib` + trigram similarity), confidence
  adjustment, user-correction handling — real logic, real DB round-trips.
- Interest scoring with recency decay, workflow detection after repeated
  evidence — real logic, real DB round-trips.
- `EvaluationEngine`'s checks, including the real `filesystem.read` tool
  call to verify an expected file actually exists.
- `AuditLogger` — a real wildcard `EventBus` subscriber persisting to
  `audit_log`.
- `CostTracker` — real cost estimation and budget-threshold logic (against
  both an in-memory store and Postgres).
- The full event-driven flow (`user.message` → ... → `task.completed`),
  including the new `context.updated`/`task.evaluating`/`knowledge.*`/
  `task.delta` events, verified end-to-end via `ClaudeOrchestrator`.
- `ClaudeProvider`'s `complete()`/`stream()` code paths, retry/backoff, and
  error classification — real `anthropic` SDK code, unit-testable
  independent of a live key (constructor/validation tests only — see
  "Not tested").
- Android: real WebSocket client, real event-log rendering, real
  chat-bubble streaming logic (`task.delta` accumulation) — verified via
  `tsc`, `expo-doctor`, and a real Metro bundle.

## MOCKED components

- **The LLM itself**, in every orchestrator-level test
  (`test_claude_orchestrator.py`): `FakeProvider` stands in for Claude, so
  `ClaudeOrchestrator`'s full flow (context → planner → "Claude" →
  tools → evaluation → learning → knowledge update) is proven correct
  without a network call or API key. This is the one deliberate mock in
  the suite, and it's exactly why it's a `Fake*` class name, not a
  disguised stub.

## NOT TESTED

- **A real call to the Anthropic API.** No `ANTHROPIC_API_KEY` was
  available in this session/sandbox. `ClaudeProvider`'s HTTP-level
  behavior (actual streaming, actual token counts, actual rate limiting)
  is therefore unverified end-to-end — only its retry/error-classification
  logic and non-network code paths are.
- **Docker image build.** No Docker daemon in this sandbox (confirmed via
  `docker info` failing to reach the socket). `docker compose config`
  validated the compose file's structure; the Dockerfile itself was not
  built or run.
- **A real Android emulator/device running against the live backend.**
  Same limitation as Phase 1 — no Android SDK/emulator in this container.
- **pgvector / true semantic search.** Not enabled (still commented out in
  `memory/schema.sql`); all "similarity" in Phase 2 is lexical
  (`difflib`/trigram), not embedding-based.
- **Production-scale load/concurrency.** The event bus, connection pool
  sizing (`asyncpg` pool `max_size=10`), and cost-tracking counters were
  exercised at unit-test scale, not under real concurrent load.

## Known limitations

- **Correction detection is regex, not NLU.** `CorrectionDetector` only
  catches a few explicit phrasings ("use X instead of Y", "koristi X
  umesto Y", "don't use X, use Y"). Differently-phrased corrections are
  silently missed (not mis-detected) — see its module docstring.
- **Interest/topic extraction is keyword matching**, not topic modeling:
  `LearningPipeline.on_user_message` only records a signal when a known
  project technology string literally appears in the message.
- **Proactive learning has no scheduler.** It's a callable engine; nothing
  in Phase 2 invokes it periodically (see docs/DECISIONS.md).
- **No in-memory fallback for knowledge/profile/suggestions.** If Postgres
  is unavailable, those features are absent entirely (the backend runs
  Phase 1's stack), not degraded — a deliberate scope decision, not an
  oversight (see docs/DECISIONS.md).
- **Workflow/interest signals use soft (non-FK) project references** — a
  typo'd project string silently creates a new, separate interest/workflow
  bucket rather than erroring.

## Technical debt

- `backend/app/deps.py`'s `initialize()` builds a fairly large object
  graph in one function. It's linear and commented, but a real
  dependency-injection container (or splitting it per-subsystem) would
  scale better as more components are added in Phase 3.
- The backend depending on `agent/` via `PYTHONPATH` rather than proper
  packaging (docs/DECISIONS.md) works for a monorepo of this size but
  won't scale to a second service reusing `agent/`.
- `ClaudeOrchestrator`'s constructor takes 13 keyword arguments. Workable
  today; if Phase 3 adds several more collaborators, group related ones
  (e.g. all of knowledge/profile/proactive) into a small facade.

## Token/cost observations

- Pricing in `agent/provider/costs.py` is an illustrative, rounded table
  (USD per million tokens), not pulled from a live pricing source —
  adequate for budget *tracking*, not for billing reconciliation.
- The cost hierarchy's highest-value lever is the knowledge short-circuit
  (`KnowledgeService.find_high_confidence_answer`): when it hits, the
  primary model is never called at all (verified in
  `test_claude_orchestrator.py::test_skips_claude_when_high_confidence_
  knowledge_already_exists`) — this is the main mechanism for "avoid
  asking Claude something JARVIS already knows."
  `CostTracker.counters.avoidable_requests_avoided` tracks how often this
  fires.
- The planner uses the "fast" model role, not "primary" — every task
  incurs one fast-tier call plus one primary-tier call (unless the
  knowledge short-circuit fires and skips both).
- No caching of repeated identical prompts (e.g. Anthropic prompt caching)
  is wired in yet — a natural Phase 3 addition once real API usage
  patterns are observed.

## Recommended Phase 3

Per the task's own scope rule, none of this was attempted in Phase 2:
1. Real GitHub/browser/web-search tool execution (the interfaces already
   exist — see `backend/app/tools/placeholders.py`).
2. Real coding-agent (Claude Code) execution behind
   `agent/coding_agent/interface.py`.
3. Real STT/TTS in the Android app, replacing the push-to-talk demo
   handler.
4. A scheduler for `ProactiveLearningEngine` (cron/Celery/similar), plus
   wiring the web-search tool so proactive learning can discover, not just
   template, new knowledge.
5. pgvector-based semantic search, once an embedding source is chosen.
6. Real auth (replacing the static bearer token).

## Exact next steps

1. Get a real `ANTHROPIC_API_KEY` into a dev environment and re-run the
   live-boot check with `JARVIS_USE_CLAUDE=true` to validate the actual
   Anthropic API call path (streaming, token counts, rate-limit handling)
   that unit tests with `FakeProvider` couldn't cover.
2. Run `docker compose -f docker/docker-compose.yml up --build` somewhere
   with a Docker daemon to validate the Dockerfile/compose changes for
   real.
3. Pick one of the Phase 3 items above per the user's priority and repeat
   this phase's process: inspect → plan → implement the smallest working
   version → test → document.

**Stopping here, as instructed — not continuing to Phase 3 automatically.**
