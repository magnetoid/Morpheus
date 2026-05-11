"""Middleware: stash the resolved market on `request` for view code.

Also stamps `Content-Language` on every response based on the resolved
market's `default_locale`. This is the SEO signal search engines use
to match the page to a regional SERP — without it Google falls back
to URL/IP guessing.
"""
from __future__ import annotations


class MarketMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        market = None
        try:
            from plugins.installed.markets.services import resolve_market
            market = resolve_market(request)
        except Exception:  # noqa: BLE001
            market = None
        request.market = market

        response = self.get_response(request)

        if not response.has_header('Content-Language'):
            locale = (getattr(market, 'default_locale', '') if market else '') or ''
            if not locale:
                from django.conf import settings
                locale = getattr(settings, 'LANGUAGE_CODE', '') or ''
            locale = locale.strip()
            if locale:
                # Django stores en_US; the header wants en-US.
                response['Content-Language'] = locale.replace('_', '-')
        return response
