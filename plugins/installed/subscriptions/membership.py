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

#: States that MAY entitle. A state alone is NOT proof of payment — see
#: :func:`entitling_subscriptions`. 'pending' (where a paid signup waits for
#: Stripe to confirm the money moved) is deliberately absent, as are
#: past_due / paused / cancelled / expired.
_ENTITLING_STATES = ('active', 'trialing')


def entitling_subscriptions(customer):
    """The customer's subscriptions that actually entitle them to member perks.

    THE single definition of "is a paying member" — the cart discount and every
    other perk surface read it, so the rule cannot drift between surfaces.

    **An entitling state is not enough; there must be evidence the plan was paid
    for.** Until v0.40 the storefront subscribe view wrote ``state='active'``
    with no payment leg at all, so any logged-in customer could POST
    ``/membership/subscribe/`` and take the member discount off every order
    forever, having paid nothing. Checking for payment evidence (rather than
    trusting the state string) also de-entitles those already-minted rows
    without a data migration, and means the next code path that writes
    'active' cannot silently reopen the hole.

    Evidence, cheapest check first:
      * the plan is free — there was nothing to pay;
      * a provider subscription exists — Stripe holds a verified card and owns
        the dunning ladder;
      * a paid invoice is on file — offline billing the merchant recorded.
    """
    from django.db.models import Q

    from plugins.installed.subscriptions.models import Subscription, SubscriptionInvoice

    paid_evidence = (
        Q(plan__price__lte=Decimal('0'))
        | ~Q(provider_subscription_id='')
        | Q(pk__in=SubscriptionInvoice.objects.filter(state='paid').values('subscription_id'))
    )
    return Subscription.objects.filter(customer=customer, state__in=_ENTITLING_STATES).filter(
        paid_evidence
    )


def member_discount_percent(customer) -> int:
    """Best member discount (%) across a customer's entitling subscriptions."""
    if customer is None or not getattr(customer, 'is_authenticated', False):
        return 0
    best = entitling_subscriptions(customer).values_list('plan__member_discount_percent', flat=True)
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
