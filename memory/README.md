# Memory

Three tiers — see `docs/ARCHITECTURE.md`. `schema.sql` is the Phase 1
PostgreSQL schema; `backend/app/memory/store.py` defines the same shape as
Python interfaces (`WorkingMemory`, `ShortTermMemory`, `LongTermMemory`),
with both an in-memory implementation (`store.py`, used as a fallback and
in unit tests) and a Postgres-backed one (`postgres_store.py`, Phase 2's
default when `DATABASE_URL` is reachable).

`migrations/0002_phase2.sql` adds everything else Phase 2 needs:
`knowledge`, `profile_facts`, `preferences`, `projects`, `goals`,
`interests`, `workflows`, `suggestions`, `tasks`, `audit_log`,
`token_usage`, `knowledge_relationships`. See
`backend/app/knowledge/`, `backend/app/profile/`,
`backend/app/suggestions/`, `backend/app/tasks/`, `backend/app/audit/`,
and `backend/app/cost/` for the Python side of each.

## Applying the schema

Apply both files, in order — every statement is idempotent
(`IF NOT EXISTS` / `ON CONFLICT`), so re-running either is safe:

```bash
createdb jarvis
psql jarvis -f memory/schema.sql
psql jarvis -f memory/migrations/0002_phase2.sql
```

`docker/docker-compose.yml` mounts both into Postgres's
`docker-entrypoint-initdb.d` (numbered so they apply in order) — but only
on a brand-new volume; see that file's comments for applying the migration
by hand against an existing one.

### Adding a migration later

Add a new numbered file under `memory/migrations/` (`0003_...sql`) rather
than editing `schema.sql` or `0002_phase2.sql` in place — see
docs/DECISIONS.md for why Phase 2 did this instead of a destructive
schema replacement. Document every migration's purpose in a comment at
the top of the file, the way `0002_phase2.sql` does.

## pgvector

`long_term_memory.embedding` is present in the schema, commented out,
along with the `CREATE EXTENSION` statement. To enable vector search:

1. Ensure the Postgres instance has the `pgvector` extension available.
2. Uncomment the `CREATE EXTENSION IF NOT EXISTS vector;` line and the
   `embedding vector(1536)` column (1536 matches common embedding-model
   output sizes; adjust to whatever embedding model is chosen).
3. Add an index, e.g. `CREATE INDEX ON long_term_memory USING ivfflat (embedding vector_cosine_ops);`
4. Implement `LongTermMemory.search` (currently naive substring matching)
   as a cosine-distance ORDER BY against `embedding`.

No application code needs to change shape — only the `search()`
implementation behind the existing interface. The same applies to
`knowledge.search()`, which uses `pg_trgm` similarity in Phase 2 (see
docs/DECISIONS.md, "Knowledge search uses trigram similarity") — an
`embedding` column there would follow the same pattern.
