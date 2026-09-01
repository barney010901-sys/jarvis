# Agent

Everything that talks to a model provider or a coding agent lives here,
behind interfaces the backend orchestrator depends on instead of a
specific SDK. See `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` at the
repo root for the reasoning.

## `provider/` — the reasoning model

- `base.py` — `AIProvider`: `stream()` (chunked, for live responses —
  yields text as it arrives so the backend can forward it to the Android
  app as `task.delta` events) and `complete()` (single `ProviderResult`,
  for the planner). `ProviderError` is what implementations raise on any
  failure; `retryable` tells a caller whether retrying makes sense.
- `claude_provider.py` — a real implementation using the `anthropic` SDK,
  with retry/backoff on transient errors (timeouts, rate limits, 5xx) and
  a configurable timeout/max-tokens/max-retries. Used by
  `ClaudeOrchestrator` (Phase 2) via `ModelRouter`, never constructed
  directly outside this package.
- `router.py` — `ModelRouter`: the abstraction the rest of the system
  talks to instead of a single model. Three roles — `fast` (planner),
  `primary` (main reasoning), `fallback` (used if primary fails) — each
  backed by an `AIProvider`. `build_claude_router()` constructs all three
  as `ClaudeProvider`s at different model tiers, but nothing outside this
  file assumes that — a future provider (a different vendor, a local
  model) just needs to implement `AIProvider` and get registered under a
  role.
- `costs.py` — `estimate_cost(model, input_tokens, output_tokens)`: an
  approximate, illustrative per-token pricing table for cost tracking
  (`backend/app/cost`) — not a live pricing source.
- `fake_provider.py` — `FakeProvider`: a deterministic `AIProvider` used
  throughout the backend test suite so orchestrator/planner behavior can
  be verified without a network call or API key. Clearly named `Fake*`,
  not disguised as real.

To use `ClaudeProvider` standalone once `ANTHROPIC_API_KEY` is set:

```python
from agent.provider.claude_provider import ClaudeProvider
from agent.provider.base import Message

provider = ClaudeProvider()
async for chunk in provider.stream(system="You are Jarvis.", messages=[Message(role="user", content="hi")]):
    print(chunk, end="")
print(provider.last_usage)  # Usage(input_tokens=..., output_tokens=...)
```

Or via the router (what the backend actually does):

```python
from agent.provider.router import build_claude_router, PRIMARY

router = build_claude_router(
    api_key="sk-...", primary_model="claude-sonnet-5",
    fast_model="claude-haiku-4-5-20251001", fallback_model="claude-opus-5",
)
result = await router.complete(PRIMARY, system="...", messages=[...])
```

## `coding_agent/` — delegating coding tasks

`interface.py` defines `CodingAgentInterface`, the contract a real Claude
Code integration must implement. **No implementation is provided here on
purpose** — the task spec is explicit that this must not be faked (Phase 2
did not change this). See the docstring on `CodingAgentInterface.run_task`
for exactly how the real integration should be wired (subprocess
invocation, working directory, streaming output back through the
backend's event bus).
