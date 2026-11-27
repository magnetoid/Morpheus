"""Storefront Cache-Control middleware.

Reads the Caching settings page knobs from the storefront plugin's
PluginConfig and emits the appropriate `Cache-Control` header on
storefront responses. Per-route TTL overrides apply when the URL
matches a known pattern (home / product / category / search) —
otherwise the base `html_cache_control` setting wins.

A page rendered with something meant for one visitor alone (tracking's
conversion queued for their browser's tag) calls ``keep_private(request)``;
this layer and the storefront app's both then answer
``Cache-Control: private, no-store``, whatever the merchant's knobs say.

Skips:
  - Admin/dashboard paths (`/dashboard/`, `/admin/`, `/auth/`,
    `/api/`, `/graphql/`)
  - Authenticated requests (Authorization header or a signed-in user)
  - A page that is one visitor's (``may_be_public``: a private cookie, or a
    cart, checkout, order or account page), the rule the storefront app's
    middleware reads too
  - Responses that already set Cache-Control upstream
  - Non-2xx responses
  - Non-GET / HEAD requests
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.i18n_links import split_language_prefix

logger = logging.getLogger('morpheus.core.storefront_cache')

#: What a page meant for one visitor answers (``keep_private``).
PRIVATE_VALUE = 'private, no-store'
_PRIVATE_FLAG = '_morph_keep_private'


def keep_private(request) -> None:
    """Mark this request's response as one visitor's: no shared cache may store it."""
    if request is not None:
        setattr(request, _PRIVATE_FLAG, True)


def is_private(request) -> bool:
    """Did anything rendering this response call ``keep_private``?"""
    return bool(getattr(request, _PRIVATE_FLAG, False))


#: Cookies that make a page the visitor's own: a session, a cart, a consent
#: choice (the banner goes and the analytics tags load). Not `csrftoken`: Django
#: sets it on a first GET, and a token is per form, not per visitor.
PRIVATE_COOKIES = ('sessionid', 'cart_token', 'morpheus_session', 'morpheus_consent')

#: Pages that are one visitor's whoever asks (after any language prefix): an
#: edge copy of an empty cart would be served to every visitor with a cart.
PRIVATE_PATH_PREFIXES = (
    '/cart/',
    '/checkout/',
    '/order/',
    '/account/',
    '/pay/',
    '/digital/',
    '/wishlist/',
    '/withdraw/',
    '/returns/start/',
)


def may_be_public(request) -> bool:
    """Whether a shared cache may keep this request's page.

    Both cache layers ask, so neither marks public a page the other keeps
    private.
    """
    if any(name in request.COOKIES for name in PRIVATE_COOKIES):
        return False
    _, path = split_language_prefix(request.path or '')
    return not path.startswith(PRIVATE_PATH_PREFIXES)


# URL patterns → TTL config key. First match wins.
_ROUTE_TTL_PATTERNS = [
    (re.compile(r'^/$'), 'home_cache_ttl'),
    (re.compile(r'^/p/[^/]+/?$'), 'product_cache_ttl'),
    (re.compile(r'^/products/[^/]+/?$'), 'product_cache_ttl'),
    (re.compile(r'^/c/[^/]+/?$'), 'category_cache_ttl'),
    (re.compile(r'^/category/[^/]+/?$'), 'category_cache_ttl'),
    (re.compile(r'^/categories/?$'), 'category_cache_ttl'),
    (re.compile(r'^/search/?$'), 'search_cache_ttl'),
]

# Bail-out path prefixes — never touch Cache-Control here.
_SKIP_PREFIXES = (
    '/dashboard/',
    '/admin/',
    '/auth/',
    '/api/',
    '/graphql/',
    '/static/',
    '/media/',
    '/_health',
    '/healthz',
)


class StorefrontCacheMiddleware:
    """Apply the merchant-configured Cache-Control to anonymous
    storefront responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_set_header(request, response)
        except Exception as e:  # noqa: BLE001 — never break a response over a header bug
            logger.debug('storefront_cache: header set failed: %s', e)
        return response

    def _maybe_set_header(self, request, response) -> None:  # noqa: PLR0911, PLR0912
        if is_private(request):
            response['Cache-Control'] = PRIVATE_VALUE
            return
        if request.method not in ('GET', 'HEAD'):
            return
        if 200 <= response.status_code < 300:
            pass
        else:
            return
        path = request.path or ''
        if path.startswith(_SKIP_PREFIXES):
            return
        # Authenticated → never cache (would leak per-user state).
        if request.META.get('HTTP_AUTHORIZATION'):
            return
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return
        if not may_be_public(request):
            return
        # Already set explicitly upstream? Respect it.
        if response.get('Cache-Control'):
            return

        cfg = self._storefront_config()
        if not cfg:
            return

        base_header = (cfg.get('html_cache_control') or '').strip()
        if not base_header:
            return

        # Per-route TTL override — replace s-maxage=<N> in the base
        # header with the route-specific value. Only when a route
        # match exists AND the route TTL > 0.
        route_ttl = self._route_ttl(path, cfg)
        if route_ttl > 0:
            header = re.sub(
                r's-maxage=\d+',
                f's-maxage={route_ttl}',
                base_header,
            )
            # If base header had no s-maxage at all, prepend one.
            if 's-maxage=' not in header:
                header = f'{header.rstrip(", ")}, s-maxage={route_ttl}'
        else:
            header = base_header

        response['Cache-Control'] = header
        # Vary on Accept-Encoding so cached bytes match the client's
        # compression support. Intentionally NOT Vary: Cookie — anon vs
        # logged-in are already bucketed by the private-cookie skip
        # (may_be_public), and
        # Vary: Cookie would explode the edge cache key on _ga / _fbp /
        # csrftoken (effective Cloudflare hit ratio ~0%).
        existing_vary = response.get('Vary', '')
        for v in ('Accept-Encoding',):
            if v.lower() not in existing_vary.lower():
                existing_vary = (existing_vary + ', ' + v).lstrip(', ')
        response['Vary'] = existing_vary

    @staticmethod
    def _route_ttl(path: str, cfg: dict[str, Any]) -> int:
        for pattern, key in _ROUTE_TTL_PATTERNS:
            if pattern.match(path):
                try:
                    return int(cfg.get(key) or 0)
                except (TypeError, ValueError):
                    return 0
        return 0

    @staticmethod
    def _storefront_config() -> dict[str, Any]:
        """Read storefront PluginConfig — cached cheaply by the registry."""
        try:
            from plugins.registry import app_registry

            p = app_registry.get('storefront')
            if p is None:
                return {}
            return p.get_config() or {}
        except Exception:  # noqa: BLE001
            return {}
