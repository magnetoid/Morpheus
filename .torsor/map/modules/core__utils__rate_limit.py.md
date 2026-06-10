---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/utils/rate_limit.py

Symbols in `core/utils/rate_limit.py`.

- L28 `RateLimitExceeded` (class)
- L29 `__init__(self, *, retry_after: int=0)` (method)
- L34 `check_and_consume(*, key: str, max_per_window: int, window_seconds: int)` (function) — Return remaining quota, or raise RateLimitExceeded.
- L56 `rate_limited(*, key_fn: Callable, max_per_window: int, window_seconds: int=60)` (function) — Decorator. `key_fn(request)` returns a string key (e.g. user id).
