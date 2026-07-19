"""Points redemption (v1) — bounded ledger-backed spend.

Public surface:

    redemption_rate()                  → int   (points per 1.00 currency unit)
    points_to_amount(points, currency) → Money (discount the points are worth)
    amount_to_points(amount)           → int   (points needed for an amount)
    max_redeemable(customer, order_total=None) → int (capped by balance + policy)
    redeem_points(customer, points, *, order=None, reason='') → Money
    reverse_redemption(customer, points, *, order=None, reason='') → PointsTransaction
    redeem_points_for_order(customer, points, *, order) → Money|None (idempotent)
    reverse_redemption_for_order(order) → PointsTransaction|None (idempotent)

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
    from plugins.registry import plugin_registry

    try:
        rate = int(
            plugin_registry.config_value(
                'loyalty_points', 'redemption_rate', DEFAULT_REDEMPTION_RATE
            )
        )
    except (TypeError, ValueError):
        rate = DEFAULT_REDEMPTION_RATE
    return rate if rate > 0 else DEFAULT_REDEMPTION_RATE


def max_redeem_fraction() -> Decimal:
    """Cap on the fraction of an order's total that points may cover.

    1.0 (default) means points can pay the whole order; 0.5 caps at half.
    Clamped to (0, 1].
    """
    from plugins.registry import plugin_registry

    try:
        frac = Decimal(
            str(plugin_registry.config_value('loyalty_points', 'max_redeem_fraction', '1'))
        )
    except (TypeError, ValueError, ArithmeticError):
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
    # FLOOR the cap, NOT amount_to_points (which rounds UP). A cap is "the most
    # points whose *value* doesn't exceed the order" — so a point worth more than
    # a small order can't be over-redeemed against it. amount_to_points answers a
    # different question ("points NEEDED to fully cover an amount", rounds up) and
    # using it here let the shopper spend a whole point against a sub-point order
    # and lose the unused value (deep-debug #23). Safe at the default rate 100:
    # any 2-dp total × 100 is integral, so floor == ceil. Because the cap now
    # floors, points_to_amount(cap) ≤ cap_amount ≤ order_total, which also keeps
    # the loyalty credit ≤ order total downstream (no discount > total).
    #
    # Deliberately conservative at rates that DON'T divide 100: because
    # points_to_amount also floors to cents, this can under-cap by one point at a
    # cent-truncation boundary (rate 3, $0.33 → 0, refusing the 1 point that would
    # exactly cover the order). That's the safe direction — the shopper keeps the
    # points, never a mischarge — and no realistic rate (a divisor of 100) hits
    # it. A fully-tight cap for non-divisor rates (largest P with
    # points_to_amount(P) ≤ cap_amount) is a noted low-priority refinement.
    cap_points = int(
        (cap_amount * Decimal(redemption_rate())).to_integral_value(rounding=ROUND_DOWN)
    )
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


def redeem_points_for_order(customer, points: int, *, order):
    """Idempotent order-time debit — spend ``points`` against ``order`` once.

    The discount is already baked into ``order.total`` by the breakdown
    hook; this is the ledger side. Safe on a checkout retry: a second call
    for the same order is a no-op (returns ``None``). The caller
    (``OrderService.create_from_cart``) treats a raised ``ValueError`` —
    e.g. a balance race — as fatal and rolls the order back rather than
    charge the discounted total without consuming the points.
    """
    from plugins.installed.loyalty_points.models import PointsTransaction

    order_number = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    if PointsTransaction.objects.filter(
        customer=customer, reason='spend_order', order_number=order_number
    ).exists():
        return None
    return redeem_points(customer, points, order=order, reason=f'Order {order_number}')


def reverse_redemption_for_order(order):
    """Re-credit whatever points were spent on ``order`` — idempotent.

    Fired from the loyalty ``ORDER_CANCELLED`` subscriber so a shopper
    isn't out the points for an order that never shipped. A no-op when
    nothing was spent or the reversal already happened (a paid cancel fires
    both ``ORDER_CANCELLED`` and a refund).
    """
    from django.db.models import Sum

    from plugins.installed.loyalty_points.models import PointsTransaction

    customer = getattr(order, 'customer', None)
    if customer is None:
        return None
    order_number = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    if PointsTransaction.objects.filter(
        customer=customer, reason='adjust', order_number=order_number
    ).exists():
        return None
    spent = (
        PointsTransaction.objects.filter(
            customer=customer, reason='spend_order', order_number=order_number
        ).aggregate(total=Sum('points'))['total']
        or 0
    )
    points = -int(spent)  # spend rows are negative
    if points <= 0:
        return None
    return reverse_redemption(
        customer, points, order=order, reason=f'Order {order_number} cancelled'
    )
