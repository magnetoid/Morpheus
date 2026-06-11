"""
Request ID middleware + logging filter.

* Every request gets an `X-Request-ID` (generated if the client didn't send one).
* The id is attached to `request.request_id` and to the response header.
* A logging filter (`RequestIdFilter`) injects `request_id` into every log
  record so JSON logs come out fully correlated.
"""

from __future__ import annotations

import contextvars
import logging
import uuid

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    'morph_request_id',
    default='-',
)


def current_request_id() -> str:
    """Return the request id for the current execution context (or '-')."""
    return _request_id_ctx.get()


class RequestIdMiddleware:
    """Generate / propagate a request id, store it in the contextvar.

    Honors `X-Request-ID` from the client (truncated to 64 chars), or
    generates a UUID4 hex.
    """

    HEADER = 'HTTP_X_REQUEST_ID'
    RESPONSE_HEADER = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = (request.META.get(self.HEADER) or '').strip()[:64] or uuid.uuid4().hex
        token = _request_id_ctx.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            _request_id_ctx.reset(token)
        try:  # noqa: SIM105
            response[self.RESPONSE_HEADER] = rid
        except Exception:  # noqa: BLE001, S110
            pass
        return response


class RequestIdFilter(logging.Filter):
    """Logging filter that attaches `request_id` to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True
