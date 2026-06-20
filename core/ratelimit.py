"""Best-effort rate limiter using the project's Redis cache.

Rolls a fixed-window counter per (client_ip, route_bucket) into the
Django cache backend. Limits are declarative — see ``_RULES`` below for
the table of per-prefix budgets. Anything not matching a rule falls
through to the GLOBAL_PER_MINUTE budget.

Design notes
------------
* **Fixed window**, not token bucket — a tiny burst at the boundary is
  cheaper to reason about than a leaky bucket and easier to debug from
  ``redis-cli``. If sustained protection becomes necessary, swap in a
  Lua-script sliding window.
* **Fail-open** — if the cache backend is unreachable, requests are
  let through. A broken Redis must not take down the storefront.
* **Bypassed paths** — health checks, static/media, dashboard internal
  routes, and the Stripe webhook. Stripe retries on non-2xx, so
  rate-limiting their delivery would create real problems.
* **Identifier** — first hop of ``X-Forwarded-For`` (Cloudflare /
  Plesk strip-and-set this), falling back to ``REMOTE_ADDR``.
"""

from __future__ import annotations

import logging
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('morpheus.ratelimit')

# (path-prefix-regex, bucket name, requests-per-minute)
# /graphql + /api are already covered by api.rate_limit.RateLimitMiddleware
# with auth-aware limits — we deliberately don't double-count them here.
_RULES = [
    (re.compile(r'^/auth/(login|signup|password/reset)/?'), 'auth', 10),
    (re.compile(r'^/search/?'), 'search', 30),
]
_GLOBAL_BUCKET = 'global'
_DEFAULT_GLOBAL_PER_MINUTE = 300

# Paths that must never be rate-limited.
_BYPASS = (
    '/healthz',
    '/static/',
    '/media/',
    '/graphql',
    '/api/',  # covered by api.rate_limit (auth-aware)
    '/payments/webhooks/',  # gateway retries are not user traffic
    '/dashboard/assistant/history/',  # internal poller; high frequency by design
)


def _client_id(request) -> str:
    # Behind Cloudflare the real client IP is CF-Connecting-IP (the payments +
    # cloudflare plugins resolve it the same way). The XFF first-hop can collapse
    # to a single shared proxy IP through the Cloudflare→Plesk→Traefik chain,
    # which would funnel EVERY visitor into one 'global' bucket and trip the
    # limit under normal traffic. Prefer CF-Connecting-IP, then XFF, then peer.
    cf = request.META.get('HTTP_CF_CONNECTING_IP', '')
    if cf:
        return cf.strip()
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'anon')


def _rule_for(path: str):
    for pattern, bucket, limit in _RULES:
        if pattern.match(path):
            return bucket, limit
    global_limit = int(
        getattr(settings, 'MORPHEUS_RATELIMIT_PER_MINUTE', _DEFAULT_GLOBAL_PER_MINUTE)
    )
    return _GLOBAL_BUCKET, global_limit


def _is_bypassed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _BYPASS)


class RateLimitMiddleware:
    """Module-level on/off via ``MORPHEUS_RATELIMIT_ENABLED`` setting."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = bool(getattr(settings, 'MORPHEUS_RATELIMIT_ENABLED', not settings.DEBUG))

    def __call__(self, request):
        if not self.enabled or _is_bypassed(request.path):
            return self.get_response(request)

        # Trusted operators (staff/admin) are never IP-rate-limited — their
        # dashboard usage is legitimately bursty (htmx polls, multi-widget
        # pages) and was tripping the global bucket. Auth middleware runs before
        # this one, so request.user is resolved.
        user = getattr(request, 'user', None)
        if user is not None and (
            getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)
        ):
            return self.get_response(request)

        bucket, limit = _rule_for(request.path)
        client = _client_id(request)
        # Fixed minute-window key. Adding the wall-clock minute number
        # gives every minute its own counter without manual eviction.
        window = int(time.time() // 60)
        key = f'ratelimit:{bucket}:{client}:{window}'

        try:
            count = cache.get(key) or 0
            if count >= limit:
                return JsonResponse(
                    {
                        'error': 'rate_limited',
                        'detail': f'too many requests; bucket={bucket} limit={limit}/min',
                    },
                    status=429,
                    headers={
                        'Retry-After': '60',
                        'X-RateLimit-Bucket': bucket,
                        'X-RateLimit-Limit': str(limit),
                    },
                )
            try:
                cache.incr(key)
            except ValueError:
                # No prior key — atomic-set with TTL of slightly over a window
                # so the counter expires naturally.
                cache.set(key, 1, timeout=70)
        except Exception as e:  # noqa: BLE001 — fail open on cache outage
            logger.debug('ratelimit fail-open: %s', e)

        return self.get_response(request)
