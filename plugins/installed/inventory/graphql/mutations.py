"""Inventory GraphQL mutations — staff-only.

Stock is tracked on (ProductVariant, Warehouse) pairs.

setStock(): replace the absolute quantity.
adjustStock(): add or subtract a delta. Useful for "decrement by 1
after a manual sale" style updates.

Both write through ``InventoryService`` (a movement in the audit log, the
low-stock alert). No warehouse given = the default one; setStock makes "Main
warehouse" for a store that has none.
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


def _resolve_variant(variant_sku: str, product_slug: str, *, create: bool = False):
    """The variant to count: by its SKU, or a one-form product by slug (its
    default variant, made when ``create``). A product with several variants
    needs the variant's SKU; until v0.152.0 its first variant was taken."""
    from plugins.installed.inventory.services import resolve_variant  # noqa: PLC0415

    code = (variant_sku or product_slug or '').strip()
    return resolve_variant(code, create=create) if code else None


def _resolve_warehouse(name: str, *, create: bool = False):
    """A warehouse by code or name; none given = the default one."""
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import default_warehouse  # noqa: PLC0415

    name = (name or '').strip()
    if name:
        return (
            Warehouse.objects.filter(code__iexact=name).first()
            or Warehouse.objects.filter(name__iexact=name).first()
        )
    return default_warehouse(create=create)


def _person(info):
    user = getattr(getattr(info.context, 'request', None), 'user', None)
    return user if getattr(user, 'is_authenticated', False) else None


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

        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        variant = _resolve_variant(input.variant_sku, input.product_slug, create=True)
        if variant is None:
            return _err('variant not found (provide variant_sku or product_slug)')
        warehouse = _resolve_warehouse(input.warehouse, create=True)
        if warehouse is None:
            return _err('warehouse not found')
        stock = InventoryService.set_quantity(
            variant, warehouse, input.quantity, reason='Set over the API', user=_person(info)
        )
        return _serialize_stock(stock)

    @strawberry.mutation(
        description='Add or subtract from the current stock quantity. Staff-only.',
    )
    def adjust_stock(self, info: strawberry.Info, input: AdjustStockInput) -> StockMutationResult:
        err = _check_scope(info, ['inventory.write'])
        if err:
            return _err(err)

        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415
        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        variant = _resolve_variant(input.variant_sku, input.product_slug)
        if variant is None:
            return _err('variant not found (provide variant_sku or product_slug)')
        warehouse = _resolve_warehouse(input.warehouse)
        if warehouse is None:
            return _err('no warehouse configured')
        current = (
            StockLevel.objects.filter(variant=variant, warehouse=warehouse)
            .values_list('quantity', flat=True)
            .first()
            or 0
        )
        if current + input.delta < 0:
            return _err(
                f'adjust would put quantity below zero (current={current}, delta={input.delta})'
            )
        stock = InventoryService.adjust(
            variant, warehouse, input.delta, reason='Changed over the API', user=_person(info)
        )
        return _serialize_stock(stock)
