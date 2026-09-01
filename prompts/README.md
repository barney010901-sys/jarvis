# Prompts

Prompt templates, loaded from disk (not inline Python strings) so they can
be iterated on without a backend deploy — `backend/app/prompts_loader.py`
reads them by name.

| file                  | used by                                                              |
|-----------------------|------------------------------------------------------------------------|
| `system_prompt.md`    | `ClaudeOrchestrator` — its `{context}` placeholder is filled with the `ContextEngine`-built `ContextBundle` text for the current request. |
| `planner_prompt.md`   | Not yet loaded by code — `ClaudePlanner` (`backend/app/planner/claude_planner.py`) currently builds its planning prompt inline. Kept here as the intended shape for when that's factored out; do so if the inline version grows past a few lines. |

`StubOrchestrator`/`StubPlanner` (the Phase 1 fallback path — still active
when Postgres/Claude aren't configured) never load these; only
`ClaudeOrchestrator` does.
