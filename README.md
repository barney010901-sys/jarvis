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
| `/memory`   | Database schema for working / short-term / long-term memory (PostgreSQL, pgvector-ready). |
| `/tools`    | Tool specifications shared across the system (schemas, permission levels, docs). |
| `/prompts`  | Prompt templates used by the agent layer. |
| `/docker`   | Local development compose files. |
| `/docs`     | Architecture, decisions, and phase plans. |

## Status

**Phase 1** (current): monorepo scaffold, backend skeleton with health check, WebSocket
event streaming, permission/confirmation model, and a stub orchestrator — no real Claude
reasoning wired in yet. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/PHASE_1.md`](docs/PHASE_1.md).

## Quick start

See [`backend/README.md`](backend/README.md) for the backend and
[`android/README.md`](android/README.md) for the app.
