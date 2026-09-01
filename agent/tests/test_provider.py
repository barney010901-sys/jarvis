import pytest

from agent.coding_agent.interface import CodingAgentInterface
from agent.provider.base import AIProvider
from agent.provider.claude_provider import ClaudeProvider


def test_ai_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()  # type: ignore[abstract]


def test_coding_agent_interface_is_abstract():
    with pytest.raises(TypeError):
        CodingAgentInterface()  # type: ignore[abstract]


def test_claude_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError):
        ClaudeProvider(api_key="")


def test_claude_provider_constructs_with_key():
    provider = ClaudeProvider(api_key="sk-test-not-real")
    assert provider is not None
