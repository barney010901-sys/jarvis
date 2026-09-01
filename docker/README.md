# Docker (local development)

```bash
cp backend/.env.example backend/.env   # edit JARVIS_API_TOKEN at minimum
docker compose -f docker/docker-compose.yml up --build
```

Starts PostgreSQL (schema auto-applied from `/memory/schema.sql` on first
boot) and the backend on `http://localhost:8000`. The backend does not
connect to Postgres yet in Phase 1 — see `docs/PHASE_1.md`.
