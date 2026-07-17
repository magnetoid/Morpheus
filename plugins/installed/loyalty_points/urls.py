"""Storefront URLs owned by the loyalty plugin.

Mounted at the site root (prefix='') by ``register_urls`` in
``plugin.ready()``. Because the route is registered by the plugin, it is
only present when the plugin is enabled — disabling loyalty_points makes
``/account/points/`` 404 (modular-os disable test).
"""

from __future__ import annotations

from django.urls import path

from plugins.installed.loyalty_points import views

app_name = 'loyalty_points'

urlpatterns = [
    path('account/points/', views.account_points, name='account_points'),
    path('checkout/points/apply/', views.apply_points, name='apply_points'),
    path('checkout/points/remove/', views.remove_points, name='remove_points'),
]
