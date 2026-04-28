"""Dashboard views contributed by advanced_ecommerce."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from morpheus.views import staff_member_required
from morpheus.views import HttpRequest, HttpResponse
from morpheus.views import redirect, render
from djmoney.money import Money

logger = logging.getLogger('morpheus.advanced_ecommerce')


@staff_member_required
def bulk_price_view(request: HttpRequest) -> HttpResponse:
    """Apply a percent change to the price of every active product."""
    from plugins.installed.catalog.models import Product

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')
        try:
            pct = Decimal(request.POST.get('percent', '0'))
        except InvalidOperation:
            pct = Decimal('0')
        product_ids = request.POST.getlist('products')
        qs = Product.objects.filter(status='active')
        if product_ids:
            qs = qs.filter(pk__in=product_ids)

        preview_rows = []
        for product in qs[:200]:
            old = product.price.amount if product.price else Decimal('0')
            new = (old * (Decimal('1') + pct / Decimal('100'))).quantize(Decimal('0.01'))
            preview_rows.append({'product': product, 'old': old, 'new': new})

        if action == 'apply' and pct != 0:
            count = 0
            for row in preview_rows:
                product = row['product']
                product.price = Money(row['new'], product.price.currency if product.price else 'USD')
                product.save(update_fields=['price', 'updated_at'])
                count += 1
            logger.info('advanced_ecommerce: bulk repriced %s products by %s%%', count, pct)
            return redirect(request.path)

        return render(request, 'advanced_ecommerce/dashboard/bulk_price.html', {
            'active_nav': 'apps',
            'preview_rows': preview_rows,
            'percent': pct,
        })

    return render(request, 'advanced_ecommerce/dashboard/bulk_price.html', {
        'active_nav': 'apps',
        'preview_rows': [],
        'percent': Decimal('0'),
    })


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

    return render(request, 'advanced_ecommerce/dashboard/low_stock.html', {
        'active_nav': 'apps',
        'rows': rows,
        'threshold': threshold,
    })
