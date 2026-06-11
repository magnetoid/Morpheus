"""Server-side error-capture middleware.

Catches any unhandled exception raised by a view, records it via
``record_error``, then re-raises so Django's normal exception handling
(debug page in DEV, 500 template in PROD) runs unchanged. The capture
is fail-soft — a bug in the capture path never breaks the original
request.
"""

from __future__ import annotations

import logging

from core.errors.services import record_error

logger = logging.getLogger('morpheus.errors')


class ErrorCaptureMiddleware:
    """Record every unhandled exception, then let Django handle it normally."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Suppress: 404 isn't an "error" worth storing.
        from django.http import Http404

        if isinstance(exception, Http404):
            return None
        try:
            record_error(exception, request=request, kind='server')
        except Exception:  # noqa: BLE001
            logger.exception('process_exception capture failed')
        return None  # let Django render its normal 500
