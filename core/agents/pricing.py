"""Approximate token → USD cost estimation for dashboard display (NOT billing).

Prices are per 1,000,000 tokens as ``(input, output)`` USD, from each provider's
public pricing. Model names vary by suffix/date, so matching is longest-prefix /
substring. Unknown models estimate 0.0 (the UI shows "—"). Update as prices move.
"""

from __future__ import annotations

# (input_per_1M, output_per_1M) in USD.
_PRICES: dict[str, tuple[float, float]] = {
    'gpt-4o-mini': (0.15, 0.60),
    'gpt-4o': (2.50, 10.00),
    'gpt-4.1-mini': (0.40, 1.60),
    'gpt-4.1': (2.00, 8.00),
    'o4-mini': (1.10, 4.40),
    'claude-3-5-haiku': (0.80, 4.00),
    'claude-3-5-sonnet': (3.00, 15.00),
    'claude-3-7-sonnet': (3.00, 15.00),
    'claude-sonnet-4': (3.00, 15.00),
    'claude-opus-4': (15.00, 75.00),
    'claude-3-opus': (15.00, 75.00),
    'gemini-2.0-flash': (0.10, 0.40),
    'gemini-1.5-pro': (1.25, 5.00),
    'grok-4': (5.00, 15.00),
    'grok-2': (2.00, 10.00),
    'deepseek-chat': (0.27, 1.10),
    'deepseek-reasoner': (0.55, 2.19),
    # The production model. APPROXIMATE — pinned to the deepseek-reasoner tier
    # rather than a published figure; correct it when the real price is known.
    # An approximation is deliberately better than the alternative here: an
    # UNPRICED model estimates $0.00, which silently neuters the merchant's
    # daily `spend_cap_daily` guardrail (it can never trip, leaving only the
    # model-independent run-count cap). Any model this deployment can actually
    # reach belongs in this table — `is_priced()` reports the gap.
    'deepseek-v4-pro': (0.55, 2.19),
    'llama3.2': (0.0, 0.0),  # local / self-hosted — no per-token cost
}


def _match(model: str) -> tuple[float, float] | None:
    m = (model or '').strip().lower()
    if not m:
        return None
    if m in _PRICES:
        return _PRICES[m]
    # Longest matching key so 'claude-3-5-sonnet-20241022' → 'claude-3-5-sonnet'.
    best_key = ''
    for key in _PRICES:
        if (m.startswith(key) or key in m) and len(key) > len(best_key):
            best_key = key
    return _PRICES[best_key] if best_key else None


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD estimate for a (model, token-counts) pair. 0.0 for unknown models."""
    price = _match(model)
    if price is None:
        return 0.0
    inp, outp = price
    return (max(0, prompt_tokens) / 1_000_000) * inp + (
        max(0, completion_tokens) / 1_000_000
    ) * outp


def is_priced(model: str) -> bool:
    """Whether we have a price for this model (vs. estimating 0)."""
    return _match(model) is not None
