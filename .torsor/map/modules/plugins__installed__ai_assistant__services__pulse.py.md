---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/pulse.py

Symbols in `plugins/installed/ai_assistant/services/pulse.py`.

- L40 `generate_pulse_insights(*, humanize: bool=True)` (function) — Evaluate every signal, write/update MerchantInsight rows, return them.
- L72 `_humanize_signal(payload: dict)` (function) — Rewrite title + body via the configured LLM in the merchant's brand voice.
- L118 `_upsert(payload: dict)` (function) — Idempotent write: keep one row per (signature) until it's read.
- L148 `_sig(payload: dict)` (function)
- L156 `_low_stock_signal()` (function)
- L183 `_abandoned_cart_signal()` (function)
- L206 `_new_rma_signal()` (function)
- L228 `_revenue_delta_signal()` (function)
- L271 `_expiring_promo_signal()` (function)
- L301 `_poor_review_signal()` (function)
