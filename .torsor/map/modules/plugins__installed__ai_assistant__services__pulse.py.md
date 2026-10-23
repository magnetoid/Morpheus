---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/ai_assistant/services/pulse.py

Symbols in `plugins/installed/ai_assistant/services/pulse.py`.

- L40 `generate_pulse_insights(*, humanize: bool=True, timeout: float | None=None)` (function) — Evaluate every signal, write/update MerchantInsight rows, return them.
- L77 `_humanize_signal(payload: dict, *, timeout: float | None=None)` (function) — Rewrite title + body via the configured LLM in the merchant's brand voice.
- L123 `_upsert(payload: dict)` (function) — Idempotent write: keep one row per (signature) until it's read.
- L153 `_sig_of_signal(name: str)` (function)
- L157 `_sig(payload: dict)` (function)
- L165 `_low_stock_signal()` (function)
- L192 `_abandoned_cart_signal()` (function)
- L215 `_new_rma_signal()` (function)
- L237 `_revenue_delta_signal()` (function)
- L280 `_expiring_promo_signal()` (function)
- L310 `_poor_review_signal()` (function)
