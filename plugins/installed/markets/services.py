"""Helpers for resolving the active Market and applying price overrides."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger('morpheus.markets')


def _country_from_request(request) -> str:
    """Pick the visitor's country code.

    Priority: explicit `?country=XX` (debugging) → Cloudflare's
    `CF-IPCountry` header → empty string (caller treats as 'unknown').
    Always uppercased.
    """
    if request is None:
        return ''
    explicit = (request.GET.get('country') or '').strip().upper()
    if explicit:
        return explicit
    cf = (request.META.get('HTTP_CF_IPCOUNTRY') or '').strip().upper()
    if cf and cf not in ('XX', 'T1'):  # T1 = Tor, XX = unknown
        return cf
    return ''


def resolve_market(request) -> 'Market | None':  # noqa: F821
    """Pick the active market for the request. ``None`` if markets
    isn't configured yet."""
    try:
        from plugins.installed.markets.models import Market
    except Exception:  # noqa: BLE001
        return None

    explicit = (request.GET.get('market') or '').strip().lower() if request else ''
    if explicit:
        m = Market.objects.filter(code=explicit, is_active=True).first()
        if m is not None:
            return m

    country = _country_from_request(request)
    if country:
        # No DB-side JSON containment so we filter in Python — list of
        # active markets is small (single-digit / low-tens).
        for m in Market.objects.filter(is_active=True):
            if country in m.country_set:
                return m

    return Market.objects.filter(is_active=True, is_default=True).first()


def price_for(*, product, market) -> Any:
    """Return the Money price of `product` in `market`.

    Resolution order:
      1. ProductMarketPrice override row, if one exists for this pair.
      2. Channel base price * (1 + market.base_price_adjustment_pct/100).
      3. Bare `product.price` (currency unchanged) if no market.
    """
    if market is None:
        return getattr(product, 'price', None)
    try:
        from djmoney.money import Money
        from plugins.installed.markets.models import ProductMarketPrice
        override = ProductMarketPrice.objects.filter(
            product=product, market=market, is_visible=True,
        ).first()
        if override is not None:
            return override.price
        base = getattr(product, 'price', None)
        if base is None:
            return None
        adj = market.base_price_adjustment_pct or Decimal('0')
        if adj == 0:
            # Re-quote in market currency without changing amount.
            if str(base.currency) != market.currency:
                return Money(base.amount, market.currency)
            return base
        amount = Decimal(base.amount) * (Decimal('100') + Decimal(adj)) / Decimal('100')
        amount = amount.quantize(Decimal('0.01'))
        return Money(amount, market.currency)
    except Exception as e:  # noqa: BLE001
        logger.debug('price_for failed: %s', e)
        return getattr(product, 'price', None)


def market_context(request) -> dict:
    """Used as a Django context processor — adds `active_market` and a
    light-weight `market_currency` to every storefront template.

    Wrapped in a broad except so that a missing table or any other
    transient DB issue can't take the entire storefront down via a
    failing context processor. Returns blank values on error.
    """
    try:
        m = resolve_market(request)
    except Exception as e:  # noqa: BLE001
        logger.debug('market_context: resolve_market failed: %s', e)
        m = None
    return {
        'active_market': m,
        'market_currency': m.currency if m is not None else '',
        'market_locale': m.default_locale if m is not None else '',
    }
