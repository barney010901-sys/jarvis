# Jarvis backend

FastAPI service. See `docs/ARCHITECTURE.md`, `docs/PHASE_2.md`, and
`docs/PHASE_3.md` at the repo root for the full module map and what's real
vs. stubbed.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit JARVIS_API_TOKEN at minimum
```

## Run

The backend imports the top-level `agent` package (the Claude provider
abstraction), which lives outside `backend/` — so the repo root needs to
be on `PYTHONPATH` in addition to `backend/` itself:

```bash
PYTHONPATH=.. uvicorn app.main:app --reload
```

At startup the backend:
- connects to `DATABASE_URL` if `JARVIS_USE_POSTGRES=true` (default) — on
  failure it logs a warning and falls back to Phase 1's in-memory stores
  rather than crashing;
- constructs a real `ClaudeOrchestrator` if Postgres connected **and**
  `JARVIS_USE_CLAUDE=true` **and** `ANTHROPIC_API_KEY` is set — otherwise
  it falls back to the Phase 1 `StubOrchestrator` and logs exactly why.

Check the startup log line (`ClaudeOrchestrator active: ...` or `Falling
back to StubOrchestrator: ...`) to see which stack is actually running.

### Endpoints

- `GET /health` — no auth required.
- `POST /messages` — bearer-token auth (`Authorization: Bearer <JARVIS_API_TOKEN>`). Body: `{"session_id": "...", "project": "...", "text": "..."}`. Returns `{"task_id": "..."}` immediately; progress comes through `/ws`, not this response.
- `POST /confirmations/{id}/approve` / `/reject` — resolves a pending `confirmation.required`.
- `WS /ws?token=<JARVIS_API_TOKEN>` — send `{"type": "user.message", "session_id": "...", "project": "...", "text": "..."}`; receive every `Event` published on the bus as JSON, including `task.delta` chunks when the real Claude response is streaming in.

### Phase 3 endpoints (`backend/app/api/phase3_routes.py`)

All bearer-token auth. Return `503` if their domain isn't configured
(Postgres+Claude unavailable) rather than crashing or faking data.

| Endpoint | Purpose |
|---|---|
| `GET /dashboard` | Command-center summary: health, suggestions, pending approvals, wallet/business snapshot. |
| `GET /system/health` | Full self-diagnostic breakdown. |
| `GET /approvals`, approve/reject via `POST /confirmations/{id}/approve\|reject` | Approval Center — an approval's `id` IS the underlying confirmation id. |
| `GET /audit` | Every event `AuditLogger` recorded (`?task_id=`/`?component=` filters). |
| `GET /memory/search?q=` | Long-term memory + knowledge search. |
| `GET /tasks` | Task lifecycle records. |
| `GET /projects`, `GET /projects/{slug}/goals` | Project/goal center. |
| `GET /wallet`, `POST /wallet/limits`, `POST /wallet/transactions` | Wallet ledger, limits, and (policy-gated) transaction proposals. |
| `GET /business/summary`, `/business/opportunities`, `/business/customers` | Business engine. |
| `GET /capabilities`, `POST /capabilities/search` | Capability discovery (real GitHub search — see docs/DECISIONS.md). |
| `GET /contacts`, `POST /contacts` | Escalation/communication contacts. |
| `POST /escalation/evaluate` | Test the escalation decision for a given urgency/availability. |
| `GET /settings/autonomy`, `POST /settings/autonomy` | Autonomy level (1-5 — see `app/policy/models.py`). |

## Database

```bash
psql "$DATABASE_URL" -f ../memory/schema.sql
psql "$DATABASE_URL" -f ../memory/migrations/0002_phase2.sql
psql "$DATABASE_URL" -f ../memory/migrations/0003_phase3.sql
```

Both are idempotent — safe to re-run. See `memory/README.md`.

## Test

```bash
PYTHONPATH=.. pytest
# or, with a local test Postgres, to also run the REAL DB integration tests:
TEST_DATABASE_URL=postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis_test PYTHONPATH=.. pytest
```

Without `TEST_DATABASE_URL` reachable, every Postgres-dependent test
`pytest.skip()`s with a message saying so — the rest of the suite (event
bus, permissions, tools, evaluation, the stub/Claude orchestrators against
`FakeProvider`, etc.) still runs. See `docs/PHASE_3.md` for the exact
REAL/MOCKED/PARTIALLY_IMPLEMENTED/NOT_TESTED breakdown (132 tests: 121
backend + 11 agent, as of Phase 3).

## What's real vs. stubbed

See `docs/PHASE_1.md`, `docs/PHASE_2.md`, `docs/PHASE_3.md`, and
`docs/DECISIONS.md` at the repo root.
