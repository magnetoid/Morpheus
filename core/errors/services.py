"""Capture helpers — used by middleware and the client API endpoint."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import traceback as _tb
from typing import Any

logger = logging.getLogger('morpheus.errors')


#: Secrets an error can quote: a provider's "Incorrect API key provided: sk-…", an
#: Authorization header in a traceback, a Linda turn token, a database URL. Removed
#: before anything is stored, shown on the error page or emailed in the digest.
_SECRETS = (
    (re.compile(r'\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}'), '<secret>'),
    (re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{12,}'), 'Bearer <secret>'),
    (re.compile(r'\blt1\.[A-Za-z0-9._\-]{8,}'), '<turn-token>'),
    (
        re.compile(
            r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16})\b'
        ),
        '<secret>',
    ),
    (re.compile(r'(://[^:/\s@]+:)[^@\s/]+@'), r'\1<secret>@'),
    (
        re.compile(
            r'(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|passwd)(\s*[=:]\s*)[\'"]?[^\s\'",;)}]+'
        ),
        r'\1\2<secret>',
    ),
)


def redact_secrets(text: str) -> str:
    for pattern, placeholder in _SECRETS:
        text = pattern.sub(placeholder, text)
    return text


# Secrets first, then the PII scrubber from observability, so keys, emails,
# phones and IPs never land in a stored message or traceback.
def _scrub(text: str) -> str:
    text = redact_secrets(text or '')
    try:
        from core.observability import scrub_pii

        return scrub_pii(text)
    except Exception:  # noqa: BLE001
        return text


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


#: Parts of a message that change on every occurrence of the same problem: a
#: provider's request id, a hashed or redacted value, a timestamp in a file name.
#: Left in, "Insufficient Balance (request_id: …)" became one group per day.
#: The PII scrubber hashes a run of digits inside an id as a phone number, so an
#: id with a ``<redacted:…>`` piece glued to it is the same placeholder as a uuid.
_VOLATILE = (
    (re.compile(r'[0-9a-f-]*<redacted:[0-9a-f]+>[0-9a-f-]*', re.I), '<id>'),
    (re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I), '<id>'),
    (re.compile(r'\b[0-9a-f]{12,}\b', re.I), '<hex>'),
    (re.compile(r'\d{6,}'), '<n>'),
)


def stable_text(text: str) -> str:
    """``text`` with its per-occurrence parts replaced, for fingerprinting only."""
    for pattern, placeholder in _VOLATILE:
        text = pattern.sub(placeholder, text)
    return text


def _fingerprint_client(message: str, source_url: str, lineno: int) -> str:
    """Stable hash for a JS error — message + file:line."""
    src = (source_url or '').split('/')[-1].split('?')[0]
    key = f'{stable_text(message)}|{src}:{lineno}'
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
_TRACEBACK_LIMIT = 20000


def _truncate(text: str, limit: int) -> str:
    """Cap `text` at `limit` chars with a visible marker so readers know
    they're not seeing the full thing (silently truncated tracebacks
    have caused phantom-frame goose-chases more than once)."""
    if not text or len(text) <= limit:
        return text
    return text[: limit - 40] + '\n…[truncated by core.errors]'


def _with_context(meta: dict[str, Any] | None, request=None) -> dict[str, Any]:
    """Add the request context to an event's metadata while detailed capture is on.

    Fail-soft and off by default: standard capture stores what it always did.
    """
    meta = dict(meta or {})
    try:
        from core.errors.mode import detailed_active

        if detailed_active() and 'context' not in meta:
            from core.errors.context import request_context

            meta['context'] = request_context(request)
    except Exception:  # noqa: BLE001, S110 — context is a bonus, never a reason to fail
        pass
    return meta


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

        if request is None:
            from core.errors.context import current_request

            request = current_request.get()
        extra = _with_context(extra, request)
        traceback_str = _scrub(''.join(_tb.format_exception(type(exc), exc, exc.__traceback__)))
        ErrorEvent.objects.create(
            kind=kind,
            level=level,
            fingerprint=_fingerprint_server(exc),
            exception_class=type(exc).__name__,
            message=_scrub(str(exc))[:2000],
            traceback=_truncate(traceback_str, _TRACEBACK_LIMIT),
            path=(getattr(request, 'path', '') or '')[:500],
            method=getattr(request, 'method', '') or '',
            status_code=500,
            user=getattr(request, 'user', None)
            if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False)
            else None,
            request_id=getattr(request, 'request_id', '') or '',
            user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[
                :_USER_AGENT_LIMIT
            ],
            ip_hash=_ip_hash(request),
            metadata=extra or {},
        )
    except Exception:  # noqa: BLE001 — never raise from the capture path
        logger.exception('record_error failed')


def _user_of(request):
    u = getattr(request, 'user', None)
    return u if u and getattr(u, 'is_authenticated', False) else None


def record_message(
    message: str,
    *,
    level: str = 'error',
    kind: str = 'server',
    source: str = '',
    exception_class: str = '',
    stack_trace: str = '',
    extra: dict[str, Any] | None = None,
    request=None,
) -> None:
    """Write a server-side error from a pre-formatted message/stack when there is
    no live exception object (e.g. a log record without exc_info, or a caller
    that only has strings). Callers holding an exception should use
    ``record_error`` for frame-based fingerprinting. Fail-soft.
    """
    try:
        from core.errors.models import ErrorEvent

        if request is None:
            from core.errors.context import current_request

            request = current_request.get()
        msg = _scrub(message or '')[:2000]
        # Fingerprint on source + class + message head so the same recurring
        # message dedups (mirrors the exception fingerprint's intent).
        fp_text = stable_text(msg)[:200]
        fp = hashlib.sha256(f'{source}|{exception_class}|{fp_text}'.encode()).hexdigest()[:32]
        meta = _with_context(extra, request)
        if source:
            meta.setdefault('source', source)
        ErrorEvent.objects.create(
            kind=kind,
            level=level if level in ('error', 'warning', 'info') else 'error',
            fingerprint=fp,
            exception_class=exception_class[:200],
            message=msg,
            traceback=_truncate(_scrub(stack_trace or ''), _TRACEBACK_LIMIT),
            path=(getattr(request, 'path', '') or '')[:500],
            method=getattr(request, 'method', '') or '',
            status_code=None,
            user=_user_of(request),
            request_id=getattr(request, 'request_id', '') or '',
            user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[
                :_USER_AGENT_LIMIT
            ],
            ip_hash=_ip_hash(request),
            metadata=meta,
        )
    except Exception:  # noqa: BLE001 — never raise from the capture path
        logger.exception('record_message failed')


_THROTTLE_S = 60.0
_THROTTLE_MAX = 1024
_throttle_seen: dict[str, float] = {}
_throttle_lock = threading.Lock()


def throttled(key: str) -> bool:
    """True when ``key`` was recorded in this process within the last minute.

    The same rule as the log handler: one row per fingerprint per minute, so a
    crawler walking ten thousand broken URLs cannot flood the table.
    """
    now = time.monotonic()
    with _throttle_lock:
        last = _throttle_seen.get(key)
        if last is not None and now - last < _THROTTLE_S:
            return True
        if len(_throttle_seen) >= _THROTTLE_MAX:
            _throttle_seen.clear()
        _throttle_seen[key] = now
    return False


#: What a request-level event is, for its title and its level.
HTTP_SOURCES = {
    'rejected': 'warning',  # 400, 403, 405, 429
    'broken_link': 'warning',  # a 404 reached from a page on this site
    'server_status': 'error',  # a 5xx answered without an exception
    'slow': 'warning',  # a response slower than the threshold
}


def record_http(source: str, *, request, status: int, duration_ms: int, message: str) -> None:
    """Record a request-level event (detailed capture). Throttled and fail-soft.

    The fingerprint names the source, the status and the view (or the path when
    no view resolved), so one broken link or one slow page is one group however
    often it is hit.
    """
    try:
        from core.errors.context import request_context
        from core.errors.models import ErrorEvent

        match = getattr(request, 'resolver_match', None)
        where = (getattr(match, 'view_name', '') if match else '') or request.path
        if source == 'broken_link':
            where = request.path  # every broken URL is its own fix
        key = f'http|{source}|{status}|{where}'
        if throttled(key):
            return
        context = request_context(request, status=status, duration_ms=duration_ms)
        ErrorEvent.objects.create(
            kind='server',
            level=HTTP_SOURCES.get(source, 'warning'),
            fingerprint=hashlib.sha256(key.encode()).hexdigest()[:32],
            exception_class=f'HTTP {status}' if source != 'slow' else 'SlowResponse',
            message=_scrub(message)[:2000],
            path=(request.path or '')[:500],
            method=request.method or '',
            status_code=status,
            user=_user_of(request),
            request_id=getattr(request, 'request_id', '') or '',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:_USER_AGENT_LIMIT],
            ip_hash=_ip_hash(request),
            metadata={'source': source, 'context': context},
        )
    except Exception:  # noqa: BLE001 — never raise from the capture path
        logger.exception('record_http failed')


_JS_FRAME_RE = re.compile(r'(?:https?://[^\s)]+|/[^\s)]+):(\d+)(?::\d+)?')


#: Browser noise that is not an error. A View Transition is aborted whenever a
#: navigation interrupts one still in flight; the browser reports it as an
#: unhandled rejection, and it was the most common "error" on three live stores.
_CLIENT_NOISE = (
    ('InvalidStateError', 'Transition was aborted'),
    ('AbortError', 'Skipping view transition'),  # Safari's wording of the same abort
    ('AbortError', 'Transition was skipped'),  # Chrome's, when skipTransition() runs
    # A script from another origin threw; the browser hides its message, file and
    # line, so there is nothing to act on (74 on one store, Oct 2026).
    ('Error', 'Script error.'),
)


def is_client_noise(name: str, message: str) -> bool:
    return any(name == n and message.startswith(prefix) for n, prefix in _CLIENT_NOISE)


def record_client_error(payload: dict[str, Any], *, request=None) -> None:
    """Write a JS error received from the browser. Validates payload shape."""
    from core.errors.models import ErrorEvent

    message = (payload.get('message') or '')[:2000]
    if is_client_noise((payload.get('name') or '').strip(), message):
        return
    # Console errors, failed requests and missing assets are reported only by a
    # page rendered while detailed capture was on; a page cached from then can
    # outlive the switch, so the server decides.
    detail = bool(payload.get('detail'))
    if detail:
        from core.errors.mode import detailed_active

        if not detailed_active():
            return
    source_url = (payload.get('source') or '')[:500]
    lineno = int(payload.get('lineno') or 0)
    colno = int(payload.get('colno') or 0)
    stack = _truncate(payload.get('stack') or '', _TRACEBACK_LIMIT)
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
        user=getattr(request, 'user', None)
        if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False)
        else None,
        request_id=getattr(request, 'request_id', '') or '',
        user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[
            :_USER_AGENT_LIMIT
        ],
        ip_hash=_ip_hash(request),
        metadata={
            'source_url': source_url,
            'lineno': lineno,
            'colno': colno,
            'browser': browser,
            **({'detail': True, 'source': 'browser'} if detail else {}),
        },
    )
