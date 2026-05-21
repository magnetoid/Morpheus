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
def apps_view(request: HttpRequest) -> HttpResponse:
    from plugins.registry import plugin_registry

    if request.method == 'POST':
        return _toggle_plugin(request)

    plugins = []
    for name, cls in sorted(plugin_registry._classes.items()):
        instance = plugin_registry.get(name)
        plugins.append({
            'name': name,
            'label': getattr(cls, 'label', name),
            'description': getattr(cls, 'description', ''),
            'version': getattr(cls, 'version', ''),
            'active': plugin_registry.is_active(name),
            'pages': [p for p in plugin_registry.dashboard_pages() if p.plugin == name],
            'has_settings': plugin_registry.settings_panel(name) is not None,
        })
    return render(request, 'admin_dashboard/apps.html', {
        'plugins': plugins,
        'active_nav': 'apps',
    })


@staff_member_required
def apps_store_view(request: HttpRequest) -> HttpResponse:
    """Browse + install surface for community apps.

    Reads from a static registry today
    (`plugins/installed/admin_dashboard/data/apps_registry.json`); future
    iterations point this at a remote index. Each entry carries enough
    metadata for the merchant to decide + a copy-pasteable install
    command. Auto-install via pip + manifest mutation is a separate PR;
    this is the MVP browse surface.

    Installed apps (status='installed') are detected against the live
    plugin registry so the UI shows a green badge instead of an install
    button. Anything in the JSON that's not yet a real plugin renders
    with 'planned' or 'available' status.
    """
    import json
    import os
    from plugins.registry import plugin_registry

    registry_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'apps_registry.json',
    )
    apps_data = {'apps': []}
    try:
        with open(registry_path) as fh:
            apps_data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning('apps_store: registry read failed: %s', exc)

    installed_names = set(plugin_registry._classes.keys())
    rows = []
    for app in apps_data.get('apps', []):
        slug = (app.get('slug') or '').strip()
        # The slug is also the plugin's `name` if it ships as a Morpheus
        # plugin — installed check on the registry confirms.
        is_installed = slug.replace('-', '_') in installed_names
        rows.append({**app, 'is_installed': is_installed})

    # Group by category for the page layout.
    categories: dict[str, list] = {}
    for r in rows:
        cat = r.get('category') or 'Other'
        categories.setdefault(cat, []).append(r)

    return render(request, 'admin_dashboard/apps_store.html', {
        'categories': sorted(categories.items()),
        'total': len(rows),
        'installed_count': sum(1 for r in rows if r['is_installed']),
        'registry_version': apps_data.get('version', '?'),
        'registry_updated_at': apps_data.get('updated_at', ''),
        'active_nav': 'apps',
    })


def _toggle_plugin(request: HttpRequest):
    """POST handler on the apps page: flip a plugin's enabled state in DB."""
    from morpheus.views import redirect

    name = request.POST.get('plugin', '').strip()
    desired = request.POST.get('enabled') == '1'
    try:
        from plugins.models import PluginConfig
        row, _ = PluginConfig.objects.get_or_create(plugin_name=name)
        row.is_enabled = desired
        row.save(update_fields=['is_enabled', 'updated_at'])
    except Exception as e:  # noqa: BLE001 — DB outage shouldn't crash the page
        logger.warning('admin_dashboard: toggle %s failed: %s', name, e, exc_info=True)
    return redirect('admin_dashboard:apps')


# ── Settings ──────────────────────────────────────────────────────────────────


