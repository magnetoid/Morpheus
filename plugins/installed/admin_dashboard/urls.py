"""Dashboard URL config.

The `apps/<plugin>/` namespace is dynamic — every contributed
`DashboardPage` becomes a route there. The router is mounted at
import time and re-checks the registry per request, so plugins enabled
later light up without a server restart (as long as the plugin's
`ready()` was called once).
"""
from __future__ import annotations

import importlib
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import path

from plugins.installed.admin_dashboard import views

app_name = 'admin_dashboard'


def _resolve_view(view_or_path: Any):
    if callable(view_or_path):
        return view_or_path
    if not isinstance(view_or_path, str) or '.' not in view_or_path:
        return None
    module_name, _, attr = view_or_path.rpartition('.')
    try:
        return getattr(importlib.import_module(module_name), attr)
    except (ImportError, AttributeError):
        return None


@staff_member_required
def plugin_page_router(request: HttpRequest, plugin: str, slug: str) -> HttpResponse:
    """Dispatch /dashboard/apps/<plugin>/<slug>/ to a contributed view."""
    from plugins.registry import plugin_registry

    for page in plugin_registry.dashboard_pages():
        if page.plugin == plugin and page.slug == slug:
            view = _resolve_view(page.view)
            if view is None:
                raise Http404('Plugin page view could not be resolved.')
            return view(request)
    raise Http404('No such plugin page.')


@staff_member_required
def plugin_settings_view(request: HttpRequest, plugin: str) -> HttpResponse:
    from plugins.registry import plugin_registry
    from django.shortcuts import render

    panel = plugin_registry.settings_panel(plugin)
    instance = plugin_registry.get(plugin)
    if panel is None or instance is None:
        raise Http404('Plugin settings panel not found.')

    if request.method == 'POST':
        # Naive merchant-form save: pull declared keys out of POST and
        # persist them via plugin.set_config. Type coercion is best-effort.
        for key, prop in (panel.schema.get('properties') or {}).items():
            if key not in request.POST:
                continue
            raw = request.POST[key]
            value: Any = raw
            ptype = prop.get('type')
            if ptype == 'boolean':
                value = raw in ('on', 'true', '1', 'yes')
            elif ptype == 'integer':
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    continue
            elif ptype == 'number':
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
            instance.set_config(key, value)
        return redirect(request.path)

    config = instance.get_config()
    fields = []
    for key, prop in (panel.schema.get('properties') or {}).items():
        ptype = prop.get('type', 'string')
        kind = 'enum' if 'enum' in prop else ptype
        value = config.get(key, prop.get('default', ''))
        if kind == 'boolean':
            value = bool(value)
        fields.append({
            'key': key,
            'title': prop.get('title') or key.replace('_', ' ').title(),
            'description': prop.get('description', ''),
            'kind': kind,
            'enum': prop.get('enum') or [],
            'value': value,
        })
    return render(request, 'admin_dashboard/plugin_settings.html', {
        'plugin': instance,
        'panel': panel,
        'fields': fields,
        'active_nav': 'apps',
    })


urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('orders/', views.orders_list, name='orders'),
    path('orders/new/', views.order_new, name='order_new'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/action/', views.order_action, name='order_action'),
    path('orders/<str:order_number>/refund/', views.order_refund, name='order_refund'),
    path('orders/<str:order_number>/fulfill/', views.order_fulfill, name='order_fulfill'),
    path('products/', views.products_list, name='products'),
    path('products/new/', views.product_new, name='product_new'),
    path('products/<uuid:product_id>/', views.product_edit, name='product_edit'),
    path('products/<uuid:product_id>/delete/', views.product_delete, name='product_delete'),
    path('products/<uuid:product_id>/variants/new/', views.variant_new, name='variant_new'),
    path('products/<uuid:product_id>/variants/<uuid:variant_id>/', views.variant_edit, name='variant_edit'),
    path('products/<uuid:product_id>/variants/<uuid:variant_id>/delete/', views.variant_delete, name='variant_delete'),
    path('products/<uuid:product_id>/images/upload/', views.image_upload, name='image_upload'),
    path('products/<uuid:product_id>/images/<uuid:image_id>/delete/', views.image_delete, name='image_delete'),
    path('products/<uuid:product_id>/images/<uuid:image_id>/primary/', views.image_set_primary, name='image_set_primary'),
    path('customers/', views.customers_list, name='customers'),
    path('customers/new/', views.customer_new, name='customer_new'),
    path('customers/<uuid:customer_id>/', views.customer_edit, name='customer_edit'),
    path('customers/<uuid:customer_id>/delete/', views.customer_delete, name='customer_delete'),
    path('customers/<uuid:customer_id>/addresses/new/', views.address_new, name='address_new'),
    path('customers/<uuid:customer_id>/addresses/<uuid:address_id>/', views.address_edit, name='address_edit'),
    path('customers/<uuid:customer_id>/addresses/<uuid:address_id>/delete/', views.address_delete, name='address_delete'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('marketing/', views.marketing_view, name='marketing'),
    path('marketing/coupons/new/', views.coupon_new, name='coupon_new'),
    path('marketing/coupons/<uuid:coupon_id>/', views.coupon_edit, name='coupon_edit'),
    path('marketing/coupons/<uuid:coupon_id>/delete/', views.coupon_delete, name='coupon_delete'),
    path('apps/', views.apps_view, name='apps'),
    path('apps/<str:plugin>/settings/', plugin_settings_view, name='plugin_settings'),
    path('apps/<str:plugin>/<slug:slug>/', plugin_page_router, name='plugin_page'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/ai/probe/', views.settings_ai_probe, name='settings_ai_probe'),
    path('settings/<slug:category>/', views.settings_category, name='settings_category'),
    path('ai-insights/', views.ai_insights, name='ai_insights'),
]
