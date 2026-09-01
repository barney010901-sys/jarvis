# Prompts

Prompt templates the `/agent` layer will load by name once Phase 2 wires
`ClaudeProvider` into the orchestrator/planner. Kept as plain files (not
inline Python strings) so they can be iterated on without a backend
deploy.

Nothing in Phase 1 loads these yet — `StubOrchestrator` and `StubPlanner`
don't call the AI provider at all (see `docs/PHASE_1.md`). They exist now
so the prompt *shape* is decided alongside the interfaces that will use it.

| file                  | used by (future)                      |
|-----------------------|-----------------------------------------|
| `system_prompt.md`    | the main Jarvis system prompt (identity, tone, safety rules) |
| `planner_prompt.md`   | turns a user request + context into a structured plan |
