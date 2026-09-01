# Jarvis

A modular personal AI assistant, controlled primarily from an Android phone.

```
Android App
   ↓ HTTPS / WebSocket
Jarvis Backend (FastAPI)
   ↓
Orchestrator
   ↓
Claude (via provider abstraction in /agent)
   ↓
Planner / Memory / Context / Tools
   ↓
MCP integrations and external services
```

## Monorepo layout

| Path        | Purpose                                                                 |
|-------------|--------------------------------------------------------------------------|
| `/android`  | React Native (Expo) client — the Jarvis interface. No AI logic here.    |
| `/backend`  | FastAPI service: API, WebSocket, auth, orchestrator, planner, memory, context, permissions, events, tools, logging. |
| `/agent`    | AI-provider abstraction (Claude first) and the coding-agent (Claude Code) delegation interface. |
| `/memory`   | Database schema (PostgreSQL) for memory, knowledge, profile/project/goal/interest/workflow, suggestions, tasks, audit, and cost tracking. |
| `/tools`    | Tool specifications shared across the system (schemas, permission levels, docs). |
| `/prompts`  | Prompt templates loaded by `ClaudeOrchestrator`. |
| `/docker`   | Local development compose files. |
| `/docs`     | Architecture, decisions, and phase plans. |

## Status

**Phase 2** (current): real Claude integration via a model router
(fast/primary/fallback), PostgreSQL-backed memory/knowledge/profile,
an extended context engine, token/cost tracking, knowledge deduplication
and learning from successful tasks, user corrections, interest/goal/
workflow tracking, non-intrusive proactive learning, an explicit task
lifecycle, deterministic evaluation, and an audit trail — all built as an
evolution of Phase 1 (the stub orchestrator/planner and in-memory stores
still exist as the automatic fallback when Postgres/Claude aren't
configured). See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/PHASE_1.md`](docs/PHASE_1.md), and
[`docs/PHASE_2.md`](docs/PHASE_2.md) (files changed/created, migrations,
env vars, exact commands, and a REAL/MOCKED/NOT TESTED breakdown).

## Quick start

See [`backend/README.md`](backend/README.md) for the backend and
[`android/README.md`](android/README.md) for the app.
