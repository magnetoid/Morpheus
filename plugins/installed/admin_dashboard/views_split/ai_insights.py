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
def ai_insights(request: HttpRequest) -> HttpResponse:
    insights: list[Any] = []
    try:
        from plugins.installed.ai_assistant.models import MerchantInsight
        insights = list(MerchantInsight.objects.order_by('-created_at')[:50])
    except Exception:  # noqa: BLE001
        insights = []
    return render(request, 'admin_dashboard/ai_insights.html', {
        'insights': insights,
        'active_nav': 'ai_insights',
    })


# ─── Editable transactional email templates ──────────────────────────────────


_EMAIL_TEMPLATE_KEYS = [
    ('order_placed', 'Order placed', 'Order #{{ order.order_number }} received'),
    ('order_paid', 'Order paid', 'Payment confirmed for order #{{ order.order_number }}'),
    ('order_fulfilled', 'Order fulfilled', 'Order #{{ order.order_number }} is on its way'),
    ('order_cancelled', 'Order cancelled', 'Order #{{ order.order_number }} cancelled'),
    ('refund_issued', 'Refund issued', 'Refund issued for order #{{ order.order_number }}'),
    ('digital_download', 'Digital downloads', 'Your downloads — order #{{ order.order_number }}'),
    ('cart_abandoned', 'Cart abandoned', 'You left items in your cart'),
    ('welcome', 'Welcome', 'Welcome'),
]


