"""Linda's Pulse — proactive merchant insights.

Generates a small ranked list of "things you should look at" cards for
the dashboard home. Pattern follows Shopify Sidekick Pulse: a continuous
stream of ranked, actionable cards rather than per-event notifications.

Six signals evaluated per refresh:
  - low_stock           — SKUs at/below threshold
  - abandoned_cart      — carts last touched >3h ago, with items
  - new_rma             — return requests in 'requested' state
  - revenue_delta       — yesterday vs. day-before
  - expiring_promo      — promotions ending in <72h
  - poor_review         — 1- or 2-star reviews in the last 7 days

Each signal yields zero or one MerchantInsight per evaluation. Results
are ranked by (priority, recency) and the top 5 unread are surfaced on
the dashboard panel.

Idempotency: each insight has a stable ``signature`` written to
``suggested_action['signature']``. Re-running the generator skips
insights with the same signature that are still unread, so the panel
doesn't accumulate duplicates between refreshes.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger('morpheus.pulse')


_PRIORITY = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


def generate_pulse_insights() -> list:
    """Evaluate every signal, write/update MerchantInsight rows, return them.

    Each signal is wrapped so a missing plugin or bad data never breaks
    the whole pulse pass — the merchant gets *some* insights even when a
    subsystem is degraded.
    """
    from plugins.installed.ai_assistant.models import MerchantInsight

    out = []
    for fn in (_low_stock_signal, _abandoned_cart_signal, _new_rma_signal,
               _revenue_delta_signal, _expiring_promo_signal,
               _poor_review_signal):
        try:
            insight = fn()
        except Exception as e:  # noqa: BLE001
            logger.debug('pulse: signal %s skipped: %s', fn.__name__, e)
            continue
        if insight is None:
            continue
        out.append(_upsert(insight))
    out.sort(key=lambda i: (_PRIORITY.get(i.priority, 9), -i.created_at.timestamp()))
    return out


def _upsert(payload: dict):
    """Idempotent write: keep one row per (signature) until it's read."""
    from plugins.installed.ai_assistant.models import MerchantInsight
    sig = payload['suggested_action'].get('signature') or _sig(payload)
    payload['suggested_action']['signature'] = sig
    existing = MerchantInsight.objects.filter(
        suggested_action__signature=sig, is_read=False,
    ).first()
    if existing is not None:
        # Refresh body + estimated_impact; keep created_at so card order stays sensible.
        existing.title = payload['title']
        existing.body = payload['body']
        existing.estimated_impact = payload.get('estimated_impact', '')
        existing.priority = payload['priority']
        existing.suggested_action = payload['suggested_action']
        existing.save(update_fields=[
            'title', 'body', 'estimated_impact', 'priority', 'suggested_action',
        ])
        return existing
    return MerchantInsight.objects.create(**payload)


def _sig(payload: dict) -> str:
    raw = f'{payload["insight_type"]}|{payload["title"]}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


# ── Signals ────────────────────────────────────────────────────────────


def _low_stock_signal() -> dict | None:
    from plugins.installed.inventory.models import StockLevel
    rows = list(
        StockLevel.objects.select_related('variant', 'variant__product')
        .filter(quantity__lte=5)[:50]
    )
    rows = [s for s in rows if s.available_quantity <= 5]
    if not rows:
        return None
    examples = ', '.join(
        f'{s.variant.product.name} ({s.available_quantity})' for s in rows[:3]
    )
    return {
        'insight_type': 'risk',
        'priority': 'high' if len(rows) >= 3 else 'medium',
        'title': f'{len(rows)} SKU(s) low or out of stock',
        'body': f'On the shelf with ≤5 units: {examples}'
                + (f' and {len(rows) - 3} more.' if len(rows) > 3 else '.'),
        'estimated_impact': 'Restock to avoid lost orders this week.',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/inventory/?filter=low_stock',
            'label': 'Open inventory',
        },
    }


def _abandoned_cart_signal() -> dict | None:
    from plugins.installed.orders.models import Cart
    cutoff = timezone.now() - timedelta(hours=3)
    rows = (Cart.objects.filter(updated_at__lt=cutoff)
            .exclude(items__isnull=True).distinct()[:200])
    n = sum(1 for c in rows if c.items.exists())
    if n == 0:
        return None
    return {
        'insight_type': 'opportunity',
        'priority': 'medium' if n < 10 else 'high',
        'title': f'{n} abandoned cart(s) older than 3h',
        'body': 'Recovery emails go out automatically; a one-off coupon often '
                'reactivates the higher-value ones.',
        'estimated_impact': 'Cart-abandonment recovery typically returns 8-15% of value.',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/cart-abandonment/',
            'label': 'Open abandonment console',
        },
    }


def _new_rma_signal() -> dict | None:
    from plugins.installed.orders.refunds import ReturnRequest
    rows = ReturnRequest.objects.filter(state='requested')
    n = rows.count()
    if n == 0:
        return None
    return {
        'insight_type': 'action',
        'priority': 'high' if n >= 3 else 'medium',
        'title': f'{n} return request(s) waiting for review',
        'body': 'Customers who get an RMA decision within 24h are 30% more '
                'likely to reorder. Approve or reject in the returns console.',
        'estimated_impact': '',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/returns/?state=requested',
            'label': 'Review returns',
        },
    }


def _revenue_delta_signal() -> dict | None:
    from django.db.models import Sum
    from plugins.installed.orders.models import Order
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)

    def rev(d):
        return Order.objects.filter(
            placed_at__date=d, status__in=('paid', 'fulfilled', 'shipped', 'delivered'),
        ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    y = Decimal(str(rev(yesterday) or 0))
    d = Decimal(str(rev(day_before) or 0))
    if d == 0 or y == 0:
        return None
    pct = (y - d) / d * Decimal(100)
    if abs(pct) < 20:
        return None
    direction = 'up' if pct > 0 else 'down'
    sign = '+' if pct > 0 else ''
    return {
        'insight_type': 'report',
        'priority': 'medium' if abs(pct) < 50 else 'high',
        'title': f'Revenue {direction} {sign}{pct:.0f}% day-on-day',
        'body': f'Yesterday: ${y:.2f}. Day before: ${d:.2f}. '
                + ('Worth a look at the source mix.' if pct > 0 else
                   'Check what changed — promos, traffic, or stockouts.'),
        'estimated_impact': '',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/analytics/',
            'label': 'Open analytics',
        },
    }


def _expiring_promo_signal() -> dict | None:
    from plugins.installed.promotions.models import Promotion
    cutoff = timezone.now() + timedelta(hours=72)
    rows = list(Promotion.objects.filter(
        is_active=True, ends_at__lte=cutoff, ends_at__gte=timezone.now(),
    )[:5])
    if not rows:
        return None
    names = ', '.join(p.name for p in rows[:3])
    return {
        'insight_type': 'action',
        'priority': 'medium',
        'title': f'{len(rows)} promotion(s) ending in <72h',
        'body': f'Ending soon: {names}.'
                + (f' (+{len(rows) - 3} more)' if len(rows) > 3 else '')
                + '  Decide whether to extend or let lapse.',
        'estimated_impact': '',
        'suggested_action': {
            'kind': 'open_view', 'url': '/dashboard/promotions/',
            'label': 'Open promotions',
        },
    }


def _poor_review_signal() -> dict | None:
    from plugins.installed.catalog.models import Review
    cutoff = timezone.now() - timedelta(days=7)
    rows = list(Review.objects.filter(
        rating__lte=2, created_at__gte=cutoff, is_approved=True,
    ).select_related('product')[:20])
    if not rows:
        return None
    examples = ', '.join(f'{r.product.name} ({r.rating}★)' for r in rows[:3])
    return {
        'insight_type': 'risk',
        'priority': 'high' if len(rows) >= 3 else 'medium',
        'title': f'{len(rows)} low-star review(s) in the last week',
        'body': f'Recent: {examples}. Reading them often surfaces a fixable '
                'product description or a fulfillment problem.',
        'estimated_impact': '',
        'suggested_action': {
            'kind': 'open_view',
            'url': '/dashboard/reviews/?rating_lte=2',
            'label': 'Read reviews',
        },
    }
