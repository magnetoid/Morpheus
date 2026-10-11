"""Server-side error-capture middleware.

Catches any unhandled exception raised by a view, records it via
``record_error``, then re-raises so Django's normal exception handling
(debug page in DEV, 500 template in PROD) runs unchanged. The capture
is fail-soft — a bug in the capture path never breaks the original
request.

It also publishes the current request (``core.errors.context.current_request``)
so an error recorded deeper down (a hook, a log line) knows the request it
happened in, and, while detailed capture is on, records the request-level
events a crash log never sees: rejected requests, broken internal links, a 5xx
answered without an exception, slow responses
(docs/plans/detailed-error-capture-2026-10.md).
"""

from __future__ import annotations

import logging
import time

from core.errors.services import record_error

logger = logging.getLogger('morpheus.errors')

#: A response slower than this is recorded while detailed capture is on.
SLOW_MS = 3000
_REJECTED = {
    400: 'Bad Request',
    403: 'Forbidden',
    405: 'Method Not Allowed',
    429: 'Too Many Requests',
}
#: Machine endpoints and assets: their status says nothing a fixer needs.
_SKIP_PREFIXES = ('/static/', '/media/', '/healthz', '/readyz', '/api/errors/client/')


class ErrorCaptureMiddleware:
    """Record every unhandled exception, then let Django handle it normally."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core.errors.context import current_request

        token = current_request.set(request)
        started = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            current_request.reset(token)
        try:
            self._detailed(request, response, started)
        except Exception:  # noqa: BLE001
            logger.exception('detailed request capture failed')
        return response

    def process_exception(self, request, exception):
        # Suppress: 404 isn't an "error" worth storing.
        from django.http import Http404

        if isinstance(exception, Http404):
            return None
        try:
            record_error(exception, request=request, kind='server')
            request._morph_error_recorded = True
        except Exception:  # noqa: BLE001
            logger.exception('process_exception capture failed')
        return None  # let Django render its normal 500

    def _detailed(self, request, response, started: float) -> None:
        from core.errors.mode import detailed_active

        if not detailed_active():
            return
        path = getattr(request, 'path', '') or ''
        if path.startswith(_SKIP_PREFIXES):
            return
        from core.errors.context import is_same_site_referer, request_context
        from core.errors.services import record_http

        status = int(getattr(response, 'status_code', 0) or 0)
        duration_ms = int((time.monotonic() - started) * 1000)
        method = getattr(request, 'method', '') or ''
        common = {'request': request, 'status': status, 'duration_ms': duration_ms}

        if status >= 500 and not getattr(request, '_morph_error_recorded', False):
            record_http(
                'server_status',
                message=f'{status} answered for {method} {path} without an exception',
                **common,
            )
        elif status in _REJECTED:
            record_http('rejected', message=f'{_REJECTED[status]}: {method} {path}', **common)
        elif status == 404 and is_same_site_referer(request):
            referer = request_context(request).get('referer', '')
            record_http(
                'broken_link', message=f'Broken link: {path} (linked from {referer})', **common
            )

        if duration_ms >= SLOW_MS and not getattr(response, 'streaming', False):
            record_http(
                'slow',
                message=f'Slow response: {duration_ms / 1000:.1f} s for {method} {path}',
                **common,
            )
