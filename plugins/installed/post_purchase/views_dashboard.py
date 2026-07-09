"""Dashboard views for post_purchase — the NPS analytics page."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def nps_dashboard(request):
    from plugins.installed.post_purchase import analytics

    days = int(request.GET.get('days', 90) or 90)
    trend = analytics.nps_trend()
    return render(
        request,
        'post_purchase/dashboard/nps.html',
        {
            'summary': analytics.nps_summary(days),
            'trend': trend,
            # NPS ranges −100…100; the sparkline tag only handles positive series,
            # so shift by +100 (preserves the trend shape, not the absolute zero-line).
            'trend_series': [r['nps'] + 100 for r in trend],
            'by_product': analytics.nps_by_product(days),
            'detractors': analytics.recent_detractors(),
            'days': days,
            'active_nav': 'analytics',
        },
    )
