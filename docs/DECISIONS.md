# Decisions

Short, dated records of choices made where the spec left room for more than
one reasonable approach. Newest first.

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
