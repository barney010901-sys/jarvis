"""Real Claude implementation of AIProvider, using the `anthropic` SDK.

Used by `ClaudeOrchestrator` (Phase 2) via `ModelRouter`
(`agent/provider/router.py`) — nothing outside this file imports the
`anthropic` SDK directly.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from agent.provider.base import AIProvider, Message, ProviderError, ProviderResult, Usage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"

# Transient failures worth a retry. AuthenticationError/BadRequestError/
# PermissionDeniedError/NotFoundError/UnprocessableEntityError are not
# retryable — retrying the same malformed/unauthorized request just wastes
# the budget.
_RETRYABLE_EXCEPTIONS = (
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class ClaudeProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        *,
        max_tokens: int = 4096,
        timeout: float = 30.0,
        max_retries: int = 2,
        role: str = "primary",
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env (see .env.example) "
                "before constructing ClaudeProvider."
            )
        self._client = AsyncAnthropic(api_key=key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self.name = "claude"
        self.model = model
        self.role = role
        self.last_usage = Usage()

    async def complete(self, *, system: str, messages: list[Message]) -> ProviderResult:
        attempt = 0
        while True:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=[{"role": m.role, "content": m.content} for m in messages],
                )
                break
            except _RETRYABLE_EXCEPTIONS as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise ProviderError(
                        f"{self._model} failed after {attempt} attempt(s): {exc}", retryable=True
                    ) from exc
                await self._backoff(attempt, exc)
            except anthropic.APIStatusError as exc:
                raise ProviderError(f"{self._model} returned {exc.status_code}: {exc}", retryable=False) from exc
            except anthropic.AnthropicError as exc:
                raise ProviderError(str(exc), retryable=False) from exc

        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        self.last_usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
        return ProviderResult(text=text, usage=self.last_usage, model=self._model, stop_reason=response.stop_reason)

    async def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        attempt = 0
        while True:
            started = False
            try:
                async with self._client.messages.stream(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=[{"role": m.role, "content": m.content} for m in messages],
                ) as stream:
                    async for text in stream.text_stream:
                        started = True
                        yield text
                    final = await stream.get_final_message()
                self.last_usage = Usage(input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens)
                return
            except _RETRYABLE_EXCEPTIONS as exc:
                # Once we've already yielded partial output to the caller
                # (which may have forwarded it to the user as task.delta
                # events), retrying would duplicate content — surface the
                # failure instead of resending from scratch. Only a failure
                # before the first chunk is safe to retry.
                attempt += 1
                if started or attempt > self._max_retries:
                    raise ProviderError(
                        f"{self._model} stream failed after {attempt} attempt(s): {exc}",
                        retryable=not started,
                    ) from exc
                await self._backoff(attempt, exc)
            except anthropic.APIStatusError as exc:
                raise ProviderError(f"{self._model} returned {exc.status_code}: {exc}", retryable=False) from exc
            except anthropic.AnthropicError as exc:
                raise ProviderError(str(exc), retryable=False) from exc

    async def _backoff(self, attempt: int, exc: Exception) -> None:
        delay = min(2**attempt, 10)
        logger.warning(
            "Claude call failed (attempt %d/%d, model=%s): %s — retrying in %ss",
            attempt,
            self._max_retries,
            self._model,
            exc,
            delay,
        )
        await asyncio.sleep(delay)
