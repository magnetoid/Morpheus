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
