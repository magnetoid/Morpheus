"""Auto-split from the legacy admin_dashboard/views.py monolith."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

from plugins.installed.admin_dashboard.forms import (
    AddressForm,
    CouponForm,
    CustomerForm,
    DraftOrderForm,
    FulfillmentForm,
    ProductForm,
    RefundForm,
    VariantForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    Metric, _bulk_ids, _period, _pct_delta, _since, _sparkline_points, _trend, logger,
)

@staff_member_required
def analytics_view(request: HttpRequest) -> HttpResponse:
    period, days = _period(request)
    since = _since(days)
    series: list[dict] = []
    try:
        from plugins.installed.observability.models import MerchantMetric
        rows = (
            MerchantMetric.objects
            .filter(granularity='hour', bucket__gte=since, metric='orders_placed')
            .order_by('bucket')
        )
        series = [{'bucket': r.bucket.isoformat(), 'value': r.value} for r in rows]
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: analytics empty: %s', e)
    return render(request, 'admin_dashboard/analytics.html', {
        'series': series,
        'active_nav': 'analytics',
        'period': period,
    })


# ── Marketing ─────────────────────────────────────────────────────────────────


