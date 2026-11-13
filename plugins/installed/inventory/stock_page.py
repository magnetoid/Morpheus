"""The Stock page (Products → Inventory → Stock): every counted stock row across
products, with the low and out filters, and a box per row to set the units on
hand. The write is ``InventoryService.set_quantity``, the one the product's
Stock card and Linda's ``inventory.set_stock`` use.
"""

from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db.models import Q, prefetch_related_objects
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.authz import require_capability

_WHOLE_NUMBER = re.compile(r'\d{1,9}')


def _filtered(request):
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        low_stock_threshold,
        stock_rows,
    )

    rows = stock_rows()
    status = (request.GET.get('status') or '').strip()
    if status == 'out':
        rows = rows.filter(free__lte=0)
    elif status == 'low':
        rows = rows.filter(free__lte=low_stock_threshold())
    else:
        status = ''
    warehouse = (request.GET.get('warehouse') or '').strip()
    if warehouse:
        try:
            rows = rows.filter(warehouse_id=warehouse)
        except (ValueError, ValidationError):
            warehouse = ''
    search = (request.GET.get('q') or '').strip()[:80]
    if search:
        rows = rows.filter(
            Q(variant__product__name__icontains=search)
            | Q(variant__sku__icontains=search)
            | Q(variant__product__sku__icontains=search)
        )
    return rows, status, warehouse, search


@require_capability('inventory.read')
def _show(request):
    from plugins.installed.admin_dashboard.views_split._shared import (  # noqa: PLC0415
        paginate_and_sort,
    )
    from plugins.installed.catalog.variants import has_only_default_variant  # noqa: PLC0415
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import low_stock_threshold  # noqa: PLC0415

    rows, status, warehouse, search = _filtered(request)
    page_obj, paging_ctx = paginate_and_sort(
        request,
        rows,
        default_sort='variant__product__name',
        allowed_sorts=('variant__product__name', 'quantity', 'free'),
        default_per_page=50,
    )
    page_rows = list(page_obj.object_list)
    prefetch_related_objects(page_rows, 'variant__product__variants')
    threshold = low_stock_threshold()
    for row in page_rows:
        product = row.variant.product
        row.show_variant = not has_only_default_variant(product, product.variants.all())
        row.state = 'out' if row.free <= 0 else 'low' if row.free <= threshold else ''
    return render(
        request,
        'inventory/dashboard/stock.html',
        {
            'rows': page_rows,
            'status_filter': status,
            'warehouse_filter': warehouse,
            'search': search,
            'warehouses': Warehouse.objects.filter(is_active=True).order_by('name'),
            'low_stock_threshold': threshold,
            'active_nav': 'products',
            **paging_ctx,
        },
    )


@require_capability('inventory.write')
def _save(request):
    from plugins.installed.inventory.services import InventoryService, stock_rows  # noqa: PLC0415

    back = HttpResponseRedirect(request.get_full_path())
    raw = (request.POST.get('quantity') or '').strip()
    if not _WHOLE_NUMBER.fullmatch(raw):
        messages.error(request, 'Enter the units on hand as a whole number, 0 or more.')
        return back
    try:
        level = stock_rows().filter(pk=request.POST.get('level') or None).first()
    except (ValueError, ValidationError):
        level = None
    if level is None:
        messages.error(request, 'That stock row is not counted: its warehouse is switched off.')
        return back
    InventoryService.set_quantity(
        level.variant,
        level.warehouse,
        int(raw),
        reason='Set on the Stock page',
        user=request.user,
    )
    messages.success(
        request, f'{level.variant.product.name}: {raw} on hand in {level.warehouse.name}.'
    )
    return back


@staff_member_required
def stock_view(request):
    return (_save if request.method == 'POST' else _show)(request)
