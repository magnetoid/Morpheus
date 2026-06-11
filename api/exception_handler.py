"""
DRF exception handler.

Default DRF behavior for an unhandled exception is to return the raw
traceback in DEBUG and a 500 in prod. We want a stable, consistent
error envelope that always includes the request_id and never leaks
exception classes or paths in prod.

Wired via `REST_FRAMEWORK['EXCEPTION_HANDLER']` in settings.py.
"""

from __future__ import annotations

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from core.request_id import current_request_id
from plugins.installed.observability.services import record_error  # type: ignore[import-not-found]

logger = logging.getLogger('morpheus.api.errors')


def morpheus_exception_handler(exc, context):
    """Standardize errors into `{status, code, message, request_id}`."""
    response = drf_default_handler(exc, context)

    if response is not None:
        # DRF handled the exception (auth, validation, perms, etc) — wrap.
        return Response(
            data={
                'status': 'error',
                'code': type(exc).__name__,
                'message': _safe_message(response.data),
                'request_id': current_request_id(),
            },
            status=response.status_code,
            headers={
                k: v for k, v in (response.headers or {}).items() if k.lower() != 'content-type'
            },
        )

    # Unknown / unhandled — log loudly, return a 500 with no internals.
    logger.error(
        'unhandled DRF exception: %s',
        exc,
        exc_info=True,
        extra={
            'request_id': current_request_id(),
        },
    )
    try:  # noqa: SIM105
        record_error(
            source='api.rest',
            message=str(exc)[:5000],
            stack_trace=_safe_stack(exc),
            metadata={'request_id': current_request_id()},
        )
    except Exception:  # noqa: BLE001, S110
        pass
    return Response(
        data={
            'status': 'error',
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error.',
            'request_id': current_request_id(),
        },
        status=500,
    )


def _safe_message(data) -> str:
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        return '; '.join(f'{k}: {v}' for k, v in data.items())
    if isinstance(data, list) and data:
        return '; '.join(str(x) for x in data)
    return str(data)[:500]


def _safe_stack(exc) -> str:
    import traceback

    try:
        return ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:20000]
    except Exception:  # noqa: BLE001
        return ''
