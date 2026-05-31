"""Storefront-facing B2B URLs."""

from __future__ import annotations

from django.urls import path

from plugins.installed.b2b import views_bulk_order

app_name = 'b2b'

urlpatterns = [
    path('bulk-order/', views_bulk_order.bulk_order, name='bulk_order'),
]
