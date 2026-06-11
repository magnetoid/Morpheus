"""Storefront Cache-Control middleware.

Reads the Caching settings page knobs from the storefront plugin's
PluginConfig and emits the appropriate `Cache-Control` header on
storefront responses. Per-route TTL overrides apply when the URL
matches a known pattern (home / product / category / search) —
otherwise the base `html_cache_control` setting wins.

Skips:
  - Admin/dashboard paths (`/dashboard/`, `/admin/`, `/auth/`,
    `/api/`, `/graphql/`)
  - Authenticated requests (cookies + Authorization both checked)
  - Responses that already set Cache-Control upstream
  - Non-2xx responses
  - Non-GET / HEAD requests
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger('morpheus.core.storefront_cache')


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
        # logged-in are already bucketed by the
        # StorefrontCacheControlMiddleware cookie-presence skip, and
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
            from plugins.registry import plugin_registry

            p = plugin_registry.get('storefront')
            if p is None:
                return {}
            return p.get_config() or {}
        except Exception:  # noqa: BLE001
            return {}
