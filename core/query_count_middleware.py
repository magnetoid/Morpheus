"""N+1 detector dev middleware.

Counts SQL queries per request and logs a WARNING when a single
request makes more than ``MORPHEUS_N_PLUS_ONE_THRESHOLD`` queries
(default 50). The default catches N+1 explosions (e.g. a product list
view fetching images one product at a time) without spamming on
legitimately query-heavy admin pages.

ONLY active when ``DEBUG=True`` — production has zero overhead.

Wire it after ``RequestIdMiddleware`` in ``MIDDLEWARE`` so the log
line carries the request id:

    'core.request_id.RequestIdMiddleware',
    'core.query_count_middleware.QueryCountMiddleware',
    'core.errors.middleware.ErrorCaptureMiddleware',

Tune by setting ``MORPHEUS_N_PLUS_ONE_THRESHOLD`` in settings or
``.env``. Set to 0 to log every request's query count (useful when
profiling a specific endpoint).
"""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.db import connection, reset_queries

logger = logging.getLogger('morpheus.query_count')


class QueryCountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = bool(getattr(settings, 'DEBUG', False))
        self.threshold = int(getattr(settings, 'MORPHEUS_N_PLUS_ONE_THRESHOLD', 50))
        # Skip noisy paths (static, healthcheck, admin assets).
        self.skip_prefixes = ('/static/', '/media/', '/api/health/', '/favicon.ico')

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.skip_prefixes):
            return self.get_response(request)

        reset_queries()
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        n = len(connection.queries)

        if self.threshold == 0 or n >= self.threshold:
            level = logging.WARNING if n >= self.threshold else logging.INFO
            logger.log(
                level,
                'query_count: %s %s → %d queries in %.0f ms',
                request.method, request.path, n, elapsed_ms,
            )
            # Log the top 5 most-duplicated SQL statements at DEBUG so
            # devs can drill in without re-running the page.
            if n >= self.threshold and logger.isEnabledFor(logging.DEBUG):
                from collections import Counter
                counts = Counter(q['sql'][:80] for q in connection.queries)
                for sql, count in counts.most_common(5):
                    if count > 1:
                        logger.debug('  %dx %s…', count, sql)
        return response
