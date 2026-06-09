"""Storefront route owned by digital_products — present only while enabled.

Mounted at the site root (prefix='') by ``register_urls`` in ``plugin.ready()``,
so disabling the plugin makes ``/account/downloads/`` 404 (the disable test).
"""

from __future__ import annotations

from django.urls import path

from plugins.installed.digital_products import storefront_views

app_name = 'digital_products_account'

urlpatterns = [
    path('account/downloads/', storefront_views.account_downloads, name='account_downloads'),
]
