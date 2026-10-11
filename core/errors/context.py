"""Request context for detailed capture: what a fixer needs, never a secret.

``ErrorCaptureMiddleware`` puts the current request in a context variable, so an
event recorded deep inside a view, a hook or a log call still knows the request
it happened in. ``request_context()`` turns that request into a small dict.

Kept: method, path, view name and route, query parameter names (values only for
harmless keys), a same-site referer path (another site's host only), language,
user id and staff flag, store version, active theme. Never kept: cookies,
headers beyond these, request bodies, secret-looking query values.
"""

from __future__ import annotations

import contextvars
from typing import Any
from urllib.parse import urlparse

current_request: contextvars.ContextVar = contextvars.ContextVar(
    'morph_errors_request', default=None
)

#: Query parameters whose values are useful and harmless.
_SAFE_QUERY_KEYS = frozenset(
    {
        'page', 'sort', 'q', 'category', 'tag', 'collection', 'genre', 'topic', 'lang',
        'view', 'tab', 'status', 'kind', 'format', 'per_page', 'price_min', 'price_max',
        'utm_source', 'utm_medium', 'utm_campaign', 'ref', 'next',
    }
)  # fmt: skip
_MAX_QUERY_KEYS = 20


def _query(request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in list(getattr(request, 'GET', {}).keys())[:_MAX_QUERY_KEYS]:
        safe = key in _SAFE_QUERY_KEYS or key.startswith('attr_')
        out[key[:60]] = (request.GET.get(key) or '')[:80] if safe else '[redacted]'
    return out


def _referer(request) -> str:
    raw = request.META.get('HTTP_REFERER', '') or ''
    if not raw:
        return ''
    try:
        ref = urlparse(raw)
        host = (request.get_host() or '').split(':')[0].lower()
    except Exception:  # noqa: BLE001 — DisallowedHost and friends
        return ''
    ref_host = (ref.hostname or '').lower()
    if ref_host and ref_host == host:
        return (ref.path or '/')[:300]
    return ref_host[:120]


def is_same_site_referer(request) -> bool:
    ref = _referer(request)
    return ref.startswith('/')


def _theme() -> str:
    try:
        from themes.registry import theme_registry

        return getattr(theme_registry, '_active_name', '') or ''
    except Exception:  # noqa: BLE001
        return ''


def request_context(request=None, **extra: Any) -> dict[str, Any]:
    """The request an event happened in, as a small JSON-safe dict."""
    from django.conf import settings

    request = request if request is not None else current_request.get()
    ctx: dict[str, Any] = {
        'version': getattr(settings, 'MORPHEUS_VERSION', ''),
        'theme': _theme(),
    }
    if request is not None:
        match = getattr(request, 'resolver_match', None)
        user = getattr(request, 'user', None)
        authed = bool(user is not None and getattr(user, 'is_authenticated', False))
        ctx.update(
            {
                'method': getattr(request, 'method', '') or '',
                'path': (getattr(request, 'path', '') or '')[:500],
                'view': (getattr(match, 'view_name', '') or '')[:200] if match else '',
                'route': (getattr(match, 'route', '') or '')[:200] if match else '',
                'query': _query(request),
                'referer': _referer(request),
                'language': getattr(request, 'LANGUAGE_CODE', '') or '',
                'user_id': str(user.pk) if authed else '',
                'is_staff': bool(authed and getattr(user, 'is_staff', False)),
            }
        )
    ctx.update({k: v for k, v in extra.items() if v not in (None, '')})
    return ctx
