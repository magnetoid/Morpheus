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

# plugins/installed/analytics/tests/test_tracking_enhancements.py

Symbols in `plugins/installed/analytics/tests/test_tracking_enhancements.py`.

- L14 `AnalyticsTrackingTests` (class)
- L15 `setUp(self)` (method)
- L22 `test_get_or_create_session_cross_device_id(self)` (method) — Verify cross_device_id and geo tracking works
- L38 `test_track_beacon_new_metrics(self)` (method) — Verify the beacon correctly processes new scroll, duration, and error metrics
- L62 `test_error_tracking(self)` (method) — Verify error context is captured
- L80 `BeaconNoContentTests` (class) — A 204 carries no body: gunicorn dropped the JSON and logged a warning per hit.
- L83 `test_the_beacon_answers_with_an_empty_204(self)` (method)
