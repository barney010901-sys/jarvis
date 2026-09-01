import pytest

from agent.provider.base import Message, ProviderError
from agent.provider.costs import estimate_cost
from agent.provider.fake_provider import FakeProvider
from agent.provider.router import FALLBACK, FAST, PRIMARY, ModelRouter


def make_router(*, primary_fail_times=0, fallback_response="fallback answer"):
    primary = FakeProvider(response_text="primary answer", fail_times=primary_fail_times, role=PRIMARY)
    fast = FakeProvider(response_text="fast answer", role=FAST)
    fallback = FakeProvider(response_text=fallback_response, role=FALLBACK)
    return ModelRouter({PRIMARY: primary, FAST: fast, FALLBACK: fallback}), primary, fast, fallback


@pytest.mark.asyncio
async def test_complete_uses_requested_role():
    router, primary, fast, fallback = make_router()
    result = await router.complete(FAST, system="sys", messages=[Message(role="user", content="hi")])
    assert result.text == "fast answer"


@pytest.mark.asyncio
async def test_complete_falls_back_on_provider_error():
    # primary always raises (fail_times huge relative to single call)
    router, primary, fast, fallback = make_router(primary_fail_times=99)
    result = await router.complete(PRIMARY, system="sys", messages=[Message(role="user", content="hi")])
    assert result.text == "fallback answer"


@pytest.mark.asyncio
async def test_complete_raises_when_fallback_also_unavailable():
    primary = FakeProvider(fail_times=99, role=PRIMARY)
    router = ModelRouter({PRIMARY: primary})
    with pytest.raises(ProviderError):
        await router.complete(PRIMARY, system="sys", messages=[])


@pytest.mark.asyncio
async def test_stream_yields_chunks_from_requested_role():
    router, primary, fast, fallback = make_router()
    chunks = [c async for c in router.stream(PRIMARY, system="sys", messages=[])]
    assert "".join(chunks).strip() == "primary answer"


@pytest.mark.asyncio
async def test_stream_falls_back_before_first_chunk():
    router, primary, fast, fallback = make_router(primary_fail_times=99)
    chunks = [c async for c in router.stream(PRIMARY, system="sys", messages=[])]
    assert "".join(chunks).strip() == "fallback answer"


def test_estimate_cost_known_model():
    cost = estimate_cost("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(3.0 + 15.0)


def test_estimate_cost_unknown_model_uses_default():
    cost = estimate_cost("some-future-model", input_tokens=1_000_000, output_tokens=0)
    assert cost == pytest.approx(3.0)
