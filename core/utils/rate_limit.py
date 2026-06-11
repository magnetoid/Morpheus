"""Sliding-window per-key rate limiter, backed by Django cache.

    from core.utils.rate_limit import rate_limited, RateLimitExceeded

    @rate_limited(
        key_fn=lambda request: f'agent:{request.user.pk or request.META["REMOTE_ADDR"]}',
        max_per_window=20,
        window_seconds=60,
    )
    def my_view(request): ...

When the limit is exceeded `RateLimitExceeded` is raised. View decorators
catch it and return HTTP 429.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable

from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger('morpheus.utils.rate_limit')


class RateLimitExceeded(Exception):
    def __init__(self, *, retry_after: int = 0):
        self.retry_after = retry_after
        super().__init__(f'rate limit exceeded — retry after {retry_after}s')


def check_and_consume(*, key: str, max_per_window: int, window_seconds: int) -> int:
    """Return remaining quota, or raise RateLimitExceeded.

    Uses a fixed window keyed by `int(time.time() / window_seconds)` for
    O(1) cache ops. Trades absolute precision (window edges can let 2x
    burst through) for simplicity — fine for LLM/API throttling.
    """
    bucket = int(time.time() / max(1, window_seconds))
    cache_key = f'rl:{key}:{bucket}'
    try:
        count = cache.incr(cache_key)
    except ValueError:
        count = None
    if count is None:
        cache.set(cache_key, 1, timeout=window_seconds + 5)
        count = 1
    if count > max_per_window:
        retry_after = window_seconds - (int(time.time()) % max(1, window_seconds))
        raise RateLimitExceeded(retry_after=max(1, retry_after))
    return max_per_window - count


def rate_limited(*, key_fn: Callable, max_per_window: int, window_seconds: int = 60):
    """Decorator. `key_fn(request)` returns a string key (e.g. user id)."""

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                key = key_fn(request)
            except Exception:  # noqa: BLE001
                return view(request, *args, **kwargs)
            try:
                check_and_consume(
                    key=str(key),
                    max_per_window=max_per_window,
                    window_seconds=window_seconds,
                )
            except RateLimitExceeded as e:
                resp = HttpResponse('Rate limit exceeded.', status=429)
                resp['Retry-After'] = str(e.retry_after)
                return resp
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
