"""Marketing dashboard pages."""

from __future__ import annotations

from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


def _safe_list(model_path, *, order_by='-created_at', limit=200):
    try:
        app_label, model_name = model_path.split('.')
        return list(apps.get_model(app_label, model_name).objects.all().order_by(order_by)[:limit])
    except Exception:  # noqa: BLE001
        return []


@staff_member_required
def coupons_list(request):
    rows = _safe_list('marketing.Coupon')
    return render(
        request,
        'marketing/dashboard/list.html',
        {
            'rows': rows,
            'title': 'Coupons',
            'columns': ['code', 'discount_type', 'discount_value', 'is_active'],
            'active_nav': 'marketing',
        },
    )


@staff_member_required
def campaigns_list(request):
    rows = _safe_list('marketing.EmailCampaign')
    return render(
        request,
        'marketing/dashboard/list.html',
        {
            'rows': rows,
            'title': 'Campaigns',
            'columns': ['name', 'channel', 'state', 'created_at'],
            'active_nav': 'marketing',
        },
    )
