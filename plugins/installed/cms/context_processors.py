"""Storefront context processors for the cms plugin.

Exposes the merchant-editable ``header`` and ``mobile`` navigation menus
(``cms.Menu``) so the active theme renders its nav + hamburger drawer from the
database instead of hardcoded markup. Cached briefly and fail-soft: a DB hiccup
or a disabled cms plugin yields ``None``, and the theme falls back to its
built-in default nav.
"""

from __future__ import annotations

_CACHE_TTL = 300
_KEYS = ('header', 'mobile')


def nav_menus(request):
    from django.core.cache import cache  # noqa: PLC0415

    out: dict = {}
    for key in _KEYS:
        ckey = f'storefront:nav_menu:{key}:v1'
        cached = cache.get(ckey)
        if cached is None:
            try:
                from plugins.installed.cms.services import get_menu  # noqa: PLC0415

                cached = get_menu(key) or {}
            except Exception:  # noqa: BLE001 — nav must never break a render
                cached = {}
            cache.set(ckey, cached, _CACHE_TTL)
        out[f'{key}_menu'] = cached or None
    return out
