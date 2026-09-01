"""ModelRouter — the abstraction JARVIS talks to instead of a single model.

Nothing outside `/agent` should construct a provider directly; go through
a `ModelRouter` role instead ("fast", "primary", "fallback") so a new
provider (a different vendor, a local model) can be added later by
registering it under a role, without the orchestrator/planner changing.
See docs/DECISIONS.md ("Model routing").
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from agent.provider.base import AIProvider, Message, ProviderError, ProviderResult

logger = logging.getLogger(__name__)

FAST = "fast"
PRIMARY = "primary"
FALLBACK = "fallback"


class ModelRouter:
    def __init__(self, providers: dict[str, AIProvider]) -> None:
        if PRIMARY not in providers:
            raise ValueError("ModelRouter requires at least a 'primary' provider")
        self._providers = providers
        # Updated by complete()/stream() to whichever provider actually
        # served the last request (which may be the 'fallback' role's
        # provider, not the one requested) — callers that need
        # token/usage for cost tracking should read this right after the
        # call rather than re-resolving the originally-requested role.
        self.last_used_role: str | None = None
        self.last_used_provider: AIProvider | None = None

    def get(self, role: str) -> AIProvider:
        provider = self._providers.get(role)
        if provider is None:
            raise KeyError(f"no provider registered for role '{role}'")
        return provider

    def has(self, role: str) -> bool:
        return role in self._providers

    async def complete(self, role: str, *, system: str, messages: list[Message]) -> ProviderResult:
        """Complete using `role`'s provider; fall back to the 'fallback'
        role (if registered and different from `role`) on ProviderError."""
        provider = self.get(role)
        try:
            result = await provider.complete(system=system, messages=messages)
            self.last_used_role, self.last_used_provider = role, provider
            return result
        except ProviderError as exc:
            if role != FALLBACK and self.has(FALLBACK):
                logger.warning("complete() on role '%s' failed (%s); falling back to '%s'", role, exc, FALLBACK)
                fallback = self._providers[FALLBACK]
                result = await fallback.complete(system=system, messages=messages)
                self.last_used_role, self.last_used_provider = FALLBACK, fallback
                return result
            raise

    async def stream(self, role: str, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        provider = self.get(role)
        started = False
        try:
            async for chunk in provider.stream(system=system, messages=messages):
                started = True
                yield chunk
            self.last_used_role, self.last_used_provider = role, provider
        except ProviderError as exc:
            # Once output has started reaching the caller (and likely the
            # user, as task.delta events), switching providers mid-stream
            # would duplicate/garble content — only a failure before the
            # first chunk is safe to retry against the fallback.
            if started or role == FALLBACK or not self.has(FALLBACK):
                raise
            logger.warning("stream() on role '%s' failed before first chunk (%s); falling back to '%s'", role, exc, FALLBACK)
            fallback = self._providers[FALLBACK]
            async for chunk in fallback.stream(system=system, messages=messages):
                yield chunk
            self.last_used_role, self.last_used_provider = FALLBACK, fallback


def build_claude_router(
    *,
    api_key: str,
    primary_model: str,
    fast_model: str,
    fallback_model: str,
    max_tokens: int = 4096,
    timeout: float = 30.0,
    max_retries: int = 2,
) -> ModelRouter:
    """Convenience factory: all three roles backed by Claude at different
    model tiers. Kept out of `backend/` so the backend never imports the
    `anthropic` SDK directly (docs/ARCHITECTURE.md, "Agent")."""
    from agent.provider.claude_provider import ClaudeProvider

    providers = {
        FAST: ClaudeProvider(api_key=api_key, model=fast_model, max_tokens=max_tokens, timeout=timeout, max_retries=max_retries, role=FAST),
        PRIMARY: ClaudeProvider(api_key=api_key, model=primary_model, max_tokens=max_tokens, timeout=timeout, max_retries=max_retries, role=PRIMARY),
        FALLBACK: ClaudeProvider(api_key=api_key, model=fallback_model, max_tokens=max_tokens, timeout=timeout, max_retries=max_retries, role=FALLBACK),
    }
    return ModelRouter(providers)
