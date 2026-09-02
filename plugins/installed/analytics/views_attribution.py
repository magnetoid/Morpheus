"""Multi-touch attribution + ROAS dashboard view."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.authz import require_capability
from plugins.installed.analytics.services_attribution import MODELS

_MODEL_LABELS = {
    'last_touch': 'Last touch',
    'first_touch': 'First touch',
    'linear': 'Linear',
    'time_decay': 'Time decay',
    'position_based': 'Position-based',
}


@staff_member_required
@require_capability('analytics.read')
def attribution_view(request):
    from plugins.installed.analytics.services_attribution import roas_by_channel

    model = request.GET.get('model', 'last_touch')
    if model not in MODELS:
        model = 'last_touch'
    rows = roas_by_channel(model=model)
    total_spend = sum((r['spend'] for r in rows), Decimal(0))
    total_revenue = sum((r['revenue'] for r in rows), Decimal(0))
    max_revenue = max((r['revenue'] for r in rows), default=Decimal(0))
    for r in rows:
        r['bar_pct'] = int(r['revenue'] / max_revenue * 100) if max_revenue else 0
    return render(
        request,
        'analytics/attribution.html',
        {
            'model': model,
            'model_label': _MODEL_LABELS.get(model, model),
            'models': [(m, _MODEL_LABELS[m]) for m in MODELS],
            'rows': rows,
            'total_spend': total_spend,
            'total_revenue': total_revenue,
            'blended_roas': round(total_revenue / total_spend, 2) if total_spend else None,
            'active_nav': 'analytics',
        },
    )
