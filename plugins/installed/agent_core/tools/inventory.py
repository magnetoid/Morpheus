"""Inventory tools — set / adjust stock per variant.

Both tools target a single (variant, warehouse) pair. Variants are
looked up by SKU OR by product slug → first variant (most simple
products have exactly one variant). Warehouse defaults to the first
configured warehouse when not specified.

Same backing logic as the GraphQL setStock/adjustStock mutations
(plugins.installed.inventory.graphql.mutations) — kept here so LLM
agents can discover and call via /mcp/admin/v1/.
"""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


def _resolve_pair(variant_sku: str, product_slug: str, warehouse_name: str):
    from plugins.installed.catalog.models import Product, ProductVariant
    from plugins.installed.inventory.models import Warehouse

    variant = None
    if variant_sku:
        variant = ProductVariant.objects.filter(sku=variant_sku).first()
    elif product_slug:
        product = Product.objects.filter(slug=product_slug).first()
        if product is None:
            raise ToolError(f'product_slug {product_slug!r} not found')
        variant = product.variants.first()
        if variant is None:
            raise ToolError(f'product {product_slug!r} has no variants')
    if variant is None:
        raise ToolError('provide variant_sku or product_slug')

    warehouse = (
        Warehouse.objects.filter(name=warehouse_name).first()
        if warehouse_name
        else Warehouse.objects.order_by('id').first()
    )
    if warehouse is None:
        raise ToolError('no warehouse configured')
    return variant, warehouse


def _serialize(s) -> dict:
    return {
        'variant_sku': s.variant.sku or str(s.variant_id),
        'warehouse': getattr(s.warehouse, 'name', '') or '',
        'quantity': s.quantity,
        'reserved': s.reserved_quantity,
        'available': max(0, s.quantity - s.reserved_quantity),
    }


@tool(
    name='inventory.set_stock',
    description=(
        'Replace the absolute stock quantity for a variant. Identify the '
        'variant by `variant_sku` (preferred) or by `product_slug` (uses '
        "the product's first variant). Refuses negative quantities. "
        'Returns the new stock level.'
    ),
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'quantity': {'type': 'integer', 'minimum': 0},
            'variant_sku': {'type': 'string'},
            'product_slug': {'type': 'string'},
            'warehouse': {'type': 'string'},
        },
        'required': ['quantity'],
    },
)
def set_stock_tool(
    *,
    quantity: int,
    variant_sku: str = '',
    product_slug: str = '',
    warehouse: str = '',
) -> ToolResult:
    if quantity < 0:
        raise ToolError('quantity must be >= 0')
    from plugins.installed.inventory.models import StockLevel

    variant, wh = _resolve_pair(variant_sku, product_slug, warehouse)
    stock, _ = StockLevel.objects.get_or_create(
        variant=variant,
        warehouse=wh,
        defaults={'quantity': 0},
    )
    stock.quantity = int(quantity)
    stock.save(update_fields=['quantity', 'updated_at'])
    out = _serialize(stock)
    return ToolResult(
        output=out,
        display=f'{out["variant_sku"]} @ {out["warehouse"]}: {out["available"]} available',
    )


@tool(
    name='inventory.adjust_stock',
    description=(
        'Add or subtract from the current stock quantity. Negative delta '
        'decrements. Refuses to drop below zero. Useful for "decrement by '
        '1 after a manual sale" or "restock by 50" style updates.'
    ),
    scopes=['inventory.write'],
    schema={
        'type': 'object',
        'properties': {
            'delta': {'type': 'integer'},
            'variant_sku': {'type': 'string'},
            'product_slug': {'type': 'string'},
            'warehouse': {'type': 'string'},
        },
        'required': ['delta'],
    },
)
def adjust_stock_tool(
    *,
    delta: int,
    variant_sku: str = '',
    product_slug: str = '',
    warehouse: str = '',
) -> ToolResult:
    from plugins.installed.inventory.models import StockLevel

    variant, wh = _resolve_pair(variant_sku, product_slug, warehouse)
    stock, _ = StockLevel.objects.get_or_create(
        variant=variant,
        warehouse=wh,
        defaults={'quantity': 0},
    )
    new_qty = stock.quantity + int(delta)
    if new_qty < 0:
        raise ToolError(f'adjust would drop below zero (current={stock.quantity}, delta={delta})')
    stock.quantity = new_qty
    stock.save(update_fields=['quantity', 'updated_at'])
    out = _serialize(stock)
    return ToolResult(
        output=out,
        display=f'{out["variant_sku"]} @ {out["warehouse"]}: {out["available"]} available (Δ {delta:+d})',
    )
