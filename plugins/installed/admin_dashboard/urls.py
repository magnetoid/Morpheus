"""Dashboard URL config.

The `apps/<plugin>/` namespace is dynamic — every contributed
`DashboardPage` becomes a route there. The router is mounted at
import time and re-checks the registry per request, so plugins enabled
later light up without a server restart (as long as the plugin's
`ready()` was called once).
"""

# ruff: noqa: PLC0415, PLR0912, I001
# Inline imports inside view functions are intentional throughout —
# plugin registry references avoid app-registry-not-ready issues at
# URLconf import time.
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
        # Boolean checkboxes need explicit absence handling — an unchecked
        # box doesn't submit a key at all — but only for AJAX posts where
        # we know the form sent every declared boolean intentionally.
        from django.http import JsonResponse

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        saved: list[str] = []
        for key, prop in (panel.schema.get('properties') or {}).items():
            ptype = prop.get('type')
            if key not in request.POST:
                if is_ajax and ptype == 'boolean':
                    instance.set_config(key, False)
                    saved.append(key)
                continue
            raw = request.POST[key]
            value: Any = raw
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
            saved.append(key)
        if is_ajax:
            return JsonResponse({'ok': True, 'saved': saved})
        # Honor `_next` so a custom landing page (e.g. /dashboard/settings/ai/)
        # can post into this generic save endpoint and bounce the user
        # back to itself instead of the legacy plugin-settings page.
        next_url = (request.POST.get('_next') or '').strip()
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect(request.path)

    config = instance.get_config()
    fields = []
    for key, prop in (panel.schema.get('properties') or {}).items():
        ptype = prop.get('type', 'string')
        kind = 'enum' if 'enum' in prop else ptype
        value = config.get(key, prop.get('default', ''))
        if kind == 'boolean':
            value = bool(value)
        fields.append(
            {
                'key': key,
                'title': prop.get('title') or key.replace('_', ' ').title(),
                'description': prop.get('description', ''),
                'kind': kind,
                'enum': prop.get('enum') or [],
                'value': value,
            }
        )
    return render(
        request,
        'admin_dashboard/plugin_settings.html',
        {
            'plugin': instance,
            'panel': panel,
            'fields': fields,
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': f'{panel.label or instance.label or plugin} settings'},
            ],
        },
    )


@staff_member_required
def plugin_settings_redirect(request: HttpRequest, plugin: str) -> HttpResponse:
    """301 from the legacy /dashboard/apps/<plugin>/settings/ to the new
    canonical /dashboard/settings/<plugin>/. Keeps old bookmarks and
    cards on the apps page working.
    """
    from django.http import HttpResponsePermanentRedirect

    return HttpResponsePermanentRedirect(f'/dashboard/settings/{plugin}/')


urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('me/', views.my_account, name='my_account'),
    path('pulse/refresh/', views.pulse_refresh, name='pulse_refresh'),
    path('pulse/<uuid:insight_id>/dismiss/', views.pulse_dismiss, name='pulse_dismiss'),
    path('orders/', views.orders_list, name='orders'),
    path('orders/bulk/', views.orders_bulk, name='orders_bulk'),
    path('orders/new/', views.order_new, name='order_new'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('orders/<str:order_number>/action/', views.order_action, name='order_action'),
    path('orders/<str:order_number>/refund/', views.order_refund, name='order_refund'),
    path('returns/', views.returns_list, name='returns_list'),
    path('returns/<uuid:rma_id>/', views.return_detail, name='return_detail'),
    path('orders/<str:order_number>/fulfill/', views.order_fulfill, name='order_fulfill'),
    path('products/', views.products_list, name='products'),
    path('products/bulk/', views.products_bulk, name='products_bulk'),
    path('products/content-audit/', views.content_audit, name='content_audit'),
    path(
        'products/<uuid:product_id>/content-fill/', views.content_fill_one, name='content_fill_one'
    ),
    path('products/new/', views.product_new, name='product_new'),
    path('products/<uuid:product_id>/', views.product_edit, name='product_edit'),
    path('products/<uuid:product_id>/delete/', views.product_delete, name='product_delete'),
    path('products/<uuid:product_id>/archive/', views.product_archive, name='product_archive'),
    path('products/<uuid:product_id>/variants/new/', views.variant_new, name='variant_new'),
    path(
        'products/<uuid:product_id>/variants/<uuid:variant_id>/',
        views.variant_edit,
        name='variant_edit',
    ),
    path(
        'products/<uuid:product_id>/variants/<uuid:variant_id>/delete/',
        views.variant_delete,
        name='variant_delete',
    ),
    path('products/<uuid:product_id>/images/upload/', views.image_upload, name='image_upload'),
    path('products/<uuid:product_id>/images/reorder/', views.image_reorder, name='image_reorder'),
    path('products/<uuid:product_id>/videos/new/', views.video_add, name='video_add'),
    path(
        'products/<uuid:product_id>/videos/<uuid:video_id>/delete/',
        views.video_delete,
        name='video_delete',
    ),
    path(
        'products/<uuid:product_id>/videos/<uuid:video_id>/edit/',
        views.video_edit,
        name='video_edit',
    ),
    path(
        'products/<uuid:product_id>/images/<uuid:image_id>/edit/',
        views.image_edit,
        name='image_edit',
    ),
    path(
        'products/<uuid:product_id>/images/<uuid:image_id>/delete/',
        views.image_delete,
        name='image_delete',
    ),
    path(
        'products/<uuid:product_id>/images/<uuid:image_id>/primary/',
        views.image_set_primary,
        name='image_set_primary',
    ),
    path('categories/', views.categories_list, name='categories'),
    path('collections/', views.collections_list, name='collections'),
    path('collections/new/', views.collection_new, name='collection_new'),
    path('collections/<uuid:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path(
        'collections/<uuid:collection_id>/delete/',
        views.collection_delete,
        name='collection_delete',
    ),
    path('customers/', views.customers_list, name='customers'),
    path('customers/bulk/', views.customers_bulk, name='customers_bulk'),
    path('customers/new/', views.customer_new, name='customer_new'),
    path('customers/<uuid:customer_id>/', views.customer_edit, name='customer_edit'),
    path('customers/<uuid:customer_id>/delete/', views.customer_delete, name='customer_delete'),
    path('customers/<uuid:customer_id>/addresses/new/', views.address_new, name='address_new'),
    path(
        'customers/<uuid:customer_id>/addresses/<uuid:address_id>/',
        views.address_edit,
        name='address_edit',
    ),
    path(
        'customers/<uuid:customer_id>/addresses/<uuid:address_id>/delete/',
        views.address_delete,
        name='address_delete',
    ),
    path('analytics/', views.analytics_view, name='analytics'),
    path('marketing/', views.marketing_view, name='marketing'),
    path('marketing/coupons/new/', views.coupon_new, name='coupon_new'),
    path('marketing/coupons/<uuid:coupon_id>/', views.coupon_edit, name='coupon_edit'),
    path('marketing/coupons/<uuid:coupon_id>/delete/', views.coupon_delete, name='coupon_delete'),
    path('apps/', views.apps_view, name='apps'),
    path('apps/store/', views.apps_store_view, name='apps_store'),
    # Legacy URL — 301-redirects to the new canonical /dashboard/settings/<plugin>/.
    # Name kept as `plugin_settings` for backward-compat with templates
    # (notably apps.html, which surfaces the per-plugin Settings button).
    path('apps/<str:plugin>/settings/', plugin_settings_redirect, name='plugin_settings'),
    path('apps/<str:plugin>/<slug:slug>/', plugin_page_router, name='plugin_page'),
    path('palette/search/', views.palette_search, name='palette_search'),
    path('ai/draft-description/', views.ai_draft_description, name='ai_draft_description'),
    path('ai/rewrite-email/', views.ai_rewrite_email, name='ai_rewrite_email'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/ai/probe/', views.settings_ai_probe, name='settings_ai_probe'),
    path('settings/email-templates/', views.email_templates_list, name='email_templates_list'),
    path(
        'settings/email-templates/<str:key>/', views.email_template_edit, name='email_template_edit'
    ),
    path('settings/<slug:category>/', views.settings_category, name='settings_category'),
    path('ai-insights/', views.ai_insights, name='ai_insights'),
    # Theme builder — section composer + live preview for CMS pages.
    path('pages/<uuid:page_id>/builder/', views.theme_builder_views.builder, name='theme_builder'),
    path(
        'pages/<uuid:page_id>/builder/add/',
        views.theme_builder_views.api_add,
        name='theme_builder_add',
    ),
    path(
        'pages/<uuid:page_id>/builder/reorder/',
        views.theme_builder_views.api_reorder,
        name='theme_builder_reorder',
    ),
    path(
        'pages/<uuid:page_id>/builder/<uuid:row_id>/update/',
        views.theme_builder_views.api_update,
        name='theme_builder_update',
    ),
    path(
        'pages/<uuid:page_id>/builder/<uuid:row_id>/delete/',
        views.theme_builder_views.api_delete,
        name='theme_builder_delete',
    ),
    # Self-improvement engine (sprint Phase 1 Increment 5).
    path(
        'system/self-improvement/',
        views.self_improvement_views.overview,
        name='self_improvement',
    ),
    path(
        'system/self-improvement/<int:recommendation_id>/approve/',
        views.self_improvement_views.approve,
        name='self_improvement_approve',
    ),
    path(
        'system/self-improvement/<int:recommendation_id>/reject/',
        views.self_improvement_views.reject,
        name='self_improvement_reject',
    ),
    path(
        'system/self-improvement/<int:recommendation_id>/snooze/',
        views.self_improvement_views.snooze,
        name='self_improvement_snooze',
    ),
]
