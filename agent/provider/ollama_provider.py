"""Local model implementation of `AIProvider`, talking to a locally-running
Ollama server (https://ollama.com) over its REST API — no API key, no
cloud call, nothing leaves the machine this backend runs on.

Requires Ollama to already be installed and running (`ollama serve`,
which is what `ollama run <model>` starts automatically) with the
configured model pulled (`ollama pull gemma3`, or whichever
`jarvis_local_model_name` names — see backend/.env.example). This module
does not install Ollama or pull models itself — "never blindly install
unknown software" applies here the same as everywhere else in this
project; that step is the user's own action.

NOT_TESTED in this sandbox: no Ollama server or GPU is available here to
round-trip a real request against. The HTTP request/response shape below
matches Ollama's documented `/api/chat` endpoint; `tests/test_ollama_provider.py`
verifies the request/parsing logic against a mocked transport (httpx's
MockTransport), not a live server — see that file's docstring.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from agent.provider.base import AIProvider, Message, ProviderError, ProviderResult, Usage

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3"


class OllamaProvider(AIProvider):
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,  # local inference on modest hardware can be slow — see docs/DECISIONS.md
        role: str = "primary",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport  # test-only seam (httpx.MockTransport) — None means a real connection
        self.name = "ollama"
        self.model = model
        self.role = role
        self.last_usage = Usage()

    def _payload(self, *, system: str, messages: list[Message], stream: bool) -> dict:
        chat_messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]
        return {"model": self._model, "messages": chat_messages, "stream": stream}

    async def complete(self, *, system: str, messages: list[Message]) -> ProviderResult:
        url = f"{self._base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(url, json=self._payload(system=system, messages=messages, stream=False))
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Ollama ({self._model}) timed out: {exc}", retryable=True) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Could not reach Ollama at {self._base_url} — is `ollama serve` running? ({exc})", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}", retryable=True) from exc

        if response.status_code != 200:
            raise ProviderError(f"Ollama returned {response.status_code}: {response.text}", retryable=False)

        data = response.json()
        text = data.get("message", {}).get("content", "")
        self.last_usage = Usage(
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )
        return ProviderResult(text=text, usage=self.last_usage, model=self._model, stop_reason=data.get("done_reason"))

    async def stream(self, *, system: str, messages: list[Message]) -> AsyncIterator[str]:
        url = f"{self._base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                async with client.stream(
                    "POST", url, json=self._payload(system=system, messages=messages, stream=True)
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ProviderError(f"Ollama returned {response.status_code}: {body.decode(errors='replace')}", retryable=False)

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            self.last_usage = Usage(
                                input_tokens=chunk.get("prompt_eval_count", 0) or 0,
                                output_tokens=chunk.get("eval_count", 0) or 0,
                            )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Ollama ({self._model}) stream timed out: {exc}", retryable=True) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Could not reach Ollama at {self._base_url} — is `ollama serve` running? ({exc})", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama stream failed: {exc}", retryable=True) from exc
