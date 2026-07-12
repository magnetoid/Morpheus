"""
Inventory service.

LAW 8 — All Stock Changes Are Atomic. Every method that mutates a
StockLevel does so inside `transaction.atomic()` with `select_for_update()`
to prevent race conditions during high-concurrency checkouts.

Public surface
--------------
* `reserve_for_order(order)` — bumps `reserved_quantity` for every order
  item that has a tracked variant. Idempotent on the order id.
* `commit_for_order(order)`  — converts reservations into actual stock
  decrements (called by the payments plugin when payment succeeds).
* `release_reservation(order)` — undoes reservations on cancel.
* `available(variant)` — sum across warehouses of `quantity - reserved`.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from django.db import DatabaseError, transaction

from plugins.installed.inventory.models import StockLevel, StockMovement

logger = logging.getLogger('morpheus.inventory')


class InsufficientStockError(RuntimeError):
    """Raised when a reservation would exceed available_quantity."""


class InventoryService:
    @classmethod
    def available(cls, variant) -> int:
        """Total reservable units across all warehouses for one variant."""
        return sum(sl.available_quantity for sl in StockLevel.objects.filter(variant=variant))

    @classmethod
    def is_in_stock(cls, variant, qty: int = 1) -> bool:
        return cls.available(variant) >= qty

    @classmethod
    def reserve_for_order(cls, order) -> int:
        """
        Reserve stock for every order item that points at a tracked variant.
        Idempotent: reservations are tagged in StockMovement.reference with
        the order's number, so re-running on the same order is a no-op.

        Returns the number of stock movements written.
        """
        if not order.items.exists():
            return 0
        # Idempotency check.
        if StockMovement.objects.filter(
            movement_type='reserve',
            reference=order.order_number,
        ).exists():
            return 0

        from plugins.installed.inventory.allocator import plan_allocation

        movements = 0
        for item in order.items.select_related('variant').all():
            if item.variant_id is None or item.quantity <= 0:
                continue
            plan = plan_allocation(item.variant_id, item.quantity)
            if not plan:
                # An empty plan is ambiguous: either (a) NO StockLevel exists —
                # the variant is untracked, so skip; or (b) StockLevels exist but
                # nothing is available (fully reserved / zero on hand) — a genuine
                # stockout that MUST block the order. The old code skipped both,
                # so a sold-out tracked variant sailed through → oversell.
                if StockLevel.objects.filter(variant_id=item.variant_id).exists():
                    raise InsufficientStockError(
                        f'Out of stock for variant {item.variant_id}: '
                        f'wanted {item.quantity}, none available'
                    )
                logger.warning(
                    'inventory: no StockLevel for variant %s on order %s',
                    item.variant_id,
                    order.order_number,
                )
                continue
            allocated = sum(a.qty for a in plan)
            if allocated < item.quantity:
                raise InsufficientStockError(
                    f'Short stock for variant {item.variant_id}: '
                    f'wanted {item.quantity}, allocated {allocated}'
                )
            for alloc in plan:
                try:
                    with transaction.atomic():
                        sl = StockLevel.objects.select_for_update().get(pk=alloc.stock_level.pk)
                        if sl.available_quantity < alloc.qty:
                            raise InsufficientStockError(
                                f'Lost race on level {sl.pk}: wanted {alloc.qty}, '
                                f'available {sl.available_quantity}'
                            )
                        sl.reserved_quantity = (sl.reserved_quantity or 0) + alloc.qty
                        sl.save(update_fields=['reserved_quantity', 'updated_at'])
                        StockMovement.objects.create(
                            stock_level=sl,
                            movement_type='reserve',
                            quantity_change=0,
                            quantity_before=sl.quantity,
                            quantity_after=sl.quantity,
                            reference=order.order_number,
                            notes=f'Reserved {alloc.qty}× for {order.order_number}',
                        )
                        movements += 1
                except DatabaseError as e:
                    logger.error(
                        'inventory: reserve failed for order=%s variant=%s level=%s: %s',
                        order.order_number,
                        item.variant_id,
                        alloc.stock_level.pk,
                        e,
                        exc_info=True,
                    )
        return movements

    @classmethod
    def release_reservation(cls, order) -> int:
        """Undo the reservations made by `reserve_for_order`."""
        movements = 0
        reservations = StockMovement.objects.filter(
            movement_type='reserve',
            reference=order.order_number,
        )
        if not reservations.exists():
            return 0
        # Group by stock_level to apply once per StockLevel.
        by_level: dict[str, int] = defaultdict(int)
        for mv in reservations.select_related('stock_level'):
            by_level[str(mv.stock_level_id)] += _qty_from_note(mv.notes)
        for level_id, qty in by_level.items():
            if qty <= 0:
                continue
            try:
                with transaction.atomic():
                    sl = StockLevel.objects.select_for_update().get(pk=level_id)
                    sl.reserved_quantity = max(0, (sl.reserved_quantity or 0) - qty)
                    sl.save(update_fields=['reserved_quantity', 'updated_at'])
                    StockMovement.objects.create(
                        stock_level=sl,
                        movement_type='unreserve',
                        quantity_change=0,
                        quantity_before=sl.quantity,
                        quantity_after=sl.quantity,
                        reference=order.order_number,
                        notes=f'Released {qty}× from {order.order_number}',
                    )
                    movements += 1
            except DatabaseError as e:
                logger.error(
                    'inventory: release failed for order=%s level=%s: %s',
                    order.order_number,
                    level_id,
                    e,
                    exc_info=True,
                )
        return movements

    @classmethod
    def commit_for_order(cls, order) -> int:
        """
        Convert reservations into actual stock decrements (after payment).
        Idempotent: a `sale` movement keyed on the order number is only
        written once.
        """
        if StockMovement.objects.filter(
            movement_type='sale',
            reference=order.order_number,
        ).exists():
            return 0
        # Find the levels we previously reserved on.
        reservation_levels = StockMovement.objects.filter(
            movement_type='reserve', reference=order.order_number
        ).select_related('stock_level')
        movements = 0
        seen: set[str] = set()
        for mv in reservation_levels:
            level_key = str(mv.stock_level_id)
            if level_key in seen:
                continue
            seen.add(level_key)
            qty = _qty_from_note(mv.notes)
            if qty <= 0:
                continue
            try:
                with transaction.atomic():
                    sl = StockLevel.objects.select_for_update().get(pk=mv.stock_level_id)
                    sl.reserved_quantity = max(0, (sl.reserved_quantity or 0) - qty)
                    sl.quantity = max(0, sl.quantity - qty)
                    sl.save(update_fields=['reserved_quantity', 'quantity', 'updated_at'])
                    StockMovement.objects.create(
                        stock_level=sl,
                        movement_type='sale',
                        quantity_change=-qty,
                        quantity_before=sl.quantity + qty,
                        quantity_after=sl.quantity,
                        reference=order.order_number,
                        notes=f'Sold {qty}× via {order.order_number}',
                    )
                    movements += 1
            except DatabaseError as e:
                logger.error(
                    'inventory: commit failed for order=%s level=%s: %s',
                    order.order_number,
                    mv.stock_level_id,
                    e,
                    exc_info=True,
                )
        return movements

    @classmethod
    def restock_for_return(cls, return_request) -> int:
        """Add stock back when a return is refunded. Idempotent: a
        ``return`` movement keyed on the RMA number is written
        once and only once, even if the hook fires twice.
        """
        rma = getattr(return_request, 'rma_number', '') or str(return_request.id)
        if StockMovement.objects.filter(
            movement_type='return',
            reference=rma,
        ).exists():
            return 0
        try:
            from plugins.installed.orders.models import OrderItem
        except Exception:  # noqa: BLE001
            return 0
        items_by_id = {
            str(oi.id): oi for oi in OrderItem.objects.filter(order=return_request.order)
        }
        movements = 0
        for entry in return_request.items or []:
            oi = items_by_id.get(str(entry.get('order_item_id', '')))
            if not oi or not getattr(oi, 'variant_id', None):
                continue
            qty = int(entry.get('quantity', 0) or 0)
            if qty <= 0:
                continue
            sl = (
                StockLevel.objects.filter(variant_id=oi.variant_id, warehouse__is_active=True)
                .order_by('-quantity')
                .first()
            )
            if sl is None:
                continue
            try:
                with transaction.atomic():
                    sl = StockLevel.objects.select_for_update().get(pk=sl.pk)
                    before = sl.quantity
                    sl.quantity = sl.quantity + qty
                    sl.save(update_fields=['quantity', 'updated_at'])
                    StockMovement.objects.create(
                        stock_level=sl,
                        movement_type='return',
                        quantity_change=qty,
                        quantity_before=before,
                        quantity_after=sl.quantity,
                        reference=rma,
                        notes=f'Restocked {qty}× from return {rma}',
                    )
                    movements += 1
            except DatabaseError as e:
                logger.warning(
                    'inventory: restock failed rma=%s level=%s: %s',
                    rma,
                    sl.pk,
                    e,
                    exc_info=True,
                )
        return movements


def _qty_from_note(note: str) -> int:
    """Parse `Reserved 2× for ABC` style notes back to the qty."""
    if not note:
        return 0
    # Find the first integer in the note.
    digits = ''
    for ch in note:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return int(digits) if digits else 0
