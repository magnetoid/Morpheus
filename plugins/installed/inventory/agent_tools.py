"""Inventory tools the agent layer can call."""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


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


@tool(
    name='inventory.adjust_stock',
    description='Adjust on-hand stock for a variant in a warehouse. Positive `delta` adds stock; negative subtracts.',
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
    from django.db import transaction

    from plugins.installed.catalog.models import ProductVariant
    from plugins.installed.inventory.models import StockLevel, Warehouse

    try:
        variant = ProductVariant.objects.get(sku=variant_sku)
    except ProductVariant.DoesNotExist as e:
        raise ToolError(f'Unknown variant SKU: {variant_sku}') from e
    try:
        warehouse = Warehouse.objects.get(code=warehouse_code)
    except Warehouse.DoesNotExist as e:
        raise ToolError(f'Unknown warehouse code: {warehouse_code}') from e

    delta = int(delta)
    with transaction.atomic():
        level, _ = StockLevel.objects.select_for_update().get_or_create(
            variant=variant,
            warehouse=warehouse,
            defaults={'quantity': 0, 'reserved_quantity': 0},
        )
        new_qty = max(0, level.quantity + delta)
        level.quantity = new_qty
        level.save(update_fields=['quantity'])
    return ToolResult(
        output={
            'variant_sku': variant_sku,
            'warehouse': warehouse_code,
            'new_quantity': new_qty,
            'reason': reason,
        },
        display=f'{variant_sku} @ {warehouse_code}: now {new_qty}',
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
    rows = [r for r in forecast_all(threshold_days=threshold_days) if r.reorder_recommended][:limit]
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
    return ToolResult(
        output={'threshold_days': threshold_days, 'at_risk': out},
        display=f'{len(out)} SKU(s) projected to stock out within {threshold_days}d',
    )
