---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/analytics/services.py

Symbols in `plugins/installed/analytics/services.py`.

- L32 `_hash_ip(ip: str)` (function)
- L36 `_device_from_ua(ua: str)` (function)
- L45 `get_or_create_session(request, *, response=None)` (function) — Resolve the visitor's analytics session. Sets the cookie if missing.
- L90 `record_event(*, name: str, kind: str='custom', request=None, session=None, customer=None, url: str='', product_slug: str='', search_query: str='', revenue: Money | None=None, agent_name: str='', payload: dict[str, Any] | None=None)` (function) — The single entry-point for recording an event.
- L136 `roll_daily(*, day: date | None=None)` (function) — Compute DailyMetric rows for `day` (default: yesterday). Idempotent.
- L216 `summary_for(*, days: int=7)` (function) — Headline numbers for the dashboard overview card.
- L256 `funnel_for(*, steps: list[str], days: int=30)` (function) — Walk the funnel: count distinct sessions hitting step1, then those
- L278 `top_products(*, days: int=30, limit: int=10)` (function)
- L291 `top_searches(*, days: int=30, limit: int=10)` (function)
- L304 `agent_activity(*, days: int=30)` (function)
- L317 `real_time(*, minutes: int=30)` (function) — Last-N-minutes stream for the real-time tile.
- L343 `trim_old_events(*, keep_days: int=90)` (function) — Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
