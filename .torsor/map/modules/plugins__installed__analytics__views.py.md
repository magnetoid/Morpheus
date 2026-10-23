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

# plugins/installed/analytics/views.py

Symbols in `plugins/installed/analytics/views.py`.

- L49 `custom_events_config(request)` (function) — Returns the list of active CustomEventConfig items for the frontend JS to attach listeners.
- L66 `track_beacon(request)` (function) — Storefront JS calls this with `{name, kind?, url?, product_slug?, search_query?, scroll_depth?, duration_ms?, error_context?}`.
- L178 `export_data(request)` (function) — Export analytics data in CSV/JSON format.
- L218 `overview(request)` (function)
- L245 `realtime(request)` (function)
- L260 `funnel_view(request)` (function) — Default funnel: pageview → product.viewed → cart.add → checkout.started → order.placed.
- L300 `cohort_view(request)` (function) — Weekly cohort retention table — % of customers signing up in
- L334 `realtime_json(request)` (function) — JSON feed for the realtime dashboard's auto-refresh.
