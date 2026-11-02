"""Fraud risk scoring on every new order (ORDER_PLACED, priority 85).

Six rules, each contributing weighted points to a 0-100 score:

  1. Velocity by IP — > 5 orders from one IP in 10 min → +30.
  2. Velocity by email — > 3 orders from one email in 24 h → +20.
  3. Address mismatch — shipping country ≠ billing country → +15.
  4. High-risk BIN — first 6 digits in a denylist → +25. No gateway records
     ``metadata['payment_bin']`` yet, so this rule never fires and the
     denylist is not offered as a setting.
  5. Refund-fraud history — customer has > 2 refunds in 90 days
     totalling > 50% of orders → +30.
  6. New-customer + high-value — first order && total > the payments
     setting ``high_value_threshold`` (default 500) → +10.

Buckets: < 30 ok, 30-59 watch, 60-79 review, ≥ 80 reject. The score, bucket
and flags are written to ``order.metadata['fraud_*']`` and shown on the
dashboard order page and to Linda (``payments.order_risk``). Nothing holds or
cancels an order because of its score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger('morpheus.payments.risk')


@dataclass(slots=True)
class FraudResult:
    score: int
    bucket: str  # 'ok' | 'watch' | 'review' | 'reject'
    flags: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


def score_order(order) -> FraudResult:
    """Compute the fraud score + flags for a freshly-placed order.

    Pure function except for read-only DB queries; safe to call from
    a hook subscriber. Failures degrade gracefully — returns
    `FraudResult(score=0, bucket='ok', flags=['score_failed'])` so the
    order pipeline never breaks because the fraud engine had a bad day.
    """
    try:
        score = 0
        flags: list[str] = []
        detail: dict = {}

        # 1. IP velocity
        v_ip = _ip_velocity(order)
        if v_ip > 5:
            score += 30
            flags.append('velocity_ip')
            detail['ip_orders_10min'] = v_ip

        # 2. Email velocity
        v_email = _email_velocity(order)
        if v_email > 3:
            score += 20
            flags.append('velocity_email')
            detail['email_orders_24h'] = v_email

        # 3. Address mismatch
        if _address_mismatch(order):
            score += 15
            flags.append('address_mismatch')

        # 4. BIN denylist
        if _bin_high_risk(order):
            score += 25
            flags.append('bin_high_risk')

        # 5. Refund-fraud history
        rate = _refund_fraud_rate(order)
        if rate >= 0.5:
            score += 30
            flags.append('refund_fraud_history')
            detail['refund_rate_90d'] = round(rate, 2)

        # 6. First-order + high value
        if _is_first_order(order) and _is_high_value(order):
            score += 10
            flags.append('new_high_value')

        score = max(0, min(100, score))
        return FraudResult(score=score, bucket=_bucket_for(score), flags=flags, detail=detail)
    except Exception:  # noqa: BLE001
        logger.exception('payments.risk: score_order failed for %s', getattr(order, 'pk', '?'))
        return FraudResult(score=0, bucket='ok', flags=['score_failed'])


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def _ip_velocity(order) -> int:
    """How many orders did this IP place in the last 10 minutes?"""
    ip = _order_ip(order)
    if not ip:
        return 0
    cutoff = timezone.now() - timedelta(minutes=10)
    return _orders_with_ip(ip, since=cutoff)


def _email_velocity(order) -> int:
    """How many orders has this email placed in the last 24 hours?"""
    email = _order_email(order)
    if not email:
        return 0
    cutoff = timezone.now() - timedelta(hours=24)
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    return Order.objects.filter(email=email, placed_at__gte=cutoff).exclude(pk=order.pk).count()


def _address_mismatch(order) -> bool:
    """Different countries on shipping vs billing addresses."""
    ship = _country(getattr(order, 'shipping_address', None) or {})
    bill = _country(getattr(order, 'billing_address', None) or {})
    if not ship or not bill:
        return False
    return ship.upper() != bill.upper()


def _bin_high_risk(order) -> bool:
    """Card BIN (first 6 digits) is on the merchant's denylist.

    The list lives in settings.FRAUD_RULES.high_risk_bins. Nothing records
    the card's BIN yet, so this never matches on a real order.
    """
    denylist = _config().get('high_risk_bins') or []
    if not denylist:
        return False
    bin6 = ((order.metadata or {}).get('payment_bin') or '')[:6]
    return bool(bin6) and bin6 in set(denylist)


def _refund_fraud_rate(order) -> float:
    """Customer's refund ratio over the past 90 days.

    Counts > 2 refunds AND refund value > 50% of order value as
    a fraud-history signal.
    """
    cust = getattr(order, 'customer_id', None)
    if not cust:
        return 0.0
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=90)
    agg = Order.objects.filter(customer_id=cust, placed_at__gte=cutoff).aggregate(
        n=Count('id'), tot=Sum('total')
    )
    n = agg.get('n') or 0
    if n < 3:
        return 0.0
    # Number of refunded orders in the window.
    refunded = Order.objects.filter(
        customer_id=cust,
        placed_at__gte=cutoff,
        status__in=('refunded', 'partially_refunded'),
    ).count()
    if refunded < 2:
        return 0.0
    return refunded / n


def _is_first_order(order) -> bool:
    cust = getattr(order, 'customer_id', None)
    if not cust:
        return False
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    return not Order.objects.filter(customer_id=cust).exclude(pk=order.pk).exists()


def _is_high_value(order) -> bool:
    threshold = Decimal(str(_config().get('high_value_threshold', 500)))
    total = getattr(order, 'total', None)
    if total is None:
        return False
    amount = Decimal(str(getattr(total, 'amount', total) or 0))
    return amount > threshold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _orders_with_ip(ip: str, *, since) -> int:
    """How many orders carry this IP in metadata since `since`?

    Order.metadata may be either a flat string or a dict; we tolerate
    both shapes via __contains lookup against the rendered JSON.
    """
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    return Order.objects.filter(
        metadata__contains={'placed_from_ip': ip},
        placed_at__gte=since,
    ).count()


def _order_ip(order) -> str:
    meta = getattr(order, 'metadata', None) or {}
    if isinstance(meta, dict):
        return meta.get('placed_from_ip', '') or ''
    return ''


def _order_email(order) -> str:
    from core.utils.orders import order_email

    return order_email(order)


def _country(addr) -> str:
    if isinstance(addr, dict):
        return (addr.get('country') or '').strip()
    return (getattr(addr, 'country', '') or '').strip()


def _bucket_for(score: int) -> str:
    if score < 30:
        return 'ok'
    if score < 60:
        return 'watch'
    if score < 80:
        return 'review'
    return 'reject'


def _config() -> dict:
    try:
        from plugins.models import PluginConfig  # noqa: PLC0415

        row = PluginConfig.objects.filter(plugin_name='payments').first()
        if row and isinstance(row.config, dict):
            return row.config
    except Exception:  # noqa: BLE001, S110
        pass
    return getattr(settings, 'FRAUD_RULES', {})


def on_order_placed(*, order: Any = None, **_: Any) -> None:
    """ORDER_PLACED: score the order and stamp the result on its metadata."""
    if order is None:
        return
    try:
        result = score_order(order)

        meta = dict(getattr(order, 'metadata', {}) or {})
        meta['fraud_score'] = result.score
        meta['fraud_bucket'] = result.bucket
        meta['fraud_flags'] = result.flags
        if result.detail:
            meta['fraud_detail'] = result.detail
        order.metadata = meta
        order.save(update_fields=['metadata'])

        if result.bucket in ('review', 'reject'):
            logger.warning(
                'payments.risk: order %s flagged bucket=%s score=%s flags=%s',
                getattr(order, 'order_number', order.pk),
                result.bucket,
                result.score,
                ','.join(result.flags),
            )
    except Exception:  # noqa: BLE001 — never break the order pipeline
        logger.exception('payments.risk: on_order_placed failed')


BUCKET_LABELS = {'ok': 'Low', 'watch': 'Watch', 'review': 'Review', 'reject': 'High'}
FLAG_LABELS = {
    'velocity_ip': 'More than five orders from this IP address in 10 minutes',
    'velocity_email': 'More than three orders from this email in 24 hours',
    'address_mismatch': 'Shipping and billing countries differ',
    'bin_high_risk': 'Card number on the high-risk list',
    'refund_fraud_history': 'Most of this customer’s recent orders were refunded',
    'new_high_value': 'A first order above the high-value amount',
    'score_failed': 'The check could not run',
}


def order_risk(order) -> dict | None:
    """The stored score of an order in plain words, or None when it has none."""
    meta = getattr(order, 'metadata', None) or {}
    if not isinstance(meta, dict) or 'fraud_score' not in meta:
        return None
    bucket = str(meta.get('fraud_bucket') or _bucket_for(int(meta.get('fraud_score') or 0)))
    return {
        'score': int(meta.get('fraud_score') or 0),
        'bucket': bucket,
        'level': BUCKET_LABELS.get(bucket, bucket),
        'reasons': [FLAG_LABELS.get(f, f) for f in meta.get('fraud_flags') or []],
    }


def order_panel(value, order=None, **_: Any):
    """ORDER_DETAIL_PANELS: the fraud check's result on the dashboard order page."""
    if order is None or not isinstance(value, list):
        return value
    risk = order_risk(order)
    if risk is None:
        return value
    from django.template.loader import render_to_string  # noqa: PLC0415

    html = render_to_string('payments/order_risk_panel.html', {'risk': risk})
    value.append({'label': 'Fraud check', 'html': html, 'priority': 40})
    return value
