---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/utils/rate_limit.py

Symbols in `core/utils/rate_limit.py`.

- L29 `RateLimitExceeded` (class)
- L30 `__init__(self, *, retry_after: int=0)` (method)
- L35 `check_and_consume(*, key: str, max_per_window: int, window_seconds: int)` (function) — Return remaining quota, or raise RateLimitExceeded.
- L57 `rate_limited(*, key_fn: Callable, max_per_window: int, window_seconds: int=60)` (function) — Decorator. `key_fn(request)` returns a string key (e.g. user id).
