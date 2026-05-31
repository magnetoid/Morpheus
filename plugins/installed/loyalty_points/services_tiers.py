"""Tier assignment from 12-month trailing revenue."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger('morpheus.loyalty.tiers')

DEFAULT_TIERS = (
    {'key': 'bronze', 'label': 'Bronze', 'rank': 1, 'min_revenue': Decimal('0')},
    {'key': 'silver', 'label': 'Silver', 'rank': 2, 'min_revenue': Decimal('500')},
    {'key': 'gold', 'label': 'Gold', 'rank': 3, 'min_revenue': Decimal('2000')},
)


def ensure_default_tiers() -> int:
    """Idempotently seed the default 3-tier ladder. Returns rows created."""
    from plugins.installed.loyalty_points.models import LoyaltyTier  # noqa: PLC0415

    created = 0
    for entry in DEFAULT_TIERS:
        _, was_created = LoyaltyTier.objects.get_or_create(
            key=entry['key'],
            defaults={
                'label': entry['label'],
                'rank': entry['rank'],
                'min_revenue': entry['min_revenue'],
                'perks': _default_perks_for(entry['key']),
            },
        )
        if was_created:
            created += 1
    return created


def assign_tier(customer) -> str:
    """Compute + persist this customer's tier from their 12-month revenue.

    Returns the assigned tier key. Idempotent.
    """
    from plugins.installed.loyalty_points.models import (  # noqa: PLC0415
        CustomerTier,
        LoyaltyTier,
    )
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=365)
    agg = Order.objects.filter(
        customer_id=customer.pk,
        placed_at__gte=cutoff,
        status__in=('confirmed', 'paid', 'fulfilled', 'completed'),
    ).aggregate(total=Sum('total'))
    revenue = Decimal(str(agg.get('total') or 0))

    # Pick the highest tier whose min_revenue ≤ this customer's 12-mo total.
    tier = LoyaltyTier.objects.filter(min_revenue__lte=revenue).order_by('-rank').first()

    CustomerTier.objects.update_or_create(
        customer=customer,
        defaults={'tier': tier, 'revenue_12m': revenue},
    )
    return tier.key if tier else ''


def assign_all() -> dict:
    """Bulk assignment — for the nightly Celery task. Returns counts."""
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    ensure_default_tiers()
    User = get_user_model()

    counts: dict[str, int] = {}
    # Iterate only customers with at least one order in the last 12 months
    # — others stay at the default unassigned (Bronze if min_revenue=0).
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=365)
    customer_ids = (
        Order.objects.filter(placed_at__gte=cutoff, customer_id__isnull=False)
        .values_list('customer_id', flat=True)
        .distinct()
    )

    for cid in customer_ids:
        try:
            customer = User.objects.only('pk').get(pk=cid)
        except User.DoesNotExist:
            continue
        key = assign_tier(customer)
        counts[key] = counts.get(key, 0) + 1
    logger.info('loyalty: tiers assigned %s', counts)
    return counts


# ---------------------------------------------------------------------------


def _default_perks_for(key: str) -> dict:
    return {
        'bronze': {'points_multiplier': 1.0},
        'silver': {
            'points_multiplier': 1.25,
            'free_shipping_above': '40',
            'early_access_hours': 24,
        },
        'gold': {
            'points_multiplier': 1.5,
            'free_shipping_above': '0',
            'early_access_hours': 72,
            'birthday_bonus_points': 500,
        },
    }.get(key, {})
