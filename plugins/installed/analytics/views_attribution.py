"""Multi-touch attribution + ROAS dashboard view."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from djmoney.money import Money

from core.authz import require_capability
from core.pricing import store_currency
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
    from plugins.installed.analytics.services import revenue_by_source
    from plugins.installed.analytics.services_attribution import roas_by_channel

    model = request.GET.get('model', 'last_touch')
    if model not in MODELS:
        model = 'last_touch'
    currency = store_currency()

    def cash(amount):
        return None if amount is None else Money(amount, currency)

    rows = roas_by_channel(model=model)
    known_spend = [r['spend'] for r in rows if r['spend'] is not None]
    # Spend comes from the Channels app; with none on file it stays unknown (None).
    total_spend = sum(known_spend, Decimal(0)) if known_spend else None
    total_revenue = sum((r['revenue'] for r in rows), Decimal(0))
    max_revenue = max((r['revenue'] for r in rows), default=Decimal(0))
    store_revenue = Decimal(str(revenue_by_source(days=30)['total']))
    for r in rows:
        r['bar_pct'] = int(r['revenue'] / max_revenue * 100) if max_revenue else 0
        for key in ('spend', 'revenue', 'platform_revenue'):
            r[key] = cash(r[key])
    return render(
        request,
        'analytics/attribution.html',
        {
            'model': model,
            'model_label': _MODEL_LABELS.get(model, model),
            'models': [(m, _MODEL_LABELS[m]) for m in MODELS],
            'rows': rows,
            'total_spend': cash(total_spend),
            'total_revenue': cash(total_revenue),
            'total_revenue_store': cash(store_revenue),
            'blended_roas': round(total_revenue / total_spend, 2) if total_spend else None,
            'blended_mer': round(store_revenue / total_spend, 2) if total_spend else None,
            'active_nav': 'analytics',
        },
    )
