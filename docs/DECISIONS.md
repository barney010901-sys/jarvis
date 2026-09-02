# Decisions

Short, dated records of choices made where the spec left room for more than
one reasonable approach. Newest first.

## Phase 4 (2026-09-02, local model support)

### Local model support via Ollama — no API key, ClaudeOrchestrator reused as-is

**Decision:** added `agent/provider/ollama_provider.py` (`OllamaProvider`,
implements `AIProvider` against a locally-running Ollama server's REST
API — no API key, no cloud call) and `build_local_router()`
(`agent/provider/router.py`), selected in `deps.py` via
`JARVIS_USE_LOCAL_MODEL=true` (with Claude not configured). Explicit user
request, 2026-09-02: run Jarvis's reasoning against a local, open-weight
model instead of Claude — no cloud dependency, no API key, own identity.

**Why `ClaudeOrchestrator`/`ClaudePlanner` are reused unchanged, not
duplicated:** despite the class names, neither is actually Claude-specific
in implementation — both depend only on `ModelRouter`/`AIProvider`
(`agent/provider/base.py`), never the `anthropic` SDK. `deps.py` picks
`build_claude_router()` or `build_local_router()` based on which backend
is configured and hands the result to the exact same orchestrator/planner
pair either way. This matches the router abstraction's original design
intent (`docs/ARCHITECTURE.md`: "a future provider... just needs to
implement `AIProvider`").

**`intelligence_ready = claude_ready or local_model_ready`:** the
Phase 2/3/4 stack (knowledge/profile/wallet/etc.) only needs Postgres +
*some* model behind it — introduced as a new, additive gate alongside
the existing `claude_ready` (left with its original, narrower meaning:
"Claude specifically is configured and active" — still used as-is by
`HealthService`'s `claude` component check, which correctly reports
`NOT_CONFIGURED` when a local model is active instead). If both were
somehow enabled at once, Claude wins (a configured, paid API key is
assumed to be the deliberate, more capable choice) — see `deps.py`.

**A real model must still back "jarvis" — no training from scratch:**
`agent/provider/ollama/Modelfile` builds a model literally named "jarvis"
in Ollama's own registry (`ollama create jarvis -f Modelfile`, so
`ollama list`/`ollama run jarvis` show and run "jarvis", not its base
model's name) — but it has to `FROM` an existing open-weight model
(Gemma, Llama, Qwen, Mistral, DeepSeek, whichever the user has pulled).
Training an actual new model from zero needs data/compute/months of
specialized work this project cannot provide — explained directly to the
user rather than implied as achievable. This is the same honesty
principle as everywhere else in this project (REAL/MOCKED/NOT_TESTED,
never fabricate a capability that doesn't exist).

**Local inference quality/speed is honestly weaker than Claude's,
depending on hardware and the chosen base model** — not something code
can fix; the user was told this plainly before building this.

## Phase 4 (2026-09-02, foundation increment 4B-4E)

### The future coding agent uses the SAME `ANTHROPIC_API_KEY`, not a separate one

**Decision:** when `agent/coding_agent/interface.py`'s real implementation
is eventually built (still deliberately not implemented — see below), it
authenticates with the exact same `ANTHROPIC_API_KEY` already configured
for the rest of Jarvis (`backend/app/config.Settings.anthropic_api_key`),
inherited through the subprocess environment. There is one Anthropic API
key for the whole system, never a second one to separately obtain,
configure, or manage for "the coding agent" as if it were an independent
account. Explicit user question/confirmation, 2026-09-02: the coding
agent is not "a separate AI agent with its own key that eventually
becomes self-sufficient" — it's just another caller of the one credential
Jarvis already has, exactly like `ClaudeProvider`/`ModelRouter` are.
No amount of self-learning changes this: calling the real Claude API
always requires a real, valid API key — that's how the Claude API works,
not a Jarvis design choice self-learning could ever remove.

### Self-modification is hard-gated in `PolicyEngine`, not just defaulted that way

**Decision:** `PolicyEngine._auto_approved()` returns `False` immediately
for any `PolicyRequest(kind="self_modification")`, before any autonomy-level
branching runs. Confirmed explicitly by the user (2026-09-02, in response
to the Phase 4 audit's §17b question): a proposal to change Jarvis's own
running code always requires human confirmation, at every autonomy level
Phase 3 or Phase 4 defines. **Why a hard carve-out instead of a default:**
a default can be changed by a future autonomy-level/mode setting without
anyone noticing the consequence; a carve-out in the one function that
decides auto-approval cannot be bypassed by any such setting. See
`backend/app/selfcode/service.py` and docs/PHASE_4_AUDIT.md §17(b).

### `AutonomyMode` (Phase 4) is a new concept, not a replacement for Phase 3's `AutonomyLevel`

**Decision:** Phase 3's `AutonomyLevel` (1-5, `app.policy.models`) keeps
governing individual policy-gated actions exactly as before. Phase 4's
spec defines a different 6-level scale (0 Observe … 5 Human-Gated)
describing the posture of the continuous autonomous loop as a whole.
Rather than renumber or replace the enum Phase 3 tests and the
`preferences` table already depend on, Phase 4 adds `AutonomyMode`
(`app.autonomy.models`) as a distinct preference key
(`autonomy_mode`, vs. Phase 3's `autonomy_level`). Default is `AUTONOMOUS`,
not `HUMAN_GATED` — explicit user instruction (2026-09-02): "don't default
to human-gated." The two scales compose: an `AUTONOMOUS`-mode engine still
has every wallet/communication/self-modification action evaluated by the
unchanged `PolicyEngine`.

### Capability Registry extends the Phase 3 `capabilities` table, doesn't duplicate it

**Decision:** Phase 4's richer capability metadata (usage stats, owner,
status, composition) was added as new columns on the existing `capabilities`
table (migration `0004_phase4.sql`, all `ADD COLUMN IF NOT EXISTS`) rather
than a second table. `CapabilityDiscoveryService` gained `register_internal`/
`compose`/`search`/`record_usage` alongside its existing GitHub-discovery
methods — one capability store, whether an entry came from GitHub search
or was registered internally. `CapabilityUsageTracker` is a new wildcard-
style `EventBus` subscriber (same pattern as `AuditLogger`) that updates
usage stats from `TOOL_COMPLETED` events — zero changes to
`plan_execution.py` or either orchestrator.

### Self-code `apply()`/`rollback()` raise `NotImplementedError` on purpose

**Decision:** an APPROVED self-modification proposal is a real, audited
decision — it is not executed. This sandbox has no isolated execution
environment or snapshot/rollback tooling (docs/PHASE_4_AUDIT.md §16), and
the Phase 4 spec's own Self-Update Protocol requires that tooling exist
*before* any autonomous code change is actually applied. Matches the
established `GitHubTool`/`BrowserTool` pattern: correct interface, honest
`NotImplementedError` until the real capability exists — never faked.

### `approvals.kind` widened to include `'self_modification'`

**Decision:** `ALTER TABLE approvals DROP/ADD CONSTRAINT` in
`0004_phase4.sql` widens the CHECK constraint's allowed values. This
touches an existing Phase 3 table, but only by widening an enum-like
constraint — no existing row is affected (all satisfy the wider
constraint), no existing code path changes behavior, and it's what lets
self-modification proposals flow through the *same* Approval
Center/ConfirmationManager as every other Phase 3 approval, rather than a
second approval mechanism. Reversible by re-narrowing the constraint if
ever needed (no data loss either way).

## Phase 3 (2026-09-02)

### Phase 3 domains share Phase 2's one-fallback-axis rule

**Decision:** the wallet, communication, escalation, business, and
capability-discovery services are all constructed only when
`claude_ready` (Postgres reachable **and** Claude configured) — the exact
same gate Phase 2 used for knowledge/profile. `HealthService` is the one
exception: it's constructed unconditionally, because reporting on a
partially-configured stack is its entire purpose.

**Why:** consistent with the Phase 2 decision "Phase 2 intelligence
features require Postgres — no in-memory duplicate": these are all
genuinely new, Postgres-native systems, and building a second,
degraded/in-memory version of each just to have *something* work without
Postgres would be exactly the kind of parallel implementation the task
repeatedly warns against. One fallback (the complete Phase 1/2 stack), not
five partial ones.

### Phase 3 capabilities are tools, not a parallel orchestrator path

**Decision:** the wallet/communication/capability-research/business/
health services are exposed to Claude as `Tool` subclasses
(`backend/app/tools/phase3_tools.py`), registered into the existing
`ToolRegistry` and invoked through the existing `execute_plan()` —
`ClaudeOrchestrator` itself gained no new "if the user wants to spend
money, do X" branches.

**Why:** the task is explicit: reuse the existing Tool Registry, don't
build a second orchestration path. Since `ClaudePlanner` already turns a
request into tool-invoking steps, a wallet transaction is just another
tool call from the model's perspective — the SENSITIVE permission level
on `wallet.propose_transaction`/`communication.propose_reply` routes it
through the exact same confirmation gate every other sensitive tool uses.

### Plan steps carry `tool_args`

**Decision:** `PlanStep` gained an optional `tool_args: dict` field
(default `{}`), and `plan_execution.execute_plan()` merges it into the
tool call alongside the existing `project_root` default. `ClaudePlanner`'s
prompt now includes each tool's full input schema, not just its name, and
asks the model to fill in `tool_args` per step.

**Why:** this is a real, load-bearing gap Phase 3 exposed: Phase 1/2's
`PlanStep` had no way to pass tool-specific parameters at all — every
tool was invoked with only `project_root="."`, which happened to work by
accident for `project.inspect` (its argument is optional) and would have
silently failed for anything else. A wallet transaction needs
`amount_usd`/`vendor`/`category`/`purpose`; there was no way to supply
them before this change. Fixed once, generically, rather than special-
cased per tool.

### The wallet is a real ledger, not a real payment rail

**Decision:** `WalletStore.execute()` only ever adjusts the
`wallet_accounts.balance_usd` column in Postgres. There is no adapter to
a bank, card processor, or cryptocurrency network anywhere in the wallet
module, and none is planned for Phase 3.

**Why:** the task's own wallet section is emphatic about controls
(limits, policy gating, audit) but never supplies — nor could this
session obtain — real payment-processor credentials. Building a "real"
external wallet integration without genuine credentials to test it
against would mean shipping unverified financial code, which is
categorically worse than a well-tested internal ledger that enforces the
same limits/policy logic a real integration would need. The GREEN/YELLOW/
RED classification, limit enforcement, and audit trail are all real and
tested (see `backend/tests/test_wallet.py`); only the "move real money"
step is absent, and it's absent by design, not by oversight.

### Communication transmission is not faked

**Decision:** `CommunicationService`/`EscalationService` both depend on a
`CommunicationChannelAdapter`; the only implementation
(`NotConfiguredChannelAdapter`) raises `NotImplementedError` from
`send()`. Classification, policy gating, audit records, and (for
escalation) the minimum-necessary disclosure message are all real and
tested; nothing is ever actually delivered over SMS/email/a messaging
platform.

**Why:** identical reasoning to Phase 1's `GitHubTool`/`BrowserTool`
placeholders and to the wallet decision above — no real messaging-
platform credentials exist in this project, and a fake "send" that
silently no-ops would let the system believe a client was notified when
they weren't. `propose_reply()`/`EscalationService.evaluate()` both
return `delivered=False` with a clear reason in that case, and the caller
(the `communication.propose_reply` tool) surfaces that in its result
rather than reporting success.

### Capability discovery is real code; its network call is NOT_TESTED here

**Decision:** `agent... backend/app/capabilities/github_search.py` calls
the real, unauthenticated GitHub repository search API
(`api.github.com/search/repositories`) — no token, no mock response.

**Why, and why it's marked NOT_TESTED:** this session's own outbound
proxy blocks that specific endpoint (`GET
api.github.com/search/repositories` returns 403 "GitHub access is not
enabled for this session"; `GET api.github.com` itself returns 200 — the
network path exists, only the search endpoint is restricted). The code is
correct for an unrestricted deployment; `backend/tests/
test_capabilities_and_health.py::test_real_github_search_network_call`
attempts the real call and `pytest.skip()`s with the exact reason when
blocked, rather than mocking around the restriction. Dedup and storage
logic are tested separately against a trivial fake network client so
they're still verified even though the live call isn't.

### Migration `0003_phase3.sql` is additive; two FK looseness calls this
### time were caught before ever shipping

**Decision:** everything from Phase 1/2 (`schema.sql`, `0002_phase2.sql`)
is untouched; `0003_phase3.sql` adds `policies`, `approvals`,
`capabilities`, `contacts`, `communications`, `escalation_events`,
`wallet_accounts`, `wallet_transactions`, `business_ideas`, `customers`,
`opportunities`, `experiments`, `revenue_records`. Unlike goals/interests/
workflows -> projects in Phase 2 (soft references, added after a test
caught the FK violation), `customers.contact_id`, `communications.
contact_id`, `escalation_events.contact_id`, and `wallet_transactions.
wallet_id` are real foreign keys — `WalletStore.get_or_create_account()`
and `ContactStore.create()` both guarantee the referenced row exists
before anything points at it, so there's no equivalent "record a signal
against a project that was never created" gap here.

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
