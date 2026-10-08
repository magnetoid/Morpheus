"""The coupons card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from django.db.models import F, Q
from django.utils import timezone


def coupons_card(request) -> dict:
    """Coupons a shopper can use right now, the most-used first — the same
    rule as `Coupon.is_valid`, as a query."""
    from plugins.installed.marketing.models import Coupon

    now = timezone.now()
    live = (
        Coupon.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exclude(usage_limit__isnull=False, usage_limit__gt=0, times_used__gte=F('usage_limit'))
    )
    total = live.count()
    if not total:
        return {'empty': 'No coupon can be used right now.'}
    rows = [(c.code, f'{c.times_used} used') for c in live.order_by('-times_used', 'code')[:3]]
    return {'value': str(total), 'caption': 'coupons live now', 'rows': rows}
