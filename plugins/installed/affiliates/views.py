"""Storefront-side affiliate redirect: /r/<code> -> set cookie + redirect."""
from __future__ import annotations

from morpheus.views import HttpRequest, HttpResponseRedirect

_AFFILIATE_COOKIE = 'morph_aff'
_COOKIE_TTL = 60 * 60 * 24 * 30  # 30 days; programs may override via cookie_window_days


def affiliate_redirect(request: HttpRequest, code: str) -> HttpResponseRedirect:
    from plugins.installed.affiliates.services import record_click

    referer = request.headers.get('Referer', '')
    user_agent = request.headers.get('User-Agent', '')
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()

    link = record_click(code=code, referer=referer, user_agent=user_agent, ip=ip)
    landing = link.landing_url if link else '/'

    response = HttpResponseRedirect(landing)
    response.set_cookie(
        _AFFILIATE_COOKIE,
        code,
        max_age=_COOKIE_TTL,
        httponly=True,
        samesite='Lax',
    )
    return response
