"""Inventory URLs — mounted at the storefront root via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.inventory import views

app_name = 'inventory'

urlpatterns = [
    path(
        'back-in-stock/subscribe/<uuid:product_id>/',
        views.back_in_stock_subscribe,
        name='back_in_stock_subscribe',
    ),
]
