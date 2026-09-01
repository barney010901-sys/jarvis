# Architecture

## Overview

Jarvis is split into independently runnable pieces connected by well-defined
interfaces, so any one of them (the AI provider, the coding agent, a given
tool) can be swapped without touching the others.

```
┌───────────────┐   HTTPS (REST)   ┌───────────────────────────────────────────┐
│               │ ───────────────► │  backend/app                              │
│  Android App  │   WebSocket      │  ┌────────┐  ┌────────────┐  ┌──────────┐  │
│  (Expo/RN)    │ ◄──────────────► │  │  api   │  │ websocket  │  │   auth   │  │
│               │  (task events)   │  └────────┘  └────────────┘  └──────────┘  │
└───────────────┘                  │  ┌────────────────────────────────────┐    │
                                    │  │            orchestrator            │    │
                                    │  └────────────────────────────────────┘    │
                                    │        │        │        │       │        │
                                    │   ┌────▼───┐┌───▼────┐┌──▼───┐┌──▼─────┐  │
                                    │   │planner ││ memory ││context││ tools │  │
                                    │   └────────┘└────────┘└──────┘└───────┘   │
                                    │  ┌────────────────────────────────────┐    │
                                    │  │      events (in-process bus)       │    │
                                    │  └────────────────────────────────────┘    │
                                    └───────────────────┬─────────────────────────┘
                                                         │
                                                ┌────────▼─────────┐
                                                │   agent/          │
                                                │  AIProvider iface │──► Claude API
                                                │  CodingAgent iface│──► Claude Code (future)
                                                └────────────────────┘
```

## Components

### Android app (`/android`)
The Jarvis *interface* only: voice button, chat, live transcription display,
streaming response rendering, task-progress panel, confirmation dialogs,
connection-status indicator, settings. It never calls an AI provider
directly — every request goes to the backend over HTTPS or the WebSocket.

### Backend (`/backend`)
A FastAPI service, organized as loosely-coupled modules under `backend/app`:

- **api** — REST endpoints (health check now; task/chat REST endpoints later).
- **ws** — `ConnectionManager` + the `/ws` endpoint. Streams `Event`s to
  connected clients in real time.
- **auth** — bearer-token dependency (placeholder; swap for real
  OAuth/session auth later without touching other modules).
- **orchestrator** — the single entry point that turns a user message into
  task events. Defines `OrchestratorInterface`; Phase 1 ships a
  `StubOrchestrator` that exercises the full event lifecycle without any
  real reasoning.
- **planner** — `PlannerInterface` turning a request into an ordered list of
  `PlanStep`s. Phase 1 ships a deterministic placeholder planner.
- **memory** — three interfaces (`WorkingMemory`, `ShortTermMemory`,
  `LongTermMemory`) with an in-memory implementation for now. The schema in
  `/memory/schema.sql` is the target PostgreSQL shape (pgvector-ready) that a
  future `PostgresMemoryStore` will implement without changing callers.
- **context** — `ContextEngine` assembling a prompt-ready context string
  from the three memory tiers.
- **permissions** — `PermissionLevel` (`SAFE` / `SENSITIVE`) and the
  `ConfirmationManager` that gates sensitive tool calls behind an explicit
  approve/reject step, surfaced to the Android app as `confirmation.*`
  events.
- **events** — the `Event` model and `EventBus` (in-process async pub/sub
  today; can move to Redis/NATS later behind the same interface).
- **tools** — `Tool` base class + `ToolRegistry`. Phase 1 ships safe
  placeholder tools (filesystem read, project inspection) and stub
  interfaces for GitHub/browser/web-search that raise `NotImplementedError`
  until wired to real integrations.
- **logging_config** — structured logging setup shared by every module.

### Agent (`/agent`)
Everything that talks to a model provider lives here, behind
`AIProvider` (`agent/provider/base.py`). The backend orchestrator depends
only on that interface, never on a specific SDK — so the reasoning
provider can change without touching `backend/`. `agent/coding_agent`
defines the interface a real Claude Code integration will implement; it is
intentionally *not* faked (see `docs/DECISIONS.md`).

### Memory (`/memory`)
`schema.sql` is the source of truth for the PostgreSQL schema: three
tables (`working_memory`, `short_term_memory`, `long_term_memory`), each
with an `embedding` column left ready for `pgvector` (commented out until
the extension is enabled — see decisions doc).

### Tools (`/tools`)
Cross-cutting tool *specifications* (name, description, JSON input schema,
permission level) that both the backend registry and any future MCP
integration should agree on. The executable implementations live in
`backend/app/tools`.

### Prompts (`/prompts`)
Versioned prompt templates the agent layer loads by name, kept out of code
so they can be iterated on without a deploy.

### Docker (`/docker`)
`docker-compose.yml` for local development: PostgreSQL + the backend
service, wired through `.env`.

## Event model

The event bus is the backbone connecting the orchestrator, permissions
system, and the Android client:

```
user.message
voice.transcription.completed
task.created
task.planned
task.started
tool.started
tool.completed
confirmation.required
confirmation.approved
confirmation.rejected
task.failed
task.completed
```

Every event carries `{id, type, timestamp, task_id, correlation_id, payload}`.
The WebSocket layer subscribes a per-connection queue to the bus and
forwards every event as JSON to the client, so the Android app always sees
the same event stream the backend itself uses internally.

## Security model

Every `Tool` declares a `PermissionLevel`:

- **SAFE** — executes immediately (read files, search, run tests, fetch
  information).
- **SENSITIVE** — the orchestrator publishes `confirmation.required` and
  suspends execution until a matching `confirmation.approved` (or
  `confirmation.rejected`) event arrives from the client, via
  `POST /confirmations/{id}/approve|reject`. The Android app is expected to
  render a confirmation dialog whenever it receives `confirmation.required`.

## What Phase 1 deliberately does not do

- No real Claude reasoning — the orchestrator and planner are stubs that
  prove the plumbing (events, memory shape, permission gate) works.
- No real PostgreSQL connection — memory uses an in-memory store behind the
  same interface the Postgres implementation will use.
- No real GitHub/browser/web-search/coding-agent execution — those tools
  and the coding-agent interface exist and are documented, but call out
  clearly that they are not implemented yet.

See `docs/PHASE_1.md` for the full scope and `docs/DECISIONS.md` for the
reasoning behind these choices.
