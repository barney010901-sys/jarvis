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
  task events. Defines `OrchestratorInterface`, implemented by two classes
  side by side: `StubOrchestrator` (Phase 1, zero external dependencies,
  no reasoning) and `ClaudeOrchestrator` (Phase 2, the real
  context→memory→planner→Claude→tools→evaluation→learning flow — see
  "Phase 2 additions" below). They share tool-execution logic via
  `plan_execution.execute_plan()`. `deps.py` picks whichever the
  environment supports and logs which one is active.
- **planner** — `PlannerInterface` turning a request into an ordered list of
  `PlanStep`s. `StubPlanner` (Phase 1) is deterministic; `ClaudePlanner`
  (Phase 2) asks the "fast" model role for a JSON plan and falls back to
  `StubPlanner` on any failure.
- **memory** — three interfaces (`WorkingMemory`, `ShortTermMemory`,
  `LongTermMemory`). `backend/app/memory/store.py` has the Phase 1
  in-memory implementation; `backend/app/memory/postgres_store.py` (Phase
  2) implements the same interfaces against `/memory/schema.sql` — same
  call sites, different backing store.
- **context** — `ContextEngine` assembling a prompt-ready `ContextBundle`
  from memory, knowledge, and profile (Phase 2 — see "Phase 2 additions").
- **permissions** — `PermissionLevel` (`SAFE` / `SENSITIVE`) and the
  `ConfirmationManager` that gates sensitive tool calls behind an explicit
  approve/reject step, surfaced to the Android app as `confirmation.*`
  events.
- **events** — the `Event` model and `EventBus` (in-process async pub/sub
  today; can move to Redis/NATS later behind the same interface).
- **tools** — `Tool` base class + `ToolRegistry`. Real, working SAFE tools
  (filesystem read, project inspection) and SENSITIVE placeholder
  interfaces for GitHub/browser/web-search that raise `NotImplementedError`
  until wired to real integrations.
- **logging_config** — structured logging setup shared by every module.

### Agent (`/agent`)
Everything that talks to a model provider lives here, behind
`AIProvider` (`agent/provider/base.py`) — `stream()` (chunked, for live
responses) and `complete()` (single result, for the planner). The backend
depends only on that interface and on `ModelRouter`
(`agent/provider/router.py`), never on the `anthropic` SDK directly, via
three roles — `fast`/`primary`/`fallback` — each backed by a
`ClaudeProvider` at a different model tier (Phase 2), with automatic
retry/timeout handling and a same-provider-family fallback on failure.
`FakeProvider` is a deterministic test double used throughout the backend
test suite so orchestrator behavior can be verified without a network
call or API key. `agent/coding_agent` defines the interface a real Claude
Code integration will implement; it is intentionally *not* faked (see
`docs/DECISIONS.md`).

### Memory (`/memory`)
`schema.sql` is the Phase 1 PostgreSQL schema (three tables:
`working_memory`, `short_term_memory`, `long_term_memory`).
`migrations/0002_phase2.sql` (Phase 2, additive) adds `knowledge`,
`profile_facts`, `preferences`, `projects`, `goals`, `interests`,
`workflows`, `suggestions`, `tasks`, `audit_log`, `token_usage`, and
`knowledge_relationships`. See `memory/README.md` for how to apply both,
in order.

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

## Phase 2 additions (`backend/app/*`)

New backend modules, all Postgres-backed (see docs/DECISIONS.md, "Phase 2
intelligence features require Postgres"):

- **knowledge** — `KnowledgeRecord`s across 11 categories (`USER_PREFERENCES`
  through `FUTURE_RELEVANT_KNOWLEDGE`), each with confidence/status/usage
  tracking. `KnowledgeService` dedupes via trigram+`difflib` similarity
  before creating a new record (merging into an existing one instead when
  they're similar enough), applies user corrections (lowering confidence
  on superseded facts, storing the correction with high confidence), and
  answers "do we already know this with enough confidence?" for the
  cost-hierarchy short-circuit.
- **profile** — `ProfileStore`: facts, preferences, projects, goals,
  interests, and workflows as separate tables/dataclasses (never merged
  into one). `InterestEngine` tracks recurring topics with recency decay
  and fires `interest.detected` the first time a topic crosses a
  repetition threshold. `WorkflowDetector` recognizes a repeated ordered
  tool-call sequence as a reusable workflow after enough evidence.
- **suggestions** — a priority-ranked (`LOW`/`MEDIUM`/`HIGH`) queue;
  `SuggestionService` enqueues and publishes `suggestion.created`.
- **proactive** — `ProactiveLearningEngine`: a manually-invoked, local-only
  (no Claude calls) cycle that turns strong interest signals into
  `FUTURE_RELEVANT_KNOWLEDGE` + a suggestion. Off by default
  (`feature_proactive_learning`).
- **cost** — `CostTracker`: records token usage/estimated cost per
  provider call, answers "are we near/over the daily budget", and counts
  cache/knowledge hits and avoided provider calls.
- **tasks** — persisted task lifecycle (`CREATED` → ... → `COMPLETED`/
  `FAILED`/`CANCELLED`/`TIMEOUT`), so the system (and a future admin view)
  always knows what it's currently doing, across restarts.
- **evaluation** — `EvaluationEngine`: deterministic checks (tool success,
  non-empty response, expected files actually exist) producing
  `SUCCESS`/`PARTIAL`/`FAILED`/`NEEDS_REVIEW` — no second Claude call to
  grade the first.
- **audit** — `AuditLogger`: a wildcard `EventBus` subscriber that writes
  every published event to `audit_log`. Not a second event system — it
  only *listens*.
- **learning** — `LearningPipeline` ties the above together: correction
  detection on every user message, interest signals against known
  project technologies, workflow observation and knowledge extraction
  after every completed task (only on a `SUCCESS` evaluation).

`ClaudeOrchestrator` (`backend/app/orchestrator/claude_orchestrator.py`)
is what actually sequences all of this — see its module docstring for the
exact flow, which matches the task spec's
"context → memory → planner → Claude → tools → evaluation → learning"
pipeline.

## Phase 3 additions (`backend/app/*`, Android)

The **centralized Policy Engine** (`backend/app/policy`) is the one new
architectural piece everything else in Phase 3 depends on:
`PolicyEngine.evaluate(PolicyRequest) -> ALLOW/DENY/ASK`, reusing the
existing `ConfirmationManager` for the ASK gate (no second confirmation
mechanism) and a durable `approvals` table for the Approval Center. Five
autonomy levels (`AutonomyLevel`, stored via the existing `preferences`
table) control how much auto-approves before asking.

New domain services, each gated behind Postgres+Claude being configured
(see docs/DECISIONS.md, "Phase 3 domains share Phase 2's one-fallback-axis
rule") and each exposed to Claude as a `Tool`
(`backend/app/tools/phase3_tools.py`) rather than a new orchestrator path:

- **wallet** — a real, deterministic internal ledger (`wallet_accounts`/
  `wallet_transactions`) with weekly/monthly/per-transaction limits and a
  GREEN/YELLOW/RED classification feeding the Policy Engine. No real
  payment rail — see docs/DECISIONS.md.
- **communication** + **escalation** — contact management, heuristic
  message classification, and policy-gated replies/escalation, all real;
  actual transmission is an explicit `NotImplementedError` adapter — see
  docs/DECISIONS.md.
- **business** — ideas, customer pipeline, risk-adjusted opportunity
  ranking (`backend/app/business/scoring.py`), revenue, and a
  sustainability-stage summary.
- **capabilities** — real (unauthenticated) GitHub repository search for
  capability-gap research, persisted as candidates with an explicit
  `verification_status`; never installs anything.
- **health** — live self-diagnostics (`HealthService`) across Postgres,
  Claude configuration, the event bus, the tool registry, and GitHub
  reachability; static, honest `NOT_CONFIGURED`/`NOT_TESTED` status for
  everything not built yet (MCP, browser automation, the coding agent,
  STT, a physical Android device).

`PlanStep` gained an optional `tool_args` field so the planner can pass
parameters (a wallet amount, a draft reply) to these tools — see
docs/DECISIONS.md.

### Android (Phase 3)

- **`JarvisCore`** (`src/components/JarvisCore.tsx`) replaces the Phase 1
  `VoiceButton` (removed) with nine distinguishable states (IDLE,
  LISTENING, THINKING, PROCESSING, USING_TOOL, WAITING_FOR_CONFIRMATION,
  SPEAKING, ERROR, OFFLINE), derived from the existing event stream by
  `useJarvisState` — no new state system.
- **Text-to-speech** (`src/tts/speech.ts`, `expo-speech`) speaks completed
  assistant replies — real, not verified on a physical device (no
  emulator/device in this sandbox).
- **Command-center Home screen**: current project/task activity,
  pending approvals, suggestions, wallet/business/system-health summaries
  — one dashboard, not a chatbot with a few buttons (section 64).
- **New screens**: Approvals, Audit, Memory (search), Projects (with
  inline goals), Tasks, Wallet, Business — each a thin view over the new
  REST endpoints (`backend/app/api/phase3_routes.py`), reusing the same
  `Card`/`StatusPill`/`EmptyState` primitives so they read as one system.
- **Settings** gained sectioned cards (Voice, Privacy/24-7, Autonomy,
  Escalation contacts, System) rather than one screen per category —
  deliberately consolidated (section 91: "avoid dozens of disconnected
  screens").
- Wake word, VAD, real STT, and real Android system integrations
  (contacts/SMS/calls/calendar) are **not implemented** — see "What's
  still deliberately not implemented" below and docs/PHASE_3.md.

## Phase 4 additions (foundation increment 4B-4E; `backend/app/*`)

Phase 4 is the "autonomous self-evolving business operating system"
expansion — an enormous spec (30 named subsystems). This increment builds
only the foundation layer (4B-4E from the recommended order in
docs/PHASE_4_AUDIT.md), additively, with no Phase 1-3 behavior changed
beyond one widened CHECK constraint (see docs/DECISIONS.md):

- **selfcode** — `SelfModificationProposal`/`SelfCodeService`: the one
  path by which a change to Jarvis's own code can be proposed. Always
  routes through `PolicyEngine` with `kind="self_modification"`, which is
  hard-coded to never auto-approve at any autonomy level (confirmed by
  the user 2026-09-02 — see docs/PHASE_4_AUDIT.md §17b). `apply()`/
  `rollback()` raise `NotImplementedError`: no sandbox/snapshot tooling
  exists yet to safely execute an approved change against the running
  system.
- **capabilities (extended)** — the Phase 3 discovery table now also
  backs a Capability Registry: `register_internal()`/`compose()`/
  `search()`/`record_usage()` alongside the existing GitHub-search
  methods. `CapabilityUsageTracker` is a new `EventBus` wildcard
  subscriber (same pattern as `AuditLogger`) that updates usage/success
  counts from `TOOL_COMPLETED` events — no change to
  `plan_execution.py`.
- **autonomy** — `AutonomyMode` (a *different* concept from Phase 3's
  per-action `AutonomyLevel`; see docs/DECISIONS.md), describing the
  posture of the continuous autonomous loop as a whole. Default
  `AUTONOMOUS`, not `HUMAN_GATED`. `ResourceBudgetService` is an opt-in
  money/API-call/action/time budget tracker, separate from the wallet's
  own hard financial limits.

New REST surface: `backend/app/api/phase4_routes.py` —
`/selfcode/proposals`, `/capability-registry/{search,register,compose}`,
`/autonomy/mode`, `/autonomy/budgets`.

Everything else in the Phase 4 spec (Agent Runtime, Workflow Engine,
Research Engine, Learning/Prediction/Decision Engines, Economic Engine,
Business OS breadth, self-healing/self-testing/self-update execution,
Command Center, and 20+ more subsystems) is **not built yet** — see
docs/PHASE_4_AUDIT.md for the full dependency list and recommended order.

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

# Phase 2 additions:
context.updated
task.evaluating
knowledge.created
knowledge.updated
interest.detected
suggestion.created
task.delta          # not in the original task spec's list — one per
                     # streamed response chunk; see docs/DECISIONS.md
                     # ("The event vocabulary gained task.delta")

# Phase 3 additions:
capability.discovered
tool.registered      # not yet published by any code path — reserved for
                     # when a discovered capability is actually installed
communication.received
communication.sent
escalation.triggered
wallet.transaction.created
wallet.limit.warning
wallet.limit.blocked
system.health.warning
```

Every event carries `{id, type, timestamp, task_id, correlation_id, payload}`.
The WebSocket layer subscribes a per-connection queue to the bus and
forwards every event as JSON to the client, so the Android app always sees
the same event stream the backend itself uses internally. `AuditLogger`
(Phase 2) subscribes the same way to persist every event to `audit_log`.

## Security model

Every `Tool` declares a `PermissionLevel`:

- **SAFE** — executes immediately (read files, search, run tests, fetch
  information).
- **SENSITIVE** — the orchestrator publishes `confirmation.required` and
  suspends execution until a matching `confirmation.approved` (or
  `confirmation.rejected`) event arrives from the client, via
  `POST /confirmations/{id}/approve|reject`. The Android app is expected to
  render a confirmation dialog whenever it receives `confirmation.required`.

Phase 3 layers the **Policy Engine** on top for wallet/communication/
capability/destructive actions specifically: `MODEL -> POLICY -> ASK
(reusing the confirmation gate above) -> EXECUTION -> AUDIT`. The model
never has unrestricted authority over money, external communication, or
escalation — every one of those goes through `PolicyEngine.evaluate()`
first (see docs/ARCHITECTURE.md's "Phase 3 additions" and
docs/DECISIONS.md).

## What's still deliberately not implemented

- No real GitHub/browser/web-search/coding-agent execution — those tools
  and the coding-agent interface exist and are documented, but call out
  clearly that they are not implemented yet (2Z: "only create clean
  interfaces where needed for future phases").
- No real STT, calendar, or email integration. TTS is real (Phase 3,
  `expo-speech`); STT is not.
- No wake word or voice-activity-detection engine — both need a native
  module and a custom dev client, neither of which this build has.
- No real Android system integrations (contacts/SMS/calls/calendar) —
  `CommunicationChannelAdapter` is the documented seam for wiring these in
  later; nothing calls a real Android API today.
- No real payment rail behind the operational wallet — see
  docs/DECISIONS.md ("The wallet is a real ledger, not a real payment
  rail").
- No background scheduler for proactive learning — it's a callable engine,
  invoked manually, off by default.
- No true semantic/vector search — knowledge/memory retrieval uses
  trigram+substring text similarity; pgvector remains the documented
  upgrade path once an embedding source is chosen.
- No MCP registry integration — `system.health`'s `mcp` component reports
  `NOT_CONFIGURED` honestly rather than pretending.

See `docs/PHASE_1.md` and `docs/PHASE_2.md` for the scope of each phase,
and `docs/DECISIONS.md` for the reasoning behind these choices.
