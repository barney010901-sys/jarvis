"""Real Claude implementation of AIProvider, using the `anthropic` SDK's
streaming Messages API.

Not called by the orchestrator yet in Phase 1 (see `agent/README.md`). Kept
here, real and working, so wiring it into the planner/orchestrator in
Phase 2 is a matter of constructing this class and calling `.stream()` —
no SDK-specific code needs to be written at that point.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from agent.provider.base import AIProvider, Message

DEFAULT_MODEL = "claude-sonnet-5"


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env (see .env.example) "
                "before constructing ClaudeProvider."
            )
        self._client = AsyncAnthropic(api_key=key)
        self._model = model

    async def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        ) as stream:
            async for text in stream.text_stream:
                yield text
