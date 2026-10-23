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

# plugins/installed/analytics/services.py

Symbols in `plugins/installed/analytics/services.py`.

- L32 `_hash_ip(ip: str)` (function)
- L36 `_device_from_ua(ua: str)` (function)
- L45 `_config()` (function) — Resolved analytics PluginConfig (cached by the plugin).
- L67 `_excluded_user(user)` (function) — Whether the configured exclusions cover this user/customer.
- L85 `should_track_request(request)` (function) — Whether this request's visitor should generate analytics events.
- L96 `should_track_customer(customer)` (function) — Request-less equivalent of `should_track_request` for the event-hook
- L102 `_inferred_ai_source(request)` (function) — 'ai:chatgpt' when the visit's referrer is an AI assistant, else ''.
- L108 `_analytics_consent_granted(request)` (function) — True when the visitor granted the 'analytics' consent category.
- L124 `get_or_create_session(request, *, response=None)` (function) — Resolve the visitor's analytics session. Sets the cookie if missing.
- L216 `record_event(*, name: str, kind: str='custom', request=None, session=None, customer=None, url: str='', product_slug: str='', search_query: str='', revenue: Money | None=None, agent_name: str='', payload: dict[str, Any] | None=None, scroll_depth: int | None=None, duration_ms: int | None=None, error_context: dict | None=None, is_realtime: bool=False, idempotency_key: str='')` (function) — The single entry-point for recording an event.
- L281 `roll_daily(*, day: date | None=None)` (function) — Compute DailyMetric rows for `day` (default: yesterday). Idempotent.
- L384 `summary_for(*, days: int=7)` (function) — Headline numbers for the dashboard overview card.
- L469 `ai_source_from_referrer(referrer: str)` (function) — 'https://chatgpt.com/c/abc' → 'chatgpt'; '' when not an AI assistant.
- L485 `ai_crawler_from_ua(user_agent: str)` (function) — Bot slug when the UA is a known AI crawler, else ''.
- L494 `record_ai_crawler_hit(bot: str)` (function) — Bump today's DailyMetric counter for one AI-crawler request. Fail-soft.
- L515 `ai_traffic_summary(*, days: int=30)` (function) — The merchant's AI-visibility picture: human sessions + revenue arriving
- L555 `revenue_by_source(*, days: int=30)` (function) — Last-touch purchase revenue grouped by the converting session's
- L590 `funnel_for(*, steps: list[str], days: int=30)` (function) — Walk the funnel: count distinct sessions hitting step1, then those
- L612 `top_products(*, days: int=30, limit: int=10)` (function)
- L625 `top_searches(*, days: int=30, limit: int=10)` (function)
- L638 `agent_activity(*, days: int=30)` (function)
- L651 `real_time(*, minutes: int=30)` (function) — Last-N-minutes stream for the real-time tile.
- L677 `predictive_trends(*, days: int=30)` (function) — Predictive trend forecasting using simple moving average and linear projection.
- L709 `trim_old_events(*, keep_days: int=90)` (function) — Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
