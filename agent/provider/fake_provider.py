"""A deterministic AIProvider test double — no network, no API key.

Used by backend tests that exercise ClaudeOrchestrator/ClaudePlanner
end-to-end without calling the real Anthropic API. Clearly a MOCKED
component — see docs/PHASE_2.md's REAL/MOCKED/NOT TESTED breakdown.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from agent.provider.base import AIProvider, Message, ProviderError, ProviderResult, Usage


class FakeProvider(AIProvider):
    def __init__(
        self,
        *,
        response_text: str = "This is a fake response.",
        plan_json: str | None = None,
        model: str = "fake-model",
        role: str = "primary",
        fail_times: int = 0,
    ) -> None:
        self.name = "fake"
        self.model = model
        self.role = role
        self.last_usage = Usage()
        self._response_text = response_text
        # If set, complete() returns this instead of response_text — used
        # by ClaudePlanner tests to hand back a canned structured plan.
        self._plan_json = plan_json
        self._fail_times = fail_times
        self._calls = 0
        self.calls: list[list[Message]] = []

    async def complete(self, *, system: str, messages: list[Message]) -> ProviderResult:
        self._calls += 1
        self.calls.append(messages)
        if self._calls <= self._fail_times:
            raise ProviderError("fake transient failure", retryable=True)
        text = self._plan_json if self._plan_json is not None else self._response_text
        usage = Usage(input_tokens=len(system) // 4, output_tokens=len(text) // 4)
        self.last_usage = usage
        return ProviderResult(text=text, usage=usage, model=self.model, stop_reason="end_turn")

    async def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        self._calls += 1
        self.calls.append(messages)
        if self._calls <= self._fail_times:
            raise ProviderError("fake transient failure", retryable=True)
        for word in self._response_text.split(" "):
            yield word + " "
        self.last_usage = Usage(input_tokens=len(system) // 4, output_tokens=len(self._response_text) // 4)
