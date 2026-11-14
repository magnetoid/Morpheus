"""The ``PRODUCT_CALCULATE_PRICE`` seam — one guarded way to apply it.

Two subscribers shipped against this filter (ai_assistant's AI dynamic pricing,
functions' merchant pricing rules) and **nothing ever fired it**, so every
pricing rule a merchant wrote was silently inert until v0.38.

It is fired from exactly two places, and they must agree or the shopper sees one
price and is charged another:

* ``catalog`` — the displayed price (GraphQL ``Product.price``)
* ``orders``  — the charged price (``_resolve_unit_price`` at cart-add)

Both go through :func:`apply_price_filter` so the validation can't drift apart.
Lives in core because the hook contract is core's; a shared helper in either
plugin would be a plugin→plugin import.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from djmoney.money import Money

logger = logging.getLogger('morpheus.pricing')


def apply_price_filter(price: Money, *, product=None, customer=None) -> Money:
    """Run ``PRODUCT_CALCULATE_PRICE`` over ``price`` and validate the result.

    Fail-soft in every direction — a broken or hostile pricing rule must never
    break a product page or a cart-add, so anything unexpected keeps the
    original price:

    * a non-``Money`` return (a handler that forgot to return ``value``),
    * a negative price,
    * a currency swap, which would breach the single-currency cart invariant
      that ``CartService.add_item`` enforces.
    """
    if not isinstance(price, Money):
        return price
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        adjusted = hook_registry.filter(
            MorpheusEvents.PRODUCT_CALCULATE_PRICE,
            value=price,
            product=product,
            customer=customer,
        )
    except Exception:  # noqa: BLE001 — pricing rules never break the page
        logger.warning('PRODUCT_CALCULATE_PRICE filter failed', exc_info=True)
        return price

    if not isinstance(adjusted, Money):
        logger.warning('PRODUCT_CALCULATE_PRICE returned %r (not Money) — ignoring', adjusted)
        return price
    if adjusted.amount < 0:
        logger.warning('PRODUCT_CALCULATE_PRICE returned negative %s — ignoring', adjusted)
        return price
    if str(adjusted.currency) != str(price.currency):
        logger.warning(
            'PRODUCT_CALCULATE_PRICE changed currency %s->%s — ignoring',
            price.currency,
            adjusted.currency,
        )
        return price
    return adjusted


def store_currency() -> str:
    """The currency the catalogue is priced in."""
    return str(getattr(settings, 'STORE_CURRENCY', 'USD') or 'USD').upper()


def quantize(amount: Decimal, currency: str) -> Decimal:
    """``amount`` rounded half up to ``currency``'s minor unit (JPY has none)."""
    from babel.numbers import get_currency_precision

    try:
        digits = get_currency_precision((currency or '').upper())
    except Exception:  # noqa: BLE001 — an unknown code is priced in cents
        digits = 2
    return Decimal(amount).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def _pair(base: str, quote: str) -> Decimal | None:
    """One stored rate, direct or inverted; ``None`` when neither row exists."""
    from core.models import ExchangeRate

    row = ExchangeRate.objects.filter(base_currency=base, quote_currency=quote).first()
    if row is not None and row.rate:
        return Decimal(row.rate)
    row = ExchangeRate.objects.filter(base_currency=quote, quote_currency=base).first()
    if row is not None and row.rate:
        return Decimal(1) / Decimal(row.rate)
    return None


def exchange_rate(base: str, quote: str) -> Decimal | None:
    """How many ``quote`` one ``base`` buys: the stored pair, its inverse, or the
    two legs through the store currency; 1 for the same currency, else ``None``."""
    base, quote = (base or '').upper(), (quote or '').upper()
    if base == quote:
        return Decimal(1)
    rate = _pair(base, quote)
    if rate is not None:
        return rate
    store = store_currency()
    if store in (base, quote):
        return None
    first, second = _pair(base, store), _pair(store, quote)
    if first is None or second is None:
        return None
    return first * second


def convert(money: Money, currency: str) -> Money | None:
    """``money`` in ``currency`` at the stored rate, or ``None`` without one."""
    currency = (currency or '').upper()
    rate = exchange_rate(str(money.currency), currency)
    if rate is None:
        return None
    return Money(quantize(Decimal(money.amount) * rate, currency), currency)
