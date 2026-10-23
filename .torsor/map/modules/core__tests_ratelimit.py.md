---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests_ratelimit.py

Symbols in `core/tests_ratelimit.py`.

- L16 `_ok(_request)` (function)
- L20 `ClientIdTests` (class)
- L21 `test_cf_connecting_ip_wins_over_xff(self)` (method)
- L30 `test_falls_back_to_xff_then_remote(self)` (method)
- L36 `RateLimitMiddlewareTests` (class)
- L37 `setUp(self)` (method)
- L42 `_req(self, *, cf='1.2.3.4', path='/shop/', user=None)` (method)
- L47 `test_anonymous_limited_after_budget(self)` (method)
- L52 `test_distinct_client_ips_have_separate_buckets(self)` (method)
- L58 `test_staff_is_never_limited(self)` (method)
- L65 `test_bypassed_path_skips(self)` (method)
