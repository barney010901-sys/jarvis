"""The seam between the rest of the system and a specific model provider.

Nothing outside `/agent` should import an SDK (`anthropic`, `openai`, ...)
directly — depend on `AIProvider` instead, so the provider can change
without touching the orchestrator, planner, or context engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


class AIProvider(ABC):
    @abstractmethod
    def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a completion as text chunks, given a system prompt and
        conversation history. Implementations should yield chunks as they
        arrive from the provider so the backend can forward them to the
        Android app in real time ("streaming assistant responses")."""
