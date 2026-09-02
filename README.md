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
| `/memory`   | Database schema (PostgreSQL) for memory, knowledge, profile/project/goal/interest/workflow, suggestions, tasks, audit, cost tracking, policy/approvals, wallet, communication/escalation, and the business engine. |
| `/tools`    | Tool specifications shared across the system (schemas, permission levels, docs). |
| `/prompts`  | Prompt templates loaded by `ClaudeOrchestrator`. |
| `/docker`   | Local development compose files. |
| `/docs`     | Architecture, decisions, and phase plans. |

## Status

**Phase 3 — final V1** (current): a centralized Policy Engine gating every
external/sensitive action (wallet spend, outgoing communication,
escalation, capability install); a real, limit-enforced operational
wallet (internal ledger only — no real payment rail); communication and
escalation with real classification/policy/audit but no real message
transmission yet; a business engine (opportunities, customer pipeline,
sustainability tracking); real GitHub capability discovery; live system
self-diagnostics; and a substantially redesigned Android app — a
`JarvisCore` visual identity with nine states, on-device TTS, and a
command-center dashboard plus Approval/Audit/Memory/Projects/Tasks/
Wallet/Business screens. All built as an evolution of Phase 1 + Phase 2
(the stub orchestrator/planner, in-memory stores, and the original event
bus/tool registry are unchanged and remain the automatic fallback when
Postgres/Claude aren't configured). See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/PHASE_1.md`](docs/PHASE_1.md), [`docs/PHASE_2.md`](docs/PHASE_2.md),
and [`docs/PHASE_3.md`](docs/PHASE_3.md) (files changed/created,
migrations, env vars, exact commands, and a REAL/MOCKED/
PARTIALLY_IMPLEMENTED/NOT_TESTED breakdown).

## Quick start

See [`backend/README.md`](backend/README.md) for the backend and
[`android/README.md`](android/README.md) for the app.
