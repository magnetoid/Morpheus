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

# plugins/installed/analytics/tasks.py

Symbols in `plugins/installed/analytics/tasks.py`.

- L13 `log_analytics_event(payload)` (function) — Back-compat: AnalyticsPlugin.record_event hooks fan out to this.
- L37 `_kind_for(name: str)` (function)
- L60 `roll_daily_task()` (function)
- L69 `trim_old_events_task(keep_days: int | None=None)` (function)
- L85 `detect_anomalies_task()` (function)
- L95 `collect_ad_spend_task()` (function) — Nightly: pull each channel's ad spend (ANALYTICS_AD_SPEND filter) → AdSpendSnapshot.
- L105 `attribute_revenue_task()` (function) — Nightly: reconstruct journeys, apply every attribution model → DailyMetric.
