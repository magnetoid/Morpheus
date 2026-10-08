"""The loyalty card on the Customers list (DashboardCard)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone


def loyalty_card(request) -> dict:
    """Points customers hold (earned minus spent), how many hold any, and the
    last 30 days' earning and spending."""
    from plugins.installed.loyalty_points.models import PointsTransaction

    ledger = PointsTransaction.objects
    if not ledger.exists():
        return {'empty': 'No points earned yet.'}
    outstanding = ledger.aggregate(n=Sum('points'))['n'] or 0
    members = ledger.values('customer_id').distinct().count()
    recent = ledger.filter(created_at__gte=timezone.now() - timedelta(days=30))
    earned = recent.filter(points__gt=0).aggregate(n=Sum('points'))['n'] or 0
    spent = -(recent.filter(points__lt=0).aggregate(n=Sum('points'))['n'] or 0)
    return {
        'value': f'{outstanding:,}',
        'caption': f'points held by {members} customer{"s" if members != 1 else ""}',
        'rows': [('Earned, 30 days', f'{earned:,}'), ('Redeemed, 30 days', f'{spent:,}')],
    }
