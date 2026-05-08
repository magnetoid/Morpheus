"""Middleware: stash the resolved market on `request` for view code."""
from __future__ import annotations


class MarketMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from plugins.installed.markets.services import resolve_market
            request.market = resolve_market(request)
        except Exception:  # noqa: BLE001
            request.market = None
        return self.get_response(request)
