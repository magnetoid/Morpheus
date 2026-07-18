"""Template tags for the loyalty cart-redeem widget.

``{% loyalty_redeem_state %}`` returns the current shopper's redeem state
(balance, what it's worth, and any pending spend read off the cart) or
``None`` — guests and zero-balance customers get nothing, so the widget
self-hides. Fail-soft: any error returns ``None`` rather than break the cart.
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def loyalty_redeem_state(context):
    request = context.get('request')
    user = getattr(request, 'user', None) if request is not None else None
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from plugins.installed.loyalty_points.services import get_balance
        from plugins.installed.loyalty_points.services_redeem import points_to_amount

        balance = get_balance(user)
        if balance <= 0:
            return None
        cart = context.get('cart')
        applied = int((getattr(cart, 'metadata', None) or {}).get('loyalty_points_redeem') or 0)
        return {
            'balance': balance,
            'worth': points_to_amount(balance),
            'applied': applied,
            'applied_worth': points_to_amount(applied) if applied else None,
            # max_redeemable(user) with no order total == the balance we already
            # have — reuse it instead of a second get_balance aggregate. The
            # order-total cap is applied later by on_cart_breakdown.
            'max': balance,
        }
    except Exception:  # noqa: BLE001 — a widget must never break the cart page
        return None
