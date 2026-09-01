# Jarvis backend

FastAPI service. See `docs/ARCHITECTURE.md` at the repo root for the full
module map.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit JARVIS_API_TOKEN at minimum
```

## Run

```bash
uvicorn app.main:app --reload
```

- `GET /health` — no auth required.
- `POST /messages` — bearer-token auth (`Authorization: Bearer <JARVIS_API_TOKEN>`). Body: `{"session_id": "...", "project": "...", "text": "..."}`. Returns `{"task_id": "..."}` immediately; progress comes through `/ws`, not this response.
- `POST /confirmations/{id}/approve` / `/reject` — resolves a pending `confirmation.required`.
- `WS /ws?token=<JARVIS_API_TOKEN>` — send `{"type": "user.message", "session_id": "...", "project": "...", "text": "..."}`; receive every `Event` published on the bus as JSON.

## Test

```bash
pytest
```

19 tests covering the event bus, permission/confirmation flow, tool
registry + placeholder tools, and the stub orchestrator's end-to-end event
sequence.

## What's real vs. stubbed in Phase 1

See `docs/PHASE_1.md` and `docs/DECISIONS.md` at the repo root.
