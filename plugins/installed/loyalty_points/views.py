"""Customer-facing loyalty surfaces.

``account_points`` is the read-only ``/account/points/`` page: balance,
what it's worth today, and the recent ledger. Login-gated like every
other account page. Moved here from storefront so the route + template
live with the plugin (modular-os: disable the plugin → the route 404s).
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry is
# ready and mirror the storefront account views it was moved from.
from __future__ import annotations

import logging

from morpheus.app.views import redirect, render

logger = logging.getLogger('morpheus.loyalty')


def account_points(request):
    """Loyalty points: balance, what it's worth today, and recent ledger.

    Read-only customer surface for redemption v1. The actual
    point→discount application happens at checkout via the loyalty
    breakdown hook; this page shows the shopper what they have and what it
    can buy. Login-gated like every other account page.
    """
    if not request.user.is_authenticated:
        return redirect('/auth/login/?next=/account/points/')
    balance = 0
    redeem_value = None
    txns: list = []
    rate = None
    try:
        from plugins.installed.loyalty_points.services import get_balance
        from plugins.installed.loyalty_points.services_redeem import (
            points_to_amount,
            redemption_rate,
        )

        balance = get_balance(request.user)
        rate = redemption_rate()
        redeem_value = points_to_amount(balance)
        from plugins.installed.loyalty_points.models import PointsTransaction

        txns = list(
            PointsTransaction.objects.filter(customer=request.user).order_by('-created_at')[:30]
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('account_points failed: %s', e, exc_info=True)
    return render(
        request,
        'loyalty_points/account_points.html',
        {
            'balance': balance,
            'redeem_value': redeem_value,
            'rate': rate,
            'txns': txns,
        },
    )


def _back(request, default='/cart/'):
    """The referring page, minus any query (mirrors the coupon/gift-card
    endpoints — the theme has no messages framework)."""
    ref = request.META.get('HTTP_REFERER', default) or default
    return ref.split('?')[0]


def apply_points(request):
    """POST /checkout/points/apply/ — stash the shopper's chosen point spend
    on the cart, capped to their balance.

    The breakdown hook turns ``cart.metadata['loyalty_points_redeem']`` into a
    discount and re-caps it against the live order total; the order-time debit
    consumes the result. Auth-only — guests have no balance to spend.
    """
    if request.method != 'POST' or not request.user.is_authenticated:
        return redirect('/cart/')
    try:
        from plugins.installed.loyalty_points.services_redeem import max_redeemable
        from plugins.installed.orders.services import CartService

        try:
            want = int(request.POST.get('points') or 0)
        except (TypeError, ValueError):
            want = 0
        cart = CartService.get_or_create_cart(customer=request.user)
        want = max(0, min(want, max_redeemable(request.user)))
        md = dict(cart.metadata or {})
        md['loyalty_points_redeem'] = want
        cart.metadata = md
        cart.save(update_fields=['metadata', 'updated_at'])
    except Exception as e:  # noqa: BLE001
        logger.warning('apply_points failed: %s', e, exc_info=True)
    return redirect(_back(request))


def remove_points(request):
    """POST /checkout/points/remove/ — clear a pending point redemption."""
    if request.method != 'POST' or not request.user.is_authenticated:
        return redirect('/cart/')
    try:
        from plugins.installed.orders.services import CartService

        cart = CartService.get_or_create_cart(customer=request.user)
        md = dict(cart.metadata or {})
        if md.pop('loyalty_points_redeem', None) is not None:
            cart.metadata = md
            cart.save(update_fields=['metadata', 'updated_at'])
    except Exception as e:  # noqa: BLE001
        logger.warning('remove_points failed: %s', e, exc_info=True)
    return redirect(_back(request))
