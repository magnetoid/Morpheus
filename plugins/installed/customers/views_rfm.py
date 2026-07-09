"""Customer RFM segments dashboard."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

_SEGMENT_ORDER = ['champions', 'loyal', 'potential', 'new', 'at_risk', 'lost']
_SEGMENT_LABEL = {
    'champions': 'Champions',
    'loyal': 'Loyal',
    'potential': 'Potential',
    'new': 'New',
    'at_risk': 'At risk',
    'lost': 'Lost',
}
_SEGMENT_TONE = {
    'champions': 'success',
    'loyal': 'success',
    'potential': 'info',
    'new': 'info',
    'at_risk': 'warn',
    'lost': 'danger',
}


@staff_member_required
def segments_dashboard(request):
    from plugins.installed.customers.models import CustomerSegment, SegmentMigration

    rows = {
        r['segment']: r
        for r in CustomerSegment.objects.values('segment').annotate(
            n=Count('id'), revenue=Sum('customer__lifetime_value')
        )
    }
    total = sum(r['n'] for r in rows.values())
    segments = [
        {
            'key': key,
            'label': _SEGMENT_LABEL[key],
            'tone': _SEGMENT_TONE[key],
            'n': rows.get(key, {}).get('n', 0),
            'revenue': rows.get(key, {}).get('revenue') or 0,
            'pct': round(rows.get(key, {}).get('n', 0) / total * 100) if total else 0,
        }
        for key in _SEGMENT_ORDER
    ]

    since = timezone.now().date() - timedelta(days=30)
    moves = list(
        SegmentMigration.objects.filter(day__gte=since)
        .exclude(old_segment='')  # real flips, not first assignment
        .values('new_segment')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    for mv in moves:
        mv['label'] = _SEGMENT_LABEL.get(mv['new_segment'], mv['new_segment'])

    return render(
        request,
        'customers/dashboard/segments.html',
        {'segments': segments, 'total': total, 'moves': moves, 'active_nav': 'customers'},
    )
