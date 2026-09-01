# Phase 1 scope

Goal: a runnable monorepo skeleton that proves the event/permission plumbing
end-to-end, with no real AI reasoning yet.

## In scope

1. Monorepo structure: `/android /backend /agent /memory /tools /prompts /docs /docker`.
2. Backend skeleton (FastAPI) with health check, WebSocket, auth placeholder,
   orchestrator/planner/memory/context/permissions/events/tools modules.
3. Android skeleton (Expo/React Native): home screen, voice button, chat,
   task-progress panel, confirmation dialog, connection status, settings —
   UI shells wired to the backend's WebSocket/REST, no AI logic.
4. Shared architecture/decisions documentation.
5. `.env.example` files for backend and Docker.
6. A working `/ws` endpoint that streams the backend's internal `Event`
   objects to connected clients.
7. `Event` model + in-process `EventBus` covering the full event list from
   the spec.
8. `OrchestratorInterface` + a `StubOrchestrator` that emits the correct
   event sequence for a message without doing any real reasoning.
9. Backend test suite (pytest) covering health, events, permissions,
   orchestrator, and tools.
10. Confirmed backend tests pass and the Android app type-checks.

## Explicitly out of scope (future phases)

- Real Claude reasoning (`agent/provider/claude_provider.py` is a real
  `anthropic` SDK call behind the `AIProvider` interface, but the
  orchestrator does not call it yet — Phase 2).
- Real PostgreSQL/pgvector connection (schema exists, store is in-memory).
- Real GitHub/browser/web-search tool execution.
- Real Claude Code coding-agent execution.
- Real STT/TTS wiring in the Android app (UI affordances exist; the actual
  audio pipeline — recording, uploading, playback — is Phase 2, since it
  depends on the backend having somewhere real to send the audio).
- Real user auth (bearer-token placeholder only).

## Next recommended phase (Phase 2)

Wire STT audio capture in the Android app to a backend endpoint, connect
`ClaudeProvider` into the orchestrator behind a real `PlannerInterface`
implementation, and switch `MemoryStore` to the Postgres-backed
implementation using `/memory/schema.sql`.
