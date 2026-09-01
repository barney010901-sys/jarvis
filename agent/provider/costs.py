"""Approximate per-token pricing, for cost estimation only.

These are illustrative, rounded, USD-per-million-token rates — NOT pulled
from a live pricing API and NOT precise to the cent. `backend/app/cost`
uses `estimate_cost()` for budget tracking/observability, not billing.
Update `_PRICING` if the real rates change; nothing else needs to.
"""
from __future__ import annotations

# (input $ / 1M tokens, output $ / 1M tokens)
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}
_DEFAULT_PRICING = (3.0, 15.0)  # assume sonnet-tier if the model is unrecognized


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _PRICING.get(model, _DEFAULT_PRICING)
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 6)
