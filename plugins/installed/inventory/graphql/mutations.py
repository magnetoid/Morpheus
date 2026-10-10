"""Inventory GraphQL mutations — staff-only.

Stock is tracked on (ProductVariant, Warehouse) pairs.

setStock(): replace the absolute quantity.
adjustStock(): add or subtract a delta. Useful for "decrement by 1
after a manual sale" style updates.

If no warehouse is specified the first warehouse (lowest id) is used.
"""

from __future__ import annotations

import strawberry

from api.graphql_permissions import mutation_scope_error as _check_scope


@strawberry.type
class StockMutationResult:
    variant_sku: str
    warehouse: str
    quantity: int
    reserved_quantity: int
    available: int
    error: str


def _err(msg: str) -> StockMutationResult:
    return StockMutationResult(
        variant_sku='',
        warehouse='',
        quantity=0,
        reserved_quantity=0,
        available=0,
        error=msg,
    )


def _resolve_variant(variant_sku: str, product_slug: str):
    from plugins.installed.catalog.models import Product, ProductVariant

    if variant_sku:
        return ProductVariant.objects.filter(sku=variant_sku).first()
    if product_slug:
        product = Product.objects.filter(slug=product_slug).first()
        if product is None:
            return None
        return product.variants.first()
    return None


def _resolve_warehouse(name: str):
    from plugins.installed.inventory.models import Warehouse

    if name:
        return Warehouse.objects.filter(name=name).first()
    return Warehouse.objects.order_by('id').first()


def _serialize_stock(s) -> StockMutationResult:
    return StockMutationResult(
        variant_sku=s.variant.sku or str(s.variant_id),
        warehouse=getattr(s.warehouse, 'name', '') or '',
        quantity=s.quantity,
        reserved_quantity=s.reserved_quantity,
        available=max(0, s.quantity - s.reserved_quantity),
        error='',
    )


@strawberry.input
class SetStockInput:
    quantity: int
    variant_sku: str = ''
    product_slug: str = ''
    warehouse: str = ''


@strawberry.input
class AdjustStockInput:
    delta: int
    variant_sku: str = ''
    product_slug: str = ''
    warehouse: str = ''


@strawberry.type
class InventoryMutationExtension:
    @strawberry.mutation(
        description='Replace the absolute stock quantity for a variant. Staff-only.',
    )
    def set_stock(self, info: strawberry.Info, input: SetStockInput) -> StockMutationResult:
        err = _check_scope(info, ['inventory.write'])
        if err:
            return _err(err)
        if input.quantity < 0:
            return _err('quantity must be >= 0')

        from plugins.installed.inventory.models import StockLevel

        variant = _resolve_variant(input.variant_sku, input.product_slug)
        if variant is None:
            return _err('variant not found (provide variant_sku or product_slug)')
        warehouse = _resolve_warehouse(input.warehouse)
        if warehouse is None:
            return _err('no warehouse configured')

        stock, _ = StockLevel.objects.get_or_create(
            variant=variant,
            warehouse=warehouse,
            defaults={'quantity': 0},
        )
        stock.quantity = input.quantity
        stock.save(update_fields=['quantity', 'updated_at'])
        return _serialize_stock(stock)

    @strawberry.mutation(
        description='Add or subtract from the current stock quantity. Staff-only.',
    )
    def adjust_stock(self, info: strawberry.Info, input: AdjustStockInput) -> StockMutationResult:
        err = _check_scope(info, ['inventory.write'])
        if err:
            return _err(err)

        from plugins.installed.inventory.models import StockLevel

        variant = _resolve_variant(input.variant_sku, input.product_slug)
        if variant is None:
            return _err('variant not found (provide variant_sku or product_slug)')
        warehouse = _resolve_warehouse(input.warehouse)
        if warehouse is None:
            return _err('no warehouse configured')

        stock, _ = StockLevel.objects.get_or_create(
            variant=variant,
            warehouse=warehouse,
            defaults={'quantity': 0},
        )
        new_qty = stock.quantity + input.delta
        if new_qty < 0:
            return _err(
                f'adjust would put quantity below zero (current={stock.quantity}, delta={input.delta})'
            )
        stock.quantity = new_qty
        stock.save(update_fields=['quantity', 'updated_at'])
        return _serialize_stock(stock)
