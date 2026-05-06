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
def palette_search(request: HttpRequest) -> HttpResponse:
    """JSON endpoint backing the Cmd+K palette.

    Returns up to ~12 hits across orders / products / customers plus a
    fixed list of nav targets and settings categories. Hits are
    annotated with `kind`, `label`, `hint`, `url`, and `icon` so the
    front-end can render them uniformly.
    """
    from django.http import JsonResponse
    from django.contrib.auth import get_user_model

    q = (request.GET.get('q') or '').strip()
    out: list[dict] = []

    # Fixed nav targets — always show top-of-list, filtered by name.
    NAV = [
        ('home', 'Home', 'Dashboard overview', '/dashboard/', 'home'),
        ('orders', 'All orders', 'Open the orders list', '/dashboard/orders/', 'shopping-bag'),
        ('orders_new', 'New order', 'Create a draft order', '/dashboard/orders/new/', 'plus'),
        ('products', 'All products', 'Open the products list', '/dashboard/products/', 'package'),
        ('product_new', 'New product', 'Create a product', '/dashboard/products/new/', 'plus'),
        ('customers', 'Customers', 'Open the customers list', '/dashboard/customers/', 'users'),
        ('customer_new', 'New customer', 'Create a customer', '/dashboard/customers/new/', 'plus'),
        ('returns', 'Returns', 'RMAs awaiting approval', '/dashboard/returns/', 'undo-2'),
        ('crm_inbox', 'CRM inbox', 'IMAP / SMTP mail', '/dashboard/crm/inbox/', 'inbox'),
        ('settings', 'Settings', 'Store configuration', '/dashboard/settings/', 'settings'),
        ('ai_settings', 'AI providers', 'Configure provider + models', '/dashboard/settings/ai/', 'sparkles'),
        ('email_templates', 'Email templates', 'Edit transactional emails', '/dashboard/settings/email-templates/', 'mail'),
        ('insights', 'AI insights', 'Read pending insights', '/dashboard/ai-insights/', 'lightbulb'),
        ('apps', 'Apps', 'All installed plugins', '/dashboard/apps/', 'grid-3x3'),
    ]
    ql = q.lower()
    for slug, label, hint, url, icon in NAV:
        if not q or ql in label.lower() or ql in hint.lower():
            out.append({'kind': 'nav', 'label': label, 'hint': hint, 'url': url, 'icon': icon})
        if len(out) >= 14:
            break

    if not q:
        return JsonResponse({'hits': out[:14]})

    # Live entity matches — small per-kind cap so a generic word doesn't
    # flood the panel with one entity type.
    try:
        from plugins.installed.orders.models import Order
        for o in Order.objects.filter(order_number__icontains=q)[:4]:
            out.append({
                'kind': 'order', 'label': f'#{o.order_number}',
                'hint': f'{o.email or "—"} · {o.get_status_display()}',
                'url': f'/dashboard/orders/{o.order_number}/',
                'icon': 'shopping-bag',
            })
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.catalog.models import Product
        for p in Product.objects.filter(name__icontains=q)[:5]:
            out.append({
                'kind': 'product', 'label': p.name,
                'hint': p.sku or '—',
                'url': f'/dashboard/products/{p.id}/',
                'icon': 'package',
            })
    except Exception:  # noqa: BLE001
        pass
    try:
        User = get_user_model()
        for u in User.objects.filter(email__icontains=q)[:5]:
            out.append({
                'kind': 'customer', 'label': u.email,
                'hint': (
                    (getattr(u, 'first_name', '') + ' ' + getattr(u, 'last_name', '')).strip()
                    or '—'
                ),
                'url': f'/dashboard/customers/{u.id}/',
                'icon': 'user',
            })
    except Exception:  # noqa: BLE001
        pass

    return JsonResponse({'hits': out[:25]})

