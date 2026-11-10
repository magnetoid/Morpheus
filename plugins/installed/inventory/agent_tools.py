"""Inventory tools the agent layer can call."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='inventory.low_stock_report',
    description='List products whose total stock is below `threshold`.',
    scopes=['inventory.read'],
    schema={
        'type': 'object',
        'properties': {
            'threshold': {'type': 'integer', 'minimum': 0, 'maximum': 1000, 'default': 5},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def low_stock_report_tool(*, threshold: int = 5, limit: int = 25) -> ToolResult:
    from django.db.models import F, Sum

    from plugins.installed.inventory.models import StockLevel

    threshold = max(0, int(threshold or 5))
    limit = max(1, min(int(limit or 25), 100))
    rows = (
        StockLevel.objects.values(
            'variant__product__name',
            'variant__product__slug',
            'variant__sku',
        )
        .annotate(available=Sum(F('quantity') - F('reserved_quantity')))
        .filter(available__lte=threshold)
        .order_by('available')[:limit]
    )
    out = [
        {
            'product': r['variant__product__name'],
            'slug': r['variant__product__slug'],
            'variant_sku': r['variant__sku'],
            'available': r['available'] or 0,
        }
        for r in rows
    ]
    return ToolResult(
        output={'threshold': threshold, 'low_stock': out},
        display=f'{len(out)} item(s) at or below {threshold}',
    )


def _variant(code: str, *, create: bool = False):
    from plugins.installed.inventory.services import resolve_variant  # noqa: PLC0415

    variant = resolve_variant(code, create=create)
    if variant is None:
        raise ToolError(
            f'No variant or one-form product with SKU or slug {code!r} '
            '(a product with several variants needs the variant SKU).'
        )
    return variant


def _warehouse(code: str, *, create_default: bool = False):
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import default_warehouse  # noqa: PLC0415

    code = (code or '').strip()
    if not code:
        found = default_warehouse(create=create_default)
        if found is None:
            raise ToolError('The store has no warehouse yet; create one first.')
        return found
    found = (
        Warehouse.objects.filter(code__iexact=code).first()
        or Warehouse.objects.filter(name__iexact=code).first()
    )
    if found is None:
        raise ToolError(f'Unknown warehouse: {code}')
    return found


@tool(
    name='inventory.stock_levels',
    description=(
        'Stock of one product or variant per warehouse: on hand, held for open '
        'orders, free, and whether it keeps selling at 0 (backorders). Give a '
        'variant SKU, or the SKU or slug of a product sold in one form.'
    ),
    scopes=['inventory.read'],
    schema={
        'type': 'object',
        'properties': {
            'sku': {'type': 'string', 'description': 'Variant SKU, product SKU or slug'}
        },
        'required': ['sku'],
    },
)
def stock_levels_tool(*, sku: str) -> ToolResult:
    from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

    variant = _variant(sku)
    levels = list(
        StockLevel.objects.filter(variant=variant)
        .select_related('warehouse')
        .order_by('-warehouse__is_default', 'warehouse__name')
    )
    rows = [
        {
            'warehouse': sl.warehouse.code,
            'on_hand': sl.quantity,
            'held': sl.reserved_quantity,
            'free': sl.available_quantity,
            'active': sl.warehouse.is_active,
        }
        for sl in levels
    ]
    tracked = bool(variant.product.track_inventory) and bool(levels)
    return ToolResult(
        output={
            'variant_sku': variant.sku,
            'product': variant.product.name,
            'counted': tracked,
            'backorders': variant.inventory_policy == 'continue',
            'levels': rows,
        },
        display=(
            f'{variant.sku}: {sum(r["free"] for r in rows)} free'
            if tracked
            else f'{variant.sku}: stock not counted'
        ),
    )


@tool(
    name='inventory.warehouses',
    description='List the warehouses: code, name, default, on or off, units on hand.',
    scopes=['inventory.read'],
    schema={'type': 'object', 'properties': {}},
)
def warehouses_tool() -> ToolResult:
    from django.db.models import Sum  # noqa: PLC0415

    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

    rows = [
        {
            'code': w.code,
            'name': w.name,
            'default': w.is_default,
            'active': w.is_active,
            'on_hand': w.units or 0,
        }
        for w in Warehouse.objects.annotate(units=Sum('stock_levels__quantity'))
    ]
    return ToolResult(output={'warehouses': rows}, display=f'{len(rows)} warehouse(s)')


@tool(
    name='inventory.adjust_stock',
    description=(
        'Change on-hand stock for a variant in a warehouse by `delta` (a delivery '
        'in, a write-off out); never below 0. Leaves a movement in the audit log.'
    ),
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'variant_sku': {'type': 'string'},
            'warehouse_code': {'type': 'string'},
            'delta': {'type': 'integer'},
            'reason': {'type': 'string'},
        },
        'required': ['variant_sku', 'warehouse_code', 'delta'],
    },
    requires_approval=True,
)
def adjust_stock_tool(
    *, variant_sku: str, warehouse_code: str, delta: int, reason: str = ''
) -> ToolResult:
    from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

    variant = _variant(variant_sku, create=True)
    warehouse = _warehouse(warehouse_code)
    level = InventoryService.adjust(
        variant, warehouse, int(delta), reason=reason or 'Changed by Linda'
    )
    return ToolResult(
        output={
            'variant_sku': variant.sku,
            'warehouse': warehouse.code,
            'new_quantity': level.quantity,
            'reason': reason,
        },
        display=f'{variant.sku} @ {warehouse.code}: now {level.quantity}',
    )


@tool(
    name='inventory.set_stock',
    description=(
        'Set the counted units on hand of a variant (or a product sold in one form) '
        'in a warehouse, e.g. after a stock count. Starts counting stock for it '
        'there. No warehouse = the default warehouse (made if the store has none). '
        'Leaves a movement in the audit log.'
    ),
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'sku': {'type': 'string', 'description': 'Variant SKU, product SKU or slug'},
            'quantity': {'type': 'integer', 'minimum': 0},
            'warehouse_code': {'type': 'string', 'description': 'Warehouse code or name'},
            'reason': {'type': 'string'},
            # The names agent_core's copy of this tool took until v0.152.0.
            'variant_sku': {'type': 'string'},
            'product_slug': {'type': 'string'},
            'warehouse': {'type': 'string'},
        },
        'required': ['quantity'],
    },
    requires_approval=True,
)
def set_stock_tool(
    *,
    quantity: int,
    sku: str = '',
    warehouse_code: str = '',
    reason: str = '',
    variant_sku: str = '',
    product_slug: str = '',
    warehouse: str = '',
) -> ToolResult:
    from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

    code = sku or variant_sku or product_slug
    if not code:
        raise ToolError('Give the variant SKU, or the SKU or slug of the product.')
    if int(quantity) < 0:
        raise ToolError('quantity must be 0 or more')
    variant = _variant(code, create=True)
    warehouse = _warehouse(warehouse_code or warehouse, create_default=True)
    level = InventoryService.set_quantity(
        variant, warehouse, int(quantity), reason=reason or 'Set by Linda'
    )
    note = '' if variant.product.track_inventory else ' (tracking is off for this product)'
    return ToolResult(
        output={
            'variant_sku': variant.sku,
            'warehouse': warehouse.code,
            'on_hand': level.quantity,
            'counted': bool(variant.product.track_inventory),
        },
        display=f'{variant.sku} @ {warehouse.code}: {level.quantity} on hand{note}',
    )


@tool(
    name='inventory.transfer_stock',
    description=(
        'Move free units of a variant from one warehouse to another in one step. '
        'Units held for open orders cannot be moved.'
    ),
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'sku': {'type': 'string', 'description': 'Variant SKU, product SKU or slug'},
            'from_code': {'type': 'string'},
            'to_code': {'type': 'string'},
            'quantity': {'type': 'integer', 'minimum': 1},
            'reason': {'type': 'string'},
        },
        'required': ['sku', 'from_code', 'to_code', 'quantity'],
    },
    requires_approval=True,
)
def transfer_stock_tool(
    *, sku: str, from_code: str, to_code: str, quantity: int, reason: str = ''
) -> ToolResult:
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        InsufficientStockError,
        InventoryService,
    )

    variant = _variant(sku)
    source, destination = _warehouse(from_code), _warehouse(to_code)
    try:
        moved = InventoryService.transfer(
            variant, source, destination, int(quantity), reason=reason or 'Moved by Linda'
        )
    except (InsufficientStockError, ValueError) as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={
            'variant_sku': variant.sku,
            'from': source.code,
            'to': destination.code,
            'moved': moved,
        },
        display=f'Moved {moved}× {variant.sku}: {source.code} → {destination.code}',
    )


@tool(
    name='inventory.create_warehouse',
    description='Add a warehouse (a place stock is kept). Optionally make it the default.',
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'code': {'type': 'string', 'description': 'Short code; made from the name if empty'},
            'make_default': {'type': 'boolean', 'default': False},
        },
        'required': ['name'],
    },
    requires_approval=True,
)
def create_warehouse_tool(*, name: str, code: str = '', make_default: bool = False) -> ToolResult:
    from plugins.installed.inventory.services import create_warehouse  # noqa: PLC0415

    try:
        warehouse = create_warehouse(name, code, make_default=bool(make_default))
    except ValueError as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={'code': warehouse.code, 'name': warehouse.name, 'default': warehouse.is_default},
        display=f'Warehouse {warehouse.name} ({warehouse.code}) added',
    )


@tool(
    name='inventory.list_back_in_stock_subs',
    description='List unsent back-in-stock notification subscriptions.',
    scopes=['inventory.read'],
    schema={'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 50}}},
)
def list_back_in_stock_tool(*, limit: int = 50) -> ToolResult:
    from plugins.installed.inventory.models import BackInStockSubscription

    rows = list(
        BackInStockSubscription.objects.filter(notified_at__isnull=True).select_related('product')[
            : max(1, min(int(limit or 50), 200))
        ]
    )
    return ToolResult(
        output={
            'subscriptions': [
                {
                    'product': s.product.name,
                    'slug': s.product.slug,
                    'email': s.email,
                    'created_at': s.created_at.isoformat(),
                }
                for s in rows
            ],
        }
    )


@tool(
    name='catalog.schedule_price_change',
    description='Schedule a price change for a product. Becomes active at `effective_at`.',
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'new_price': {'type': 'number'},
            'currency': {'type': 'string', 'default': 'USD'},
            'effective_at_iso': {'type': 'string', 'description': 'ISO-8601 datetime UTC'},
            'note': {'type': 'string'},
        },
        'required': ['slug', 'new_price', 'effective_at_iso'],
    },
    requires_approval=True,
)
def schedule_price_change_tool(
    *,
    slug: str,
    new_price: float,
    effective_at_iso: str,
    currency: str = 'USD',
    note: str = '',
) -> ToolResult:
    from datetime import datetime
    from decimal import Decimal

    from djmoney.money import Money

    from plugins.installed.catalog.models import PriceSchedule, Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    try:
        when = datetime.fromisoformat(effective_at_iso.replace('Z', '+00:00'))
    except ValueError as e:
        raise ToolError(f'Bad effective_at_iso: {e}') from e
    sched = PriceSchedule.objects.create(
        product=product,
        new_price=Money(Decimal(str(new_price)), currency),
        effective_at=when,
        note=note[:240],
    )
    return ToolResult(
        output={
            'schedule_id': str(sched.id),
            'product': product.name,
            'new_price': str(new_price),
            'effective_at': when.isoformat(),
        },
        display=f'Price change for {product.name} → {new_price} at {when}',
    )


@tool(
    name='inventory.stockout_forecast',
    description=(
        'List SKUs predicted to stock out within N days, with days of cover, '
        'daily velocity and a suggested reorder quantity. Velocity-based — unlike '
        'inventory.low_stock_report which is a static threshold.'
    ),
    scopes=['inventory.read'],
    schema={
        'type': 'object',
        'properties': {
            'threshold_days': {'type': 'integer', 'minimum': 1, 'maximum': 90, 'default': 14},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def stockout_forecast_tool(*, threshold_days: int = 14, limit: int = 25) -> ToolResult:
    from plugins.installed.inventory.demand_forecast import forecast_all  # noqa: PLC0415

    threshold_days = max(1, min(int(threshold_days or 14), 90))
    limit = max(1, min(int(limit or 25), 100))
    all_rows = forecast_all(threshold_days=threshold_days)
    rows = [r for r in all_rows if r.reorder_recommended][:limit]
    overstock_rows = [r for r in all_rows if r.overstocked][:limit]
    out = [
        {
            'product': r.variant_label,
            'available': r.available,
            'days_of_cover': r.days_until_stockout,
            'daily_velocity': round(r.daily_velocity, 2),
            'suggested_reorder_qty': r.suggested_reorder_qty,
        }
        for r in rows
    ]
    overstock = [
        {
            'product': r.variant_label,
            'available': r.available,
            'days_of_cover': r.days_until_stockout,
            'daily_velocity': round(r.daily_velocity, 2),
        }
        for r in overstock_rows
    ]
    return ToolResult(
        output={'threshold_days': threshold_days, 'at_risk': out, 'overstock': overstock},
        display=f'{len(out)} at-risk · {len(overstock)} overstocked',
    )
