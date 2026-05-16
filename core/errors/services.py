"""Capture helpers — used by middleware and the client API endpoint."""
from __future__ import annotations

import hashlib
import logging
import re
import traceback as _tb
from typing import Any

logger = logging.getLogger('morpheus.errors')


# Reuse the PII scrubber from observability so emails/phones/IPs never
# land in stored tracebacks.
def _scrub(text: str) -> str:
    try:
        from core.observability import scrub_pii
        return scrub_pii(text or '')
    except Exception:  # noqa: BLE001
        return text or ''


def _fingerprint_server(exc: BaseException) -> str:
    """Stable hash from exception class + first 3 frame file:line pairs."""
    parts = [type(exc).__name__]
    tb = exc.__traceback__
    while tb and len(parts) < 4:
        co = tb.tb_frame.f_code
        # Strip BASE_DIR-style prefixes so the fingerprint stays stable
        # across deploys (different container paths shouldn't shift it).
        filename = co.co_filename.split('/site-packages/', 1)[-1]
        filename = filename.split('/app/', 1)[-1]
        parts.append(f'{filename}:{co.co_name}:{tb.tb_lineno}')
        tb = tb.tb_next
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:32]


def _fingerprint_client(message: str, source_url: str, lineno: int) -> str:
    """Stable hash for a JS error — message + file:line."""
    src = (source_url or '').split('/')[-1].split('?')[0]
    key = f'{message}|{src}:{lineno}'
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]


def _ip_hash(request) -> str:
    ip = ''
    if request is None:
        return ''
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        ip = xff.split(',')[0].strip()
    if not ip:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    if not ip:
        return ''
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16]


_USER_AGENT_LIMIT = 400


def record_error(
    exc: BaseException,
    *,
    request=None,
    kind: str = 'server',
    level: str = 'error',
    extra: dict[str, Any] | None = None,
) -> None:
    """Write a server-side exception to the error log. Fail-soft."""
    try:
        from core.errors.models import ErrorEvent
        traceback_str = _scrub(''.join(_tb.format_exception(type(exc), exc, exc.__traceback__)))
        ErrorEvent.objects.create(
            kind=kind,
            level=level,
            fingerprint=_fingerprint_server(exc),
            exception_class=type(exc).__name__,
            message=_scrub(str(exc))[:2000],
            traceback=traceback_str[:20000],
            path=(getattr(request, 'path', '') or '')[:500],
            method=getattr(request, 'method', '') or '',
            status_code=500,
            user=getattr(request, 'user', None) if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False) else None,
            request_id=getattr(request, 'request_id', '') or '',
            user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[:_USER_AGENT_LIMIT],
            ip_hash=_ip_hash(request),
            metadata=extra or {},
        )
    except Exception:  # noqa: BLE001 — never raise from the capture path
        logger.exception('record_error failed')


_JS_FRAME_RE = re.compile(r'(?:https?://[^\s)]+|/[^\s)]+):(\d+)(?::\d+)?')


def record_client_error(payload: dict[str, Any], *, request=None) -> None:
    """Write a JS error received from the browser. Validates payload shape."""
    from core.errors.models import ErrorEvent

    message = (payload.get('message') or '')[:2000]
    source_url = (payload.get('source') or '')[:500]
    lineno = int(payload.get('lineno') or 0)
    colno = int(payload.get('colno') or 0)
    stack = (payload.get('stack') or '')[:20000]
    page_url = (payload.get('page') or '')[:500]
    browser = (payload.get('browser') or '')[:120]
    level = (payload.get('level') or 'error').lower()
    if level not in ('error', 'warning', 'info'):
        level = 'error'

    fingerprint = _fingerprint_client(message, source_url, lineno)
    ErrorEvent.objects.create(
        kind='client',
        level=level,
        fingerprint=fingerprint,
        exception_class=(payload.get('name') or '')[:200] or 'JSError',
        message=_scrub(message),
        traceback=_scrub(stack),
        path=page_url,
        method='GET',
        status_code=None,
        user=getattr(request, 'user', None) if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False) else None,
        request_id=getattr(request, 'request_id', '') or '',
        user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[:_USER_AGENT_LIMIT],
        ip_hash=_ip_hash(request),
        metadata={
            'source_url': source_url,
            'lineno': lineno,
            'colno': colno,
            'browser': browser,
        },
    )
