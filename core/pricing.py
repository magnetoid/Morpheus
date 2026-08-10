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
