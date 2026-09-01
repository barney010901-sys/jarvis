# Tools

Cross-cutting tool *specifications* — every tool the backend registry
implements (`backend/app/tools/`) should match one of these. Keeping the
spec here (rather than only in code) means a future MCP integration or the
Android settings screen can describe available tools without importing
Python.

Each tool has:

- **name** — dotted identifier, e.g. `filesystem.read`.
- **description** — one line, human-readable.
- **input_schema** — JSON Schema for its arguments.
- **permission_level** — `safe` (executes immediately) or `sensitive`
  (requires a confirmation round-trip — see `docs/ARCHITECTURE.md`,
  "Security model").
- **execute** — the implementation. Errors must be caught and returned as
  `ToolResult.fail(...)`, never raised past `Tool.run()`.

## Phase 1 tools

| name                  | permission | status                                   |
|-----------------------|------------|-------------------------------------------|
| `filesystem.read`     | safe       | real — reads a file under a sandboxed project root |
| `project.inspect`     | safe       | real — lists files under a sandboxed project root |
| `github.create_issue` | sensitive  | interface only — `NotImplementedError` until connected to the GitHub MCP server or REST API |
| `browser.navigate`    | sensitive  | interface only — `NotImplementedError` until connected to a real browser-automation backend |
| `web.search`          | safe       | interface only — `NotImplementedError` until connected to a real search provider |

See `backend/app/tools/` for the implementations and
`docs/DECISIONS.md` for why the last three are explicit `NotImplementedError`
rather than fake success.

## Adding a tool

1. Implement `Tool` (see `backend/app/tools/base.py`) in
   `backend/app/tools/<name>.py`.
2. Register it in `backend/app/tools/registry.py`'s `default_registry()`.
3. Add a row to the table above.
4. If it's `sensitive`, no extra wiring is needed — `StubOrchestrator`
   already routes any `sensitive` tool through `ConfirmationManager`.
