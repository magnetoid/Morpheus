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

# plugins/installed/analytics/tests/test_analytics.py

Symbols in `plugins/installed/analytics/tests/test_analytics.py`.

- L31 `_set_analytics_config(**kwargs)` (function)
- L53 `SessionTests` (class)
- L54 `test_creates_session_with_cookie(self)` (method)
- L65 `test_links_customer_after_login(self)` (method)
- L78 `RecordEventTests` (class)
- L79 `test_record_event_writes_row_and_bumps_session(self)` (method)
- L95 `RollupTests` (class)
- L96 `setUp(self)` (method)
- L101 `test_roll_daily_writes_metrics(self)` (method)
- L134 `FunnelTests` (class)
- L135 `test_funnel_walks_steps(self)` (method)
- L162 `AgentToolTests` (class)
- L163 `test_tools_registered(self)` (method)
- L176 `TrimTests` (class)
- L177 `test_trim_old_events(self)` (method)
- L190 `StaffExclusionTests` (class) — Staff/admins are excluded from tracking; everyone else is tracked.
- L193 `setUp(self)` (method)
- L196 `test_anonymous_is_tracked(self)` (method)
- L203 `test_customer_is_tracked(self)` (method)
- L208 `test_staff_is_excluded(self)` (method)
- L215 `test_superuser_is_excluded(self)` (method)
- L220 `test_beacon_skips_staff(self)` (method)
- L236 `test_exclude_staff_toggle_off_tracks_staff(self)` (method)
- L245 `test_exclude_logged_in_toggle_excludes_customer(self)` (method)
- L252 `test_hook_path_excludes_staff_customer(self)` (method) — A staff member's order/product events (no HttpRequest) are excluded.
