"""Middleware: stash the resolved market on `request` for view code.

Also stamps `Content-Language` on every response: the language the page is
served in. `LocaleMiddleware` activates it from the URL (`/sr/…`) and forces the
core language on unprefixed routes, so `get_language()` is the page's language.
The market's own locale is used only when it names that same language, for its
region (`en-US`). The header used to come from the market or `LANGUAGE_CODE`
alone, so every `/sr/` page said `Content-Language: en`.
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
            locale = _content_language(market)
            if locale:
                response['Content-Language'] = locale
        return response


def _content_language(market) -> str:
    """The active language, as the market writes it when the market speaks it."""
    from django.conf import settings
    from django.utils import translation

    # Django stores en_US; the header wants en-US.
    language = (translation.get_language() or settings.LANGUAGE_CODE or '').strip()
    language = language.replace('_', '-')
    market_locale = ((getattr(market, 'default_locale', '') if market else '') or '').strip()
    market_locale = market_locale.replace('_', '-')
    if market_locale and market_locale.split('-')[0].lower() == language.split('-')[0].lower():
        return market_locale
    return language
