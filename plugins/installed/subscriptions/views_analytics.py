"""Subscription analytics dashboard view."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def subscription_analytics(request):
    from plugins.installed.subscriptions import analytics

    trend = analytics.mrr_trend()
    plans = analytics.plan_breakdown()
    return render(
        request,
        'subscriptions/dashboard/analytics.html',
        {
            'mrr': analytics.committed_mrr(),
            'trend': trend,
            'trend_series': [float(r['mrr']) for r in trend],  # MRR ≥ 0 → sparkline-safe
            'churn': analytics.churn_rate(),
            'trials': analytics.trial_funnel(),
            'plans': plans,
            'active_count': sum(p['active'] for p in plans),
            'active_nav': 'analytics',
        },
    )
