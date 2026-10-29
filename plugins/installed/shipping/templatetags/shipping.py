"""Storefront template tags for the shipping plugin.

`{% load shipping %}` exposes ``free_shipping_progress`` — the data behind the
cart's "add X for free shipping" progress bar. Kept as a tag (not a context
processor) so the query only runs on the cart page where the block renders.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def free_shipping_progress(subtotal):
    """Progress toward the lowest active free-shipping threshold.

    Returns ``{threshold, remaining, pct, qualified}`` for the cart progress
    bar, or ``None`` when no ``free_over`` rate is configured (the block then
    self-hides). Compares raw amounts, mirroring the ``free_over`` logic in
    ``shipping/services.py`` so the bar can never promise free shipping the
    checkout won't honour.
    """
    if subtotal is None:
        return None

    from djmoney.money import Money

    from plugins.installed.shipping.models import ShippingRate

    rate = (
        ShippingRate.objects.filter(
            computation='free_over', is_active=True, free_threshold__isnull=False
        )
        .order_by('free_threshold')
        .first()
    )
    if rate is None or not rate.free_threshold:
        return None

    threshold = rate.free_threshold
    sub_amt = getattr(subtotal, 'amount', subtotal)
    thr_amt = threshold.amount
    qualified = sub_amt >= thr_amt
    remaining_amt = thr_amt - sub_amt if thr_amt > sub_amt else 0
    pct = 100 if qualified or thr_amt <= 0 else min(100, int(sub_amt / thr_amt * 100))
    return {
        'threshold': threshold,
        'remaining': Money(remaining_amt, threshold.currency),
        'pct': pct,
        'qualified': qualified,
    }


@register.simple_tag
def shipping_rate_cards() -> list[dict]:
    """The active rates, by zone, for the store's shipping page.

    Each card says what checkout charges and nothing more: ``kind`` is
    ``flat`` (``price``), ``from`` (the lowest tier, ``price``) or ``live``
    (a carrier quotes at checkout); ``free_over`` is set for a free-over
    rate, whose ``price`` applies below the threshold. Empty when no rate is
    configured, so a page can never list a rate checkout does not offer.
    """
    from django.conf import settings
    from djmoney.money import Money

    from plugins.installed.shipping.models import ShippingRate

    store_currency = str(getattr(settings, 'STORE_CURRENCY', '') or 'USD').upper()
    cards = []
    for rate in ShippingRate.objects.filter(is_active=True).select_related('zone'):
        card = {
            'zone': rate.zone.name,
            'name': rate.name,
            'description': rate.description,
            'kind': 'flat',
            'price': rate.flat_amount,
            'free_over': None,
            'days_min': rate.estimated_days_min,
            'days_max': rate.estimated_days_max,
        }
        if rate.computation == 'free_over' and rate.free_threshold:
            # Below the threshold it costs `price`; without one, free only above.
            card['free_over'] = rate.free_threshold
        elif rate.computation in ('order_total_tier', 'weight_tier'):
            amounts = [t.get('amount') for t in rate.tiers or [] if t.get('amount') is not None]
            # Checkout prices a tier in the cart's currency, which is the store's.
            currency = rate.flat_amount.currency if rate.flat_amount else store_currency
            if amounts:
                card.update(kind='from', price=Money(min(amounts, key=float), currency))
            else:
                card.update(kind='live', price=None)
        elif rate.computation.startswith('carrier_'):
            card.update(kind='live', price=None)
        elif rate.flat_amount is None:
            continue  # checkout cannot quote a flat rate with no amount
        cards.append(card)
    return cards
