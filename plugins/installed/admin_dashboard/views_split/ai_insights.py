"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from typing import Any

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    render,
    staff_member_required,
)


@staff_member_required
def ai_insights(request: HttpRequest) -> HttpResponse:
    insights: list[Any] = []
    try:
        from plugins.installed.ai_assistant.models import MerchantInsight

        insights = list(MerchantInsight.objects.order_by('-created_at')[:50])
    except Exception:  # noqa: BLE001
        insights = []
    return render(
        request,
        'admin_dashboard/ai_insights.html',
        {
            'insights': insights,
            'active_nav': 'ai_insights',
        },
    )


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
