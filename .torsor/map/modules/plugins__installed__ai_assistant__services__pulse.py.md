---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/services/pulse.py

Symbols in `plugins/installed/ai_assistant/services/pulse.py`.

- L39 `generate_pulse_insights(*, humanize: bool=True)` (function) — Evaluate every signal, write/update MerchantInsight rows, return them.
- L67 `_humanize_signal(payload: dict)` (function) — Rewrite title + body via the configured LLM in the merchant's brand voice.
- L112 `_upsert(payload: dict)` (function) — Idempotent write: keep one row per (signature) until it's read.
- L134 `_sig(payload: dict)` (function)
- L142 `_low_stock_signal()` (function)
- L169 `_abandoned_cart_signal()` (function)
- L192 `_new_rma_signal()` (function)
- L213 `_revenue_delta_signal()` (function)
- L250 `_expiring_promo_signal()` (function)
- L274 `_poor_review_signal()` (function)
