"""The affiliates card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from django.db.models import Sum


def affiliates_card(request) -> dict:
    """Approved partners, partners waiting for review, and the commission the
    store owes (approved, not yet paid)."""
    from djmoney.money import Money

    from core.templatetags.morph import money_filter
    from plugins.installed.affiliates.models import Affiliate, AffiliateConversion

    approved = Affiliate.objects.filter(status='approved').count()
    waiting = Affiliate.objects.filter(status='pending').count()
    if not (approved or waiting):
        return {'empty': 'No affiliates yet.'}
    owed = [
        (row['commission_currency'], row['total'] or 0)
        for row in AffiliateConversion.objects.filter(status='approved')
        .values('commission_currency')
        .annotate(total=Sum('commission'))
        .order_by('-total')
    ]
    rows = [('Waiting for review', waiting)]
    rows += [('Commission owed', money_filter(Money(total, cur))) for cur, total in owed[:2]]
    return {'value': str(approved), 'caption': 'approved affiliates', 'rows': rows}
