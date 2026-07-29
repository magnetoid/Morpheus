"""Dashboard views contributed by advanced_ecommerce."""

from __future__ import annotations

import logging

from morpheus.plugin.views import HttpRequest, HttpResponse, render, staff_member_required

logger = logging.getLogger('morpheus.advanced_ecommerce')


@staff_member_required
def low_stock_view(request: HttpRequest) -> HttpResponse:
    """List variants whose available stock is below the configured threshold."""
    from plugins.installed.inventory.models import StockLevel
    from plugins.registry import plugin_registry

    plugin = plugin_registry.get('advanced_ecommerce')
    threshold = int(plugin.get_config_value('low_stock_threshold', 5)) if plugin else 5

    rows = []
    qs = StockLevel.objects.select_related('variant', 'variant__product', 'warehouse')
    for sl in qs[:500]:
        if sl.available_quantity <= threshold:
            rows.append(sl)
    rows.sort(key=lambda sl: sl.available_quantity)

    return render(
        request,
        'advanced_ecommerce/dashboard/low_stock.html',
        {
            'active_nav': 'apps',
            'rows': rows,
            'threshold': threshold,
        },
    )
