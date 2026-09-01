# Agent

Everything that talks to a model provider or a coding agent lives here,
behind interfaces the backend orchestrator depends on instead of a
specific SDK. See `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` at the
repo root for the reasoning.

## `provider/` — the reasoning model

- `base.py` — `AIProvider`, the interface the orchestrator/planner will
  call once Phase 2 wires real reasoning in. `stream()` yields response
  text chunks so the backend can forward them to the Android app as they
  arrive (streaming assistant responses).
- `claude_provider.py` — a real implementation using the `anthropic` SDK's
  streaming Messages API. It is **not yet called by the orchestrator** —
  `StubOrchestrator` (Phase 1) does not reason at all. Wiring it in is a
  Phase 2 change to `backend/app/orchestrator`, not to this module.

To use it standalone once `ANTHROPIC_API_KEY` is set:

```python
from agent.provider.claude_provider import ClaudeProvider
from agent.provider.base import Message

provider = ClaudeProvider()
async for chunk in provider.stream(system="You are Jarvis.", messages=[Message(role="user", content="hi")]):
    print(chunk, end="")
```

## `coding_agent/` — delegating coding tasks

`interface.py` defines `CodingAgentInterface`, the contract a real Claude
Code integration must implement. **No implementation is provided here on
purpose** — the task spec is explicit that this must not be faked. See the
docstring on `CodingAgentInterface.run_task` for exactly how the real
integration should be wired (subprocess invocation, working directory,
streaming output back through the backend's event bus).
