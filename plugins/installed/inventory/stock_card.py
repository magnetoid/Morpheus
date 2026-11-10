"""The "Stock" card on the dashboard's product form (PRODUCT_FORM_CARDS /
PRODUCT_FORM_SAVED): units on hand per variant and warehouse, and whether a
variant keeps selling once none is left.

Until v0.152.0 no dashboard page could enter a stock quantity; only Linda or
the API could. A product sold in one form gets its default variant here
(``catalog.variants.ensure_stock_variant``) the first time stock is entered,
and a store with no warehouse gets "Main warehouse".
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.inventory')

NEW = 'new'
CAPABILITY = 'inventory.write'


def may_change_stock(user) -> bool:
    """Whether the card takes this person's numbers. The product form asks for
    ``catalog.write`` only, and stock is ``inventory.write``, as on the
    Warehouses page and in the API; like every capability it denies only while
    the store enforces roles."""
    from core import authz  # noqa: PLC0415

    return authz.enforcement_mode() != authz.MODE_ENFORCE or authz.has_capability(user, CAPABILITY)


def _stocked_variants(product) -> list:
    """The variants that count stock: active ones that ship (a download or a
    service has nothing on a shelf)."""
    return [
        v
        for v in product.variants.all()
        if v.is_active and (v.variant_type or 'physical') == 'physical'
    ]


def card(product, user=None) -> dict | None:
    """The card's context, or None when the product has no stock to count. A
    person who may not change stock sees the numbers and no boxes to change."""
    from plugins.installed.catalog.variants import UNSTOCKED_TYPES  # noqa: PLC0415
    from plugins.installed.inventory.models import StockLevel, Warehouse  # noqa: PLC0415

    if product is None or not getattr(product, 'pk', None):
        return None
    if product.product_type in UNSTOCKED_TYPES:
        return None
    variants = _stocked_variants(product)
    if not variants and product.product_type == 'variable':
        return None  # nothing to count until it has a variant that ships
    warehouses = list(Warehouse.objects.filter(is_active=True).order_by('-is_default', 'name'))
    columns = [{'key': str(w.pk), 'name': w.name, 'code': w.code} for w in warehouses] or [
        {'key': NEW, 'name': 'Main warehouse', 'code': ''}
    ]
    levels = {
        (str(sl.variant_id), str(sl.warehouse_id)): sl
        for sl in StockLevel.objects.filter(variant__in=variants)
    }
    rows = []
    for v in variants or [None]:
        key = str(v.pk) if v is not None else NEW
        cells, reserved = [], 0
        for col in columns:
            sl = levels.get((key, col['key']))
            reserved += sl.reserved_quantity if sl else 0
            cells.append(
                {
                    'name': f'stock__{key}__{col["key"]}',
                    'value': sl.quantity if sl else '',
                    'label': f'{v.name if v else product.name} in {col["name"]}',
                }
            )
        rows.append(
            {
                'key': key,
                'label': v.name if v is not None else product.name,
                'sku': v.sku if v is not None else (product.sku or ''),
                'backorder': bool(v is not None and v.inventory_policy == 'continue'),
                'reserved': reserved,
                'cells': cells,
            }
        )
    return {
        'stock_columns': columns,
        'stock_rows': rows,
        'stock_tracked': bool(product.track_inventory),
        'stock_own_toggle': product.product_type == 'variable',
        'stock_locked': not may_change_stock(user),
    }


def save(product, post, user=None) -> None:
    """Write what the card posted. A form without the card leaves stock alone;
    an empty box leaves that warehouse as it was."""
    if product is None or post is None or 'stock_submitted' not in post:
        return
    from core import authz  # noqa: PLC0415

    if not authz.check(user, CAPABILITY, target=f'product:{product.pk}'):
        return
    # A variable product's form hides the shell's "Track inventory" box (it sits in
    # a card for one-form products, and a hidden box still posts its old value), so
    # this card carries its own. Decided here by type, never by what was posted.
    if product.product_type == 'variable' and 'stock_track_submitted' in post:
        track = bool(post.get('stock_track'))
        if product.track_inventory != track:
            product.track_inventory = track
            product.save(update_fields=['track_inventory'])
    variants = {str(v.pk): v for v in _stocked_variants(product)}
    made = _save_quantities(product, post, variants, user)
    if made is not None:
        variants[NEW] = made
    for key in post.getlist('stock_rows'):
        variant = variants.get(key)
        if variant is None:
            continue
        policy = 'continue' if post.get(f'backorder__{key}') else 'deny'
        if variant.inventory_policy != policy:
            variant.inventory_policy = policy
            variant.save(update_fields=['inventory_policy', 'updated_at'])


def _save_quantities(product, post, variants: dict, user):
    """Each filled box becomes that variant's units in that warehouse. Returns
    the default variant when this save made it."""
    from plugins.installed.catalog.variants import ensure_stock_variant  # noqa: PLC0415
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
    from plugins.installed.inventory.services import (  # noqa: PLC0415
        InventoryService,
        default_warehouse,
    )

    made = None
    for name in post:
        parts = name.split('__')
        raw = (post.get(name) or '').strip()
        if parts[0] != 'stock' or len(parts) != 3 or not raw:
            continue
        try:
            quantity = int(raw)
        except ValueError:
            logger.warning('inventory: stock card ignored %r=%r', name, raw)
            continue
        if parts[1] == NEW:
            made = made or ensure_stock_variant(product)
        variant = made if parts[1] == NEW else variants.get(parts[1])
        warehouse = (
            default_warehouse(create=True)
            if parts[2] == NEW
            else Warehouse.objects.filter(pk=parts[2]).first()
        )
        if variant is not None and warehouse is not None:
            InventoryService.set_quantity(
                variant, warehouse, quantity, reason='Set on the product page', user=user
            )
    return made
