"""Marketplace dashboard sub-routes (mounted under /dashboard/marketplace/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.marketplace import customer_panel, dashboard

app_name = 'marketplace_dashboard'

urlpatterns = [
    path('vendors/<uuid:vendor_id>/', dashboard.vendor_detail, name='vendor_detail'),
    # Staff-gated toggle for the customer-detail Vendor panel.
    path(
        'customer/<uuid:customer_id>/toggle-vendor/',
        customer_panel.toggle_vendor,
        name='toggle_vendor',
    ),
]
