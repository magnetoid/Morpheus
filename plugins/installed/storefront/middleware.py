"""Storefront HTTP cache headers.

Sets ``Cache-Control`` so Cloudflare (and any sane CDN) can aggressively
cache catalog pages while still allowing fast refresh on product
updates. Without these headers the edge can't cache at all, so every
PDP/PLP hit travels all the way to the origin web container.

Strategy:
  - ``GET /`` / ``GET /products/`` / ``GET /products/<slug>/`` /
    ``GET /category/<slug>/`` / ``GET /journal/`` / ``GET /journal/<slug>/``
    →  ``public, s-maxage=60, stale-while-revalidate=300``
  - Anything authenticated / mutating / cart-bearing →  skipped (the
    middleware bails out the moment it sees a sessionid cookie or a
    cart_token cookie).
  - The middleware never overrides a header the view already set
    (Django views can opt out by setting Cache-Control themselves).

This is intentionally conservative. 60 seconds at the edge means a
product update propagates within ~60s without any explicit purge, and
during a flash sale the origin is shielded.
"""
from __future__ import annotations

import re

# Storefront paths that are safe to cache at the CDN edge.
# Anything that requires per-user data (cart, account, checkout) stays
# out of this set.
_CACHEABLE_PATTERNS = (
    re.compile(r'^/$'),
    re.compile(r'^/products/?$'),
    re.compile(r'^/products/[^/]+/?$'),
    re.compile(r'^/category/[^/]+/?$'),
    re.compile(r'^/c/[^/]+/?$'),
    re.compile(r'^/journal/?$'),
    re.compile(r'^/journal/[^/]+/?$'),
    re.compile(r'^/staff-picks/?$'),
    re.compile(r'^/about/?$'),
    re.compile(r'^/p/[^/]+/?$'),         # CMS pages
    re.compile(r'^/authors?/[^/]*/?$'),
)

# Cookies whose presence signals a per-user request → don't edge-cache.
_PRIVATE_COOKIES = ('sessionid', 'csrftoken', 'cart_token', 'morpheus_session')

_CACHE_VALUE = 'public, s-maxage=60, stale-while-revalidate=300'


def _is_cacheable_path(path: str) -> bool:
    return any(p.match(path) for p in _CACHEABLE_PATTERNS)


class StorefrontCacheControlMiddleware:
    """Add public-edge Cache-Control to safe storefront GETs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Bail conditions:
        if request.method != 'GET':
            return response
        if response.status_code != 200:
            return response
        if response.has_header('Cache-Control'):
            # View already declared a policy — respect it.
            return response
        if any(c in request.COOKIES for c in _PRIVATE_COOKIES):
            return response
        if not _is_cacheable_path(request.path):
            return response

        response['Cache-Control'] = _CACHE_VALUE
        # Vary on Accept-Encoding (so Brotli vs gzip get separate cache
        # entries) and Accept-Language (themes can localise). Cookie
        # is intentionally NOT in Vary — we already filtered users out
        # by cookie presence above; varying on Cookie would explode the
        # cache key with junk like _ga.
        existing_vary = response.get('Vary', '')
        new_vary = 'Accept-Encoding, Accept-Language'
        response['Vary'] = f'{existing_vary}, {new_vary}'.strip(', ') if existing_vary else new_vary
        return response
