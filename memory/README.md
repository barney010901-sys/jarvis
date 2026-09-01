# Memory

Three tiers — see `docs/ARCHITECTURE.md`. `schema.sql` is the target
PostgreSQL schema; `backend/app/memory/store.py` defines the same shape as
Python interfaces (`WorkingMemory`, `ShortTermMemory`, `LongTermMemory`)
with an in-memory implementation for Phase 1.

## Applying the schema (once a Postgres-backed store is implemented)

```bash
createdb jarvis
psql jarvis -f memory/schema.sql
```

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
implementation behind the existing interface.
