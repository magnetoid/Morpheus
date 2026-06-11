"""Multi-warehouse stock allocator.

Pure function — given a variant and a desired quantity, returns a list
of (StockLevel, qty_to_take) tuples that satisfy the request, preferring
to fulfill from a single warehouse when possible.

Strategies:
  * `single_warehouse`: pick the smallest warehouse that has the full qty
    on its own. Falls back to multi if none does.
  * `default_first`: drain the default warehouse first, spill to others
    by descending available_quantity.
  * `descending_stock` (default): drain warehouses by descending
    available_quantity until the order is filled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from plugins.installed.inventory.models import StockLevel

logger = logging.getLogger('morpheus.inventory.allocator')


@dataclass
class Allocation:
    stock_level: StockLevel
    qty: int


def plan_allocation(
    variant_id,
    qty: int,
    *,
    strategy: str = 'descending_stock',
    prefer_warehouse_code: str | None = None,
) -> list[Allocation]:
    """Return an allocation plan that totals `qty` (or fewer if short)."""
    if qty <= 0:
        return []
    levels = list(
        StockLevel.objects.select_related('warehouse').filter(
            variant_id=variant_id, warehouse__is_active=True
        )
    )
    if not levels:
        return []
    levels = [sl for sl in levels if sl.available_quantity > 0]
    if not levels:
        return []

    if prefer_warehouse_code:
        levels.sort(
            key=lambda sl: (sl.warehouse.code != prefer_warehouse_code, -sl.available_quantity)
        )
    elif strategy == 'single_warehouse':
        single = sorted(
            (sl for sl in levels if sl.available_quantity >= qty),
            key=lambda sl: sl.available_quantity,
        )
        if single:
            return [Allocation(stock_level=single[0], qty=qty)]
        levels.sort(key=lambda sl: -sl.available_quantity)
    elif strategy == 'default_first':
        levels.sort(key=lambda sl: (not sl.warehouse.is_default, -sl.available_quantity))
    else:  # descending_stock
        levels.sort(key=lambda sl: -sl.available_quantity)

    plan: list[Allocation] = []
    remaining = qty
    for sl in levels:
        take = min(sl.available_quantity, remaining)
        if take <= 0:
            continue
        plan.append(Allocation(stock_level=sl, qty=take))
        remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        logger.warning(
            'allocator: short by %d for variant=%s (asked %d)',
            remaining,
            variant_id,
            qty,
        )
    return plan
