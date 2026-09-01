"""The seam between the rest of the system and a specific model provider.

Nothing outside `/agent` should import an SDK (`anthropic`, `openai`, ...)
directly — depend on `AIProvider` instead, so the provider can change
without touching the orchestrator, planner, or context engine.

Phase 2 adds `complete()` (non-streaming, used by the planner and by
anything that needs a single parsed result rather than a live token
stream) and `Usage`/`ProviderResult` so callers can track tokens/cost
(see backend/app/cost) without any provider-specific code leaking out of
this package. `stream()` is unchanged from Phase 1.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderResult:
    text: str
    usage: Usage
    model: str
    stop_reason: str | None = None


class AIProvider(ABC):
    #: Set by implementations; used only for logging/cost attribution, so a
    #: router can tell providers apart without isinstance checks.
    name: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a completion as text chunks, given a system prompt and
        conversation history. Implementations should yield chunks as they
        arrive from the provider so the backend can forward them to the
        Android app in real time ("streaming assistant responses").

        Implementations should set `self.last_usage` (a `Usage`) once the
        stream completes, so a caller that just finished iterating can read
        token counts without a second call. This is a pragmatic compromise
        to avoid changing the streaming return type to a tuple — see
        docs/DECISIONS.md.
        """

    @abstractmethod
    async def complete(self, *, system: str, messages: list[Message]) -> ProviderResult:
        """Non-streaming completion. Used where a single parsed result is
        needed up front (e.g. the planner asking for a structured plan)
        rather than a live token stream."""


class ProviderError(Exception):
    """Raised by a provider on any failure (timeout, rate limit, API error).
    Callers (ModelRouter) catch this to decide whether to retry or fall
    back to another provider — provider implementations should not leak
    SDK-specific exception types past this module."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable
