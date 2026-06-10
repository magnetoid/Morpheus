---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/analytics/services.py

Symbols in `plugins/installed/analytics/services.py`.

- L31 `_hash_ip(ip: str)` (function)
- L35 `_device_from_ua(ua: str)` (function)
- L44 `get_or_create_session(request, *, response=None)` (function) — Resolve the visitor's analytics session. Sets the cookie if missing.
- L85 `record_event(*, name: str, kind: str='custom', request=None, session=None, customer=None, url: str='', product_slug: str='', search_query: str='', revenue: Optional[Money]=None, agent_name: str='', payload: Optional[dict[str, Any]]=None)` (function) — The single entry-point for recording an event.
- L130 `roll_daily(*, day: Optional[date]=None)` (function) — Compute DailyMetric rows for `day` (default: yesterday). Idempotent.
- L194 `summary_for(*, days: int=7)` (function) — Headline numbers for the dashboard overview card.
- L228 `funnel_for(*, steps: list[str], days: int=30)` (function) — Walk the funnel: count distinct sessions hitting step1, then those
- L250 `top_products(*, days: int=30, limit: int=10)` (function)
- L261 `top_searches(*, days: int=30, limit: int=10)` (function)
- L272 `agent_activity(*, days: int=30)` (function)
- L283 `real_time(*, minutes: int=30)` (function) — Last-N-minutes stream for the real-time tile.
- L305 `trim_old_events(*, keep_days: int=90)` (function) — Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
