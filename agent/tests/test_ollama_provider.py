"""Tests for OllamaProvider against a mocked HTTP transport
(httpx.MockTransport) — no real Ollama server or GPU exists in this
sandbox to round-trip a live request against (see the module's own
docstring). These verify the request shape sent and the response
parsing logic match Ollama's documented `/api/chat` API; a live
request/response round-trip against a real `ollama serve` remains
NOT_TESTED here.
"""
from __future__ import annotations

import json

import httpx
import pytest

from agent.provider.base import Message, ProviderError
from agent.provider.ollama_provider import OllamaProvider


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_complete_sends_system_message_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "jarvis",
                "message": {"role": "assistant", "content": "hello from jarvis"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 4,
            },
        )

    provider = OllamaProvider(model="jarvis", base_url="http://localhost:11434", transport=_transport(handler))
    result = await provider.complete(system="You are Jarvis.", messages=[Message(role="user", content="hi")])

    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["model"] == "jarvis"
    assert captured["body"]["stream"] is False
    assert captured["body"]["messages"][0] == {"role": "system", "content": "You are Jarvis."}
    assert captured["body"]["messages"][1] == {"role": "user", "content": "hi"}

    assert result.text == "hello from jarvis"
    assert result.model == "jarvis"
    assert result.stop_reason == "stop"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 4
    assert provider.last_usage.output_tokens == 4


@pytest.mark.asyncio
async def test_complete_raises_provider_error_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="model not found")

    provider = OllamaProvider(transport=_transport(handler))
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(system="s", messages=[Message(role="user", content="hi")])
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_complete_raises_retryable_provider_error_on_connect_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = OllamaProvider(transport=_transport(handler))
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(system="s", messages=[Message(role="user", content="hi")])
    assert exc_info.value.retryable is True
    assert "ollama serve" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_yields_chunks_and_sets_usage_at_done():
    lines = [
        json.dumps({"message": {"content": "hel"}, "done": False}),
        json.dumps({"message": {"content": "lo"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True, "prompt_eval_count": 5, "eval_count": 2}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(lines) + "\n"
        return httpx.Response(200, content=body.encode(), headers={"content-type": "application/x-ndjson"})

    provider = OllamaProvider(transport=_transport(handler))
    chunks = [c async for c in provider.stream(system="s", messages=[Message(role="user", content="hi")])]

    assert "".join(chunks) == "hello"
    assert provider.last_usage.input_tokens == 5
    assert provider.last_usage.output_tokens == 2


@pytest.mark.asyncio
async def test_stream_raises_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    provider = OllamaProvider(transport=_transport(handler))
    with pytest.raises(ProviderError) as exc_info:
        async for _ in provider.stream(system="s", messages=[Message(role="user", content="hi")]):
            pass
    assert exc_info.value.retryable is False
