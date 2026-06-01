"""Points redemption (v1) — bounded ledger-backed spend.

Public surface:

    redemption_rate()                  → int   (points per 1.00 currency unit)
    points_to_amount(points, currency) → Money (discount the points are worth)
    amount_to_points(amount)           → int   (points needed for an amount)
    max_redeemable(customer, order_total=None) → int (capped by balance + policy)
    redeem_points(customer, points, *, order=None, reason='') → Money
    reverse_redemption(customer, points, *, order=None, reason='') → PointsTransaction

The discount math is intentionally separate from the checkout wiring.
``redeem_points`` only touches the ledger; the *application* of the
resulting discount to an order total flows through the existing
``CART_CALCULATE_BREAKDOWN`` hook (see ``LoyaltyPointsPlugin``) — the
same path gift cards and coupons use. See the module docstring in
``plugin.py`` and ``docs/plans/morph-backlog-2026-06.md`` for the
remaining cart-mutation endpoint that lets a shopper choose how many
points to spend at checkout.
"""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional — this module is reachable from
# apps.py:ready() via the breakdown hook before all models are loaded.
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

# Default: 100 points == 1.00 unit of store currency. Configurable per
# store via the loyalty settings panel (`redemption_rate`).
DEFAULT_REDEMPTION_RATE = 100


def redemption_rate() -> int:
    """Points needed to redeem 1.00 unit of store currency.

    Reads the merchant-configured value from the plugin's PluginConfig
    (settings panel), falling back to the schema default. Always returns
    a positive int — a misconfigured 0/negative rate falls back to the
    default so we never divide by zero.
    """
    rate = DEFAULT_REDEMPTION_RATE
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('loyalty_points')
        if plugin is not None:
            rate = int(plugin.get_config_value('redemption_rate', DEFAULT_REDEMPTION_RATE))
    except Exception:  # noqa: BLE001 — config read must never break checkout math
        rate = DEFAULT_REDEMPTION_RATE
    return rate if rate > 0 else DEFAULT_REDEMPTION_RATE


def max_redeem_fraction() -> Decimal:
    """Cap on the fraction of an order's total that points may cover.

    1.0 (default) means points can pay the whole order; 0.5 caps at half.
    Clamped to (0, 1].
    """
    frac = Decimal('1')
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('loyalty_points')
        if plugin is not None:
            frac = Decimal(str(plugin.get_config_value('max_redeem_fraction', '1')))
    except Exception:  # noqa: BLE001
        frac = Decimal('1')
    if frac <= 0 or frac > 1:
        return Decimal('1')
    return frac


def points_to_amount(points: int, currency: str = 'USD'):
    """Money value of ``points`` at the current redemption rate.

    Rounded DOWN to the cent so we never over-credit a fractional point.
    """
    from djmoney.money import Money

    rate = redemption_rate()
    amount = (Decimal(int(points or 0)) / Decimal(rate)).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN
    )
    if amount < 0:
        amount = Decimal('0')
    return Money(amount, currency)


def amount_to_points(amount) -> int:
    """Points required to cover ``amount`` (Money or Decimal-like).

    Rounded UP so the discount granted never exceeds the points spent.
    """
    value = Decimal(str(getattr(amount, 'amount', amount) or 0))
    rate = redemption_rate()
    points = (value * Decimal(rate)).to_integral_value(rounding='ROUND_CEILING')
    return max(0, int(points))


def max_redeemable(customer, order_total=None) -> int:
    """Largest point spend allowed for this customer right now.

    Bounded by (a) the customer's balance and (b) the points-value of the
    order total times ``max_redeem_fraction`` (when an order total is
    supplied). Returns whole points only.
    """
    from plugins.installed.loyalty_points.services import get_balance

    balance = get_balance(customer)
    if balance <= 0:
        return 0
    if order_total is None:
        return balance
    cap_amount = (
        Decimal(str(getattr(order_total, 'amount', order_total) or 0)) * max_redeem_fraction()
    )
    if cap_amount <= 0:
        return 0
    cap_points = amount_to_points(cap_amount)
    return max(0, min(balance, cap_points))


def redeem_points(customer, points: int, *, order=None, reason: str = ''):
    """Spend ``points`` from ``customer``'s balance, return the discount Money.

    Records a single negative ``PointsTransaction(kind='spend_order')`` and
    returns the Money discount the spend is worth. Raises ``ValueError`` if
    the points are non-positive or exceed the available balance — callers
    must catch this (the checkout breakdown hook degrades gracefully).

    Idempotency is the caller's responsibility: pass a stable
    ``order_number`` via ``order`` and check for an existing spend row
    before calling if the checkout path can retry.
    """
    from plugins.installed.loyalty_points.models import PointsTransaction
    from plugins.installed.loyalty_points.services import get_balance

    points = int(points or 0)
    if points <= 0:
        raise ValueError('Redemption points must be a positive integer.')
    if customer is None or not getattr(customer, 'is_authenticated', False):
        raise ValueError('Only authenticated customers can redeem points.')
    balance = get_balance(customer)
    if points > balance:
        raise ValueError(f'Insufficient balance: have {balance}, asked {points}.')

    order_number = ''
    currency = 'USD'
    if order is not None:
        order_number = str(
            getattr(order, 'order_number', '') or getattr(order, 'number', '') or order.pk
        )
        total = getattr(order, 'total', None)
        if total is not None:
            currency = str(getattr(total, 'currency', currency))

    PointsTransaction.objects.create(
        customer=customer,
        points=-points,
        reason='spend_order',
        order_number=order_number,
        note=(reason or f'-{points} pts redeemed')[:200],
    )
    return points_to_amount(points, currency)


def reverse_redemption(customer, points: int, *, order=None, reason: str = ''):
    """Refund a prior redemption — re-credit ``points`` to the customer.

    Used on order cancel / refund so a shopper isn't out the points for an
    order that never shipped. Records a positive ``adjust`` row (not
    ``earn_order`` — these weren't earned, they're a reversal).
    """
    from plugins.installed.loyalty_points.models import PointsTransaction

    points = int(points or 0)
    if points <= 0:
        raise ValueError('Reversal points must be a positive integer.')
    order_number = ''
    if order is not None:
        order_number = str(
            getattr(order, 'order_number', '') or getattr(order, 'number', '') or order.pk
        )
    return PointsTransaction.objects.create(
        customer=customer,
        points=points,
        reason='adjust',
        order_number=order_number,
        note=(reason or f'+{points} pts redemption reversed')[:200],
    )
