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

# plugins/installed/analytics/services_attribution.py

Symbols in `plugins/installed/analytics/services_attribution.py`.

- L23 `_weights(journey: list, model: str)` (function) — Per-touch weights (Decimals summing to 1) for a journey of n touches.
- L49 `attribute(journey: list, revenue, model: str)` (function) — Split `revenue` across a journey `[(channel, timestamp)]` (oldest→newest).
- L68 `_channel_of(session)` (function)
- L73 `build_journey(customer_id, purchase_ts, lookback_days: int=30)` (function) — A purchaser's touch sequence: their sessions' UTM sources within the
- L86 `collect_ad_spend()` (function) — Fire ANALYTICS_AD_SPEND, snapshot each channel's spend into AdSpendSnapshot
- L111 `attribute_revenue(days: int=30)` (function) — Reconstruct journeys for purchases in the window, apply every model, and
- L147 `roas_by_channel(model: str='last_touch', days: int=30)` (function) — Per-channel spend vs attributed revenue → ROAS, from the newest snapshot of
