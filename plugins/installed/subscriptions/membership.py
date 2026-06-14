"""Membership perks — the subscriber book/cart discount.

A confirmed active subscriber gets the best `member_discount_percent` of their
active plans off the cart. Applied at checkout via the live
CART_CALCULATE_BREAKDOWN filter (the per-product price filter is a dead hook),
so it composes with coupons/tax/shipping and the customer is known.
"""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger('morpheus.subscriptions.membership')

_ACTIVE_STATES = ('active', 'trialing')


def member_discount_percent(customer) -> int:
    """Best member discount (%) for a customer's active subscriptions. 0 if none."""
    if customer is None or not getattr(customer, 'is_authenticated', False):
        return 0
    from plugins.installed.subscriptions.models import Subscription

    best = (
        Subscription.objects.filter(customer=customer, state__in=_ACTIVE_STATES)
        .select_related('plan')
        .values_list('plan__member_discount_percent', flat=True)
    )
    return min(100, max((p or 0 for p in best), default=0))


def apply_member_discount(value, *, cart=None, customer=None, **_kwargs):
    """CART_CALCULATE_BREAKDOWN subscriber — add the member discount to the cart.

    Adds to the existing `discount` and recomputes `total` so it stacks cleanly
    with a coupon. Fail-soft: returns the breakdown unchanged on any problem."""
    if not isinstance(value, dict):
        return value
    try:
        who = customer if customer is not None else getattr(cart, 'customer', None)
        pct = member_discount_percent(who)
        if pct <= 0:
            return value

        from djmoney.money import Money

        subtotal = value.get('subtotal')
        if not isinstance(subtotal, Money):
            return value
        currency = str(subtotal.currency)
        member_off = Money(
            (Decimal(subtotal.amount) * Decimal(pct) / Decimal(100)).quantize(Decimal('0.01')),
            currency,
        )

        existing_discount = value.get('discount')
        existing_discount = (
            existing_discount
            if isinstance(existing_discount, Money)
            else Money(Decimal('0'), currency)
        )
        shipping = (
            value.get('shipping')
            if isinstance(value.get('shipping'), Money)
            else Money(Decimal('0'), currency)
        )
        tax = (
            value.get('tax')
            if isinstance(value.get('tax'), Money)
            else Money(Decimal('0'), currency)
        )

        new_discount = existing_discount + member_off
        value['discount'] = new_discount
        value['total'] = subtotal - new_discount + shipping + tax
        meta = dict(value.get('meta') or {})
        meta['member_discount_percent'] = pct
        meta['member_discount'] = str(member_off)
        value['meta'] = meta
        return value
    except Exception as e:  # noqa: BLE001 — pricing must never crash the cart
        logger.warning('membership: apply_member_discount failed: %s', e, exc_info=True)
        return value
