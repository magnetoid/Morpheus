"""The Warehouses page (Settings → Shipping & delivery → Warehouses): the places
stock is kept, which one is the default, switching one off, and moving stock
between them. Every write goes through ``InventoryService`` or the warehouse
helpers in ``services.py``, the same ones Linda's tools use.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.authz import require_capability
from morpheus.app import dashboard_trail

#: Movements the page lists: what a person did, not the holds every order makes.
_SHOWN_MOVEMENTS = ('adjustment', 'transfer', 'receive', 'damage', 'return', 'sale')


def _warehouse_from(request):
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

    pk = (request.POST.get('warehouse_id') or '').strip()
    found = Warehouse.objects.filter(pk=pk).first() if pk else None
    if found is None:
        messages.error(request, 'Warehouse not found.')
    return found


def _create(request) -> None:
    from plugins.installed.inventory.services import create_warehouse  # noqa: PLC0415

    try:
        w = create_warehouse(
            request.POST.get('name') or '',
            request.POST.get('code') or '',
            make_default=bool(request.POST.get('is_default')),
        )
    except ValueError as e:
        messages.error(request, str(e))
        return
    messages.success(request, f'Warehouse "{w.name}" ({w.code}) added.')


def _edit(request) -> None:
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        make_default_warehouse,
        warehouse_code,
    )

    w = _warehouse_from(request)
    if w is None:
        return
    name = (request.POST.get('name') or '').strip()[:200]
    code = warehouse_code(request.POST.get('code') or w.code)
    if not name or not code:
        messages.error(request, 'A warehouse needs a name and a code.')
        return
    if Warehouse.objects.filter(code=code).exclude(pk=w.pk).exists():
        messages.error(request, f'The code {code} is taken by another warehouse.')
        return
    w.name, w.code = name, code
    w.save(update_fields=['name', 'code'])
    if request.POST.get('is_default') and not w.is_default:
        make_default_warehouse(w)
    messages.success(request, f'Warehouse "{w.name}" saved.')


def _make_default(request) -> None:
    from plugins.installed.inventory.services import make_default_warehouse  # noqa: PLC0415

    w = _warehouse_from(request)
    if w is not None:
        make_default_warehouse(w)
        messages.success(request, f'"{w.name}" is the default warehouse now.')


def _toggle(request) -> None:
    w = _warehouse_from(request)
    if w is None:
        return
    w.is_active = not w.is_active
    if not w.is_active:
        w.is_default = False
    w.save(update_fields=['is_active', 'is_default'])
    if w.is_active:
        messages.success(request, f'"{w.name}" is on: its stock can be sold again.')
    else:
        messages.success(
            request,
            f'"{w.name}" is off: its stock is no longer sold. Orders already holding '
            'units there keep them.',
        )


def _delete(request) -> None:
    """Only an empty warehouse can go: deleting one deletes its stock rows and
    their movement history with them. One that holds stock is switched off."""
    w = _warehouse_from(request)
    if w is None:
        return
    if w.stock_levels.exists():
        messages.error(
            request,
            f'"{w.name}" has stock records, and deleting it would delete their history. '
            'Move its stock out and switch it off instead.',
        )
        return
    name = w.name
    w.delete()
    messages.success(request, f'Warehouse "{name}" deleted.')


def _transfer(request) -> None:
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        InsufficientStockError,
        InventoryService,
        resolve_variant,
    )

    sku = (request.POST.get('sku') or '').strip()
    variant = resolve_variant(sku)
    if variant is None:
        messages.error(
            request,
            f'No variant or one-form product with SKU or slug "{sku}" '
            '(a product with several variants needs the variant SKU).',
        )
        return
    source = Warehouse.objects.filter(pk=request.POST.get('from_id') or None).first()
    destination = Warehouse.objects.filter(pk=request.POST.get('to_id') or None).first()
    if source is None or destination is None:
        messages.error(request, 'Pick the warehouse to move from and the one to move to.')
        return
    try:
        quantity = int(request.POST.get('quantity') or 0)
        moved = InventoryService.transfer(
            variant,
            source,
            destination,
            quantity,
            reason=(request.POST.get('reason') or '').strip()[:500],
            user=request.user,
        )
    except (InsufficientStockError, ValueError) as e:
        messages.error(request, str(e) if str(e) else 'Enter how many units to move.')
        return
    messages.success(
        request, f'Moved {moved}× {variant.sku} from {source.name} to {destination.name}.'
    )


_ACTIONS = {
    'create': _create,
    'edit': _edit,
    'default': _make_default,
    'toggle': _toggle,
    'delete': _delete,
    'transfer': _transfer,
}


@staff_member_required
@require_capability('inventory.write')
def warehouses(request):
    from plugins.installed.inventory.models import StockMovement, Warehouse  # noqa: PLC0415

    if request.method == 'POST':
        handler = _ACTIONS.get((request.POST.get('action') or '').strip())
        if handler is not None:
            handler(request)
        return HttpResponseRedirect(request.path)

    rows = list(
        Warehouse.objects.annotate(
            on_hand=Sum('stock_levels__quantity'),
            held=Sum('stock_levels__reserved_quantity'),
            stocked=Count('stock_levels', filter=Q(stock_levels__quantity__gt=0)),
            records=Count('stock_levels'),
        ).order_by('-is_active', '-is_default', 'name')
    )
    edit_id = (request.GET.get('edit') or '').strip()
    editing = next((w for w in rows if str(w.pk) == edit_id), None)
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        low_stock_levels,
        low_stock_threshold,
    )

    movements = list(
        StockMovement.objects.filter(movement_type__in=_SHOWN_MOVEMENTS)
        .select_related('stock_level__variant__product', 'stock_level__warehouse', 'created_by')
        .order_by('-created_at')[:30]
    )
    return render(
        request,
        'inventory/dashboard/warehouses.html',
        {
            'warehouse_rows': rows,
            'active_warehouses': [w for w in rows if w.is_active],
            'editing': editing,
            'movements': movements,
            'low_stock': low_stock_levels(),
            'low_stock_threshold': low_stock_threshold(),
            'active_nav': 'shipping',
            'breadcrumb_trail': dashboard_trail(
                'Shipping', '/dashboard/shipping/zones/', {'label': 'Warehouses'}
            ),
        },
    )
