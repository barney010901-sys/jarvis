# Decisions

Short, dated records of choices made where the spec left room for more than
one reasonable approach. Newest first.

## Phase 2 (2026-09-01)

### Backend imports the agent package via PYTHONPATH, not packaging

**Decision:** the backend imports `agent.provider...` directly, and both
`backend/pytest.ini` and the run instructions in `backend/README.md` add
the repo root to `PYTHONPATH` (alongside `backend/` itself) rather than
vendoring/copying `agent/` into `backend/` or setting up a proper
multi-package build (a `pyproject.toml` workspace, `pip install -e`, etc).

**Why:** the monorepo has no shared Python packaging yet, and adding one
just to satisfy this one cross-package import would be a bigger change
than the import itself justifies. `PYTHONPATH=..` is the smallest thing
that makes `agent` importable from `backend/` in dev, tests, and Docker
(see `backend/Dockerfile`, which now builds from the repo root and sets
`PYTHONPATH=/app:/app/backend`). If the two ever need to be installed
independently (e.g. `agent` reused by a second service), revisit with real
packaging then.

### ClaudeOrchestrator is additive, not a replacement

**Decision:** Phase 2 adds `backend/app/orchestrator/claude_orchestrator.py`
implementing the same `OrchestratorInterface` as Phase 1's
`StubOrchestrator` — the latter is untouched in behavior (only a small
refactor to share `execute_plan`, see below) and still exists, still
passes its original tests, and is still what `deps.py` falls back to when
Postgres or Claude aren't available.

**Why:** the task explicitly forbids replacing the existing architecture
or creating a duplicate orchestration system. `OrchestratorInterface` was
designed in Phase 1 specifically so a real implementation could be added
alongside the stub (see docs/ARCHITECTURE.md's original description:
"everything downstream of this interface... can be swapped without the
API/WebSocket layer knowing"). Keeping `StubOrchestrator` also means the
backend still runs with zero external dependencies (no Postgres, no API
key) for local development and CI.

### Plan execution is shared, not duplicated between orchestrators

**Decision:** the tool-lookup/permission-gate/tool-execution loop that
`StubOrchestrator` had inline in Phase 1 is now `backend/app/orchestrator/
plan_execution.py`'s `execute_plan()`, called by both `StubOrchestrator`
and `ClaudeOrchestrator`. Same event sequence, same behavior — verified by
re-running the Phase 1 orchestrator tests unchanged after the refactor.

**Why:** without this, "Claude reasoning" would have meant copy-pasting
the tool loop into a second file, which is exactly the "duplicated logic"
the code-quality rules and the task's "do not create duplicate... tools"
instruction warn against.

### Planner failures fall back, they don't fail the task

**Decision:** `ClaudePlanner` catches `ProviderError`/JSON-parse failures
and falls back to `StubPlanner`'s deterministic 3-step plan rather than
failing the task outright.

**Why:** a malformed or unavailable planning call is a degraded-quality
problem, not a hard failure — the orchestrator can still make progress
with a generic plan. This is the same "graceful fallback" principle the
task asks for at the provider level, applied one layer up.

### Working memory stores plain data, not live objects

**Decision:** both orchestrators store the plan in `WorkingMemory` as a
list of plain dicts (`{"description": ..., "tool_name": ...}`), not the
`Plan`/`PlanStep` dataclass instances themselves.

**Why:** `PostgresWorkingMemory.value` is a `JSONB` column (see
`memory/schema.sql`) — it can only hold JSON-serializable data. Since
nothing in Phase 1 ever read the stored plan back, changing what's stored
was a safe, non-breaking change, and it makes the in-memory and
Postgres-backed implementations behave identically instead of the
in-memory one silently tolerating non-serializable values the Postgres one
would reject.

### Deps wiring became an explicit async `initialize()` in Phase 2

**Decision:** `backend/app/deps.py`'s Phase 1 `lru_cache`d getters (each
constructing its object lazily and synchronously on first call) were
replaced by one `initialize()` coroutine, called from `app.main`'s FastAPI
`lifespan`, that builds everything once and stores it in a module-level
dict; the `get_*` functions just read that dict.

**Why:** Postgres-backed stores need an `asyncpg.Pool`, which can only be
opened with `await` — there's no way to keep the old "construct lazily
inside a sync function" pattern once any dependency requires async setup.
Doing it once, explicitly, at startup (rather than "first request pays the
connection cost") also means a connection failure is visible in the
startup log immediately, not on some later, unrelated request.

### Phase 2 intelligence features require Postgres — no in-memory duplicate

**Decision:** `backend/app/deps.py` has exactly one fallback axis, not a
matrix: either Postgres **and** Claude are both available (the full
`ClaudeOrchestrator` stack — memory, knowledge, profile, tasks, cost, all
Postgres-backed) or the backend runs the complete Phase 1 stack
(`StubOrchestrator`, in-memory memory, no knowledge/profile/suggestions at
all). There is no in-memory `KnowledgeStore`/`ProfileStore`/
`SuggestionQueue` implementation.

**Why:** the task is explicit about not building a second memory/knowledge
architecture. An in-memory knowledge base that forgets everything on
restart wouldn't actually deliver what sections 2F–2Q ask for (durable,
reusable knowledge) — it would just be a different, half-working
implementation of the same interface, which is worse than not having one
and clearly saying so. Tests that need these stores use a real local
Postgres and `pytest.skip()` if one isn't reachable (see
`backend/tests/conftest.py` and every `test_*.py` with a `pool` fixture) —
they never fall back to a fake in-memory substitute that would make a test
"pass" without proving anything.

### Knowledge search uses trigram similarity, not substring matching

**Decision:** `PostgresKnowledgeStore.search()` filters and ranks by
PostgreSQL's `pg_trgm` `similarity()` function, not `ILIKE '%query%'`.

**Why:** the callers that matter most (`ContextEngine`, `KnowledgeService.
find_high_confidence_answer`) pass a full natural-language message as the
query (e.g. "I'm getting a CORS error"), which will essentially never
appear verbatim inside a concise knowledge title/content ("Fix CORS
error"). Trigram similarity matches on shared character sequences instead
of requiring one string to literally contain the other, which is what
actually made the cost-hierarchy short-circuit work in testing — the
first implementation (ILIKE) silently never matched anything and was
caught by `test_skips_claude_when_high_confidence_knowledge_already_exists`.

### Knowledge deduplication uses `difflib`, not an embeddings API

**Decision:** `backend/app/knowledge/similarity.py` compares candidate
title/content via stdlib `difflib.SequenceMatcher`, not a vector
embedding call to any provider.

**Why:** calling an embeddings endpoint for every piece of candidate
knowledge would itself be exactly the kind of "avoidable request" section
2E asks the system to minimize. `difflib` is free, local, and — per the
dedup tests in `backend/tests/test_knowledge.py` — good enough to merge
near-duplicate titles/content while still creating separate records for
genuinely different facts. pgvector remains the documented upgrade path
(`memory/README.md`) if semantic (not just lexical) dedup is needed later.

### Evaluation stays deterministic — no second Claude call to grade the first

**Decision:** `EvaluationEngine` (2U) runs fixed checks (did every tool
succeed, is there response text, do any files the plan expected actually
exist) rather than asking Claude "did this task succeed?".

**Why:** matches 2E's cost hierarchy directly, and a self-graded LLM
response is a weaker signal than checking the actual side effects (tool
results, filesystem) it produced. `PARTIAL`/`NEEDS_REVIEW` verdicts exist
precisely so ambiguous cases aren't silently marked `SUCCESS`.

### Proactive learning makes zero Claude calls

**Decision:** `ProactiveLearningEngine.run_cycle()` only reads
`InterestEngine.top_interests()` and writes a templated
`FUTURE_RELEVANT_KNOWLEDGE` record + a `Suggestion` — it never calls a
model provider, and it's invoked manually (there is no background
scheduler in Phase 2), gated off by default via
`feature_proactive_learning`.

**Why:** the task is explicit: "do not constantly call Claude", "do not
automatically implement anything". A background loop that periodically
calls an LLM to decide what might be interesting is exactly the kind of
uncontrolled, hard-to-audit cost and behavior the task warns against for
this phase. What's here proves the shape (interest -> candidate knowledge
-> suggestion) without that risk; a real "go research this" capability
needs the web-search/browser tools this phase deliberately leaves as
interfaces only (2Z), so it's the natural Phase 3 extension point.

### Project references (goals/interests/workflows) are soft, not FK-enforced

**Decision:** `goals.project_slug`, `interests.project_slug`, and
`workflows.project_slug` are plain `TEXT` columns with an index, not
`REFERENCES projects (slug)` foreign keys.

**Why:** the orchestrator records interest/workflow signals against
whatever `project` string the caller passes (e.g. `"default"`) without
requiring a corresponding `projects` row to be created first — the same
way `knowledge.project` and `long_term_memory.project` already worked in
Phase 1/2. A hard FK would mean every new project string needs an
explicit `upsert_project()` call before any signal about it could be
recorded, which the orchestrator doesn't currently guarantee. This is a
correctness fix made during Phase 2 development (caught by
`backend/tests/test_profile.py` failing with
`ForeignKeyViolationError`) before the migration was ever committed —
`memory/migrations/0002_phase2.sql` reflects the corrected, soft-reference
version, not a later change to a shipped constraint.

### The event vocabulary gained `task.delta` for streaming

**Decision:** beyond the Phase 2 event list given in the task
(`context.updated`, `task.evaluating`, `knowledge.created`,
`knowledge.updated`, `interest.detected`, `suggestion.created`),
`EventType` also gained `task.delta`, carrying one streamed text chunk
each.

**Why:** 2A requires real streaming reach the Android app, and the
existing architecture's only channel for that is the `/ws` event stream
(2W: "do not create a second event bus"). Without a per-chunk event type,
"streaming" would have meant either a second WebSocket protocol just for
text deltas, or buffering the whole response before sending anything —
both worse options. `task.delta` is additive to the existing enum/model
(`backend/app/events/models.py`), forwarded by the same `/ws` handler, and
handled by the same Android event log (`useJarvisSocket`), just consumed
differently by `useChatMessages` (appended into the pending bubble) vs.
`TaskProgressPanel` (filtered out — see its own comment).

### `agent.provider`'s streaming interface keeps a side-effect `last_usage`

**Decision:** `AIProvider.stream()` still returns `AsyncIterator[str]`
(unchanged from Phase 1); token usage is captured as a `self.last_usage`
attribute on the provider instance after the stream completes, rather than
changing the return type to something like
`AsyncIterator[str | UsageEvent]`.

**Why:** every caller of `stream()` (Android-facing chunk forwarding in
`ClaudeOrchestrator`) only wants text chunks in the loop body; folding
usage into the yielded type would force every call site to filter/cast.
`ModelRouter` tracks which provider instance actually served the last
call (`last_used_provider`/`last_used_role`, since a mid-stream failure
can fall back to a different provider) specifically so callers can read
`last_usage` off the right instance for cost tracking. This is a
pragmatic compromise, documented here so it isn't mistaken for an
oversight.

## 2026-09-01 — In-process event bus instead of Redis/NATS for Phase 1

**Decision:** implement `EventBus` as an in-memory asyncio pub/sub, not
backed by an external broker.

**Why:** Phase 1 runs a single backend process; a broker adds an
operational dependency with no present benefit. The bus is written behind
`EventBus`'s public API (`publish`, `subscribe`, `unsubscribe`) so a
Redis/NATS-backed implementation can replace it later without touching the
orchestrator, permissions system, or WebSocket layer.

## 2026-09-01 — In-memory MemoryStore instead of a live PostgreSQL connection

**Decision:** `WorkingMemory` / `ShortTermMemory` / `LongTermMemory` are
implemented as in-process dict-backed stores in Phase 1, while
`/memory/schema.sql` defines the target PostgreSQL schema (pgvector-ready)
up front.

**Why:** wiring a real database dependency into Phase 1 would make the
"make sure everything runs" bar depend on external infrastructure being
available in every environment that clones this repo. The schema is
written now so the interfaces are designed against the real target shape;
swapping in a `PostgresMemoryStore` in a later phase is an implementation
detail behind the same `MemoryStore` interface, not a redesign.

## 2026-09-01 — pgvector column present but commented out

**Decision:** `schema.sql` includes an `embedding vector(1536)` column on
`long_term_memory`, commented out, with the `CREATE EXTENSION` statement
also commented out.

**Why:** enabling `pgvector` requires the extension to exist in the target
Postgres instance, which Phase 1 does not provision. Documenting the exact
column now avoids a schema migration surprise when vector search is added;
uncommenting is the entire Phase-2 change.

## 2026-09-01 — Coding-agent integration is a documented interface, not a fake

**Decision:** `agent/coding_agent/interface.py` defines
`CodingAgentInterface` with a docstring describing exactly how a real
Claude Code integration should implement it (subprocess invocation,
working directory, streaming output back through the event bus). No
implementation is provided, and no method silently returns fabricated
"success".

**Why:** the task explicitly says "do not fake this integration." A stub
that returns fake success would be worse than no integration, because it
would let the evaluation layer (Phase 2+) believe a coding task completed
when nothing ran.

## 2026-09-01 — Placeholder tools are either genuinely safe-and-functional, or explicitly `NotImplementedError`

**Decision:** `FilesystemReadTool` and `ProjectInspectionTool` are real,
working, sandboxed-to-the-repo implementations (SAFE). `GitHubTool`,
`BrowserTool`, and `WebSearchTool` are registered with correct metadata
(name, description, input schema, permission level) but their `execute`
raises `NotImplementedError` with a message pointing at the real
integration to wire in.

**Why:** matches "do not fake integrations" while still giving the
orchestrator and permission system real tools to exercise end-to-end in
tests (a SAFE tool that actually does something, and a SENSITIVE tool that
actually goes through the confirmation gate).

## 2026-09-01 — Bearer-token auth placeholder

**Decision:** `backend/app/auth` checks a single static bearer token from
`JARVIS_API_TOKEN` (env var), not a full user/session system.

**Why:** Phase 1 has exactly one client (the Android app, one user). A
static shared secret is the simplest thing that (a) is not "no auth at
all" and (b) doesn't block on choosing a long-term identity provider
before the rest of the system can be built. Swapping in real auth later
only touches `backend/app/auth`.

## 2026-09-01 — Android app talks to the backend only

**Decision:** the Expo app has zero AI/business logic — no direct calls to
Claude or any provider, no local task planning. It renders the event
stream from the backend WebSocket and sends user messages/confirmations
back over REST/WebSocket.

**Why:** required by the task ("do not put AI business logic directly into
the Android application") and keeps the provider swap in `/agent` from
ever requiring an app release.
