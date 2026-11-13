"""One answer to "what does this product cost in this market?"."""

from __future__ import annotations

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation

from babel.numbers import get_currency_precision
from djmoney.money import Money

from core.pricing import apply_price_filter, exchange_rate, quantize, store_currency


def _store_price(product, variant) -> Money | None:
    price = variant.effective_price if variant is not None else product.price
    return price if isinstance(price, Money) else None


def _typed_price(prices, currency: str) -> Decimal | None:
    """A ``localized_prices`` entry that is a real price: a number above zero.

    ``0`` means "not entered" (Supernatural has three of them), never free.
    """
    if not isinstance(prices, dict):
        return None
    raw = prices.get(currency)
    if raw is None:
        return None
    try:
        amount = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def _round(amount: Decimal, currency: str, rounding: str) -> Decimal:
    if rounding == 'whole':
        # Never let a cheap item round down to free.
        whole = amount.quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return whole if whole > 0 or amount <= 0 else Decimal(1)
    if rounding == 'ninety_nine':
        base = amount.quantize(Decimal(1), rounding=ROUND_FLOOR)
        if get_currency_precision(currency) == 0:
            return base  # a currency without cents has no .99
        return base + Decimal('0.99')
    return quantize(amount, currency)


def market_price(product, market, variant=None) -> Money | None:
    """The price of ``product`` (or one of its variants) in ``market``'s currency.

    In order: the store price when the market uses the store currency; a price
    the merchant fixed for the market; one typed in the product's
    ``localized_prices``; else the store price, adjusted by the market's
    percentage, converted at the stored rate and rounded as the market says.
    ``None`` when there is no rate.
    """
    store_price = _store_price(product, variant)
    if store_price is None:
        return None
    store_price = apply_price_filter(store_price, product=product, customer=None)
    currency = market.currency.upper()
    if currency == store_currency():
        return store_price

    from plugins.installed.markets.models import ProductMarketPrice

    fixed = ProductMarketPrice.objects.filter(market=market, product=product).first()
    if fixed is not None:
        return apply_price_filter(
            Money(fixed.price.amount, currency), product=product, customer=None
        )

    for holder in (variant, product):
        amount = _typed_price(getattr(holder, 'localized_prices', None), currency)
        if amount is not None:
            return apply_price_filter(
                Money(quantize(amount, currency), currency), product=product, customer=None
            )

    rate = exchange_rate(str(store_price.currency), currency)
    if rate is None:
        return None
    adjustment = Decimal(market.base_price_adjustment_pct or 0)
    exact = Decimal(store_price.amount) * (Decimal(100) + adjustment) / Decimal(100) * rate
    return Money(_round(exact, currency, market.rounding), currency)
