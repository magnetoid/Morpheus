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
                    # FAIL CLOSED. This runs under ORDER_RESERVE_STOCK fired with
                    # raise_errors=True (orders/services.py:602) precisely so a
                    # reservation that cannot be confirmed aborts the order.
                    # Swallowing it here let checkout proceed believing stock was
                    # held — a silent oversell on any DB hiccup. Surfaced as
                    # InsufficientStockError so the caller's existing
                    # can't-fulfil path handles it, rather than a raw DB error.
                    raise InsufficientStockError(
                        f'Could not confirm reservation for variant {item.variant_id} '
                        f'on {order.order_number}: {e}'
                    ) from e
        return movements

    @classmethod
    def release_reservation(cls, order) -> int:
        """Undo the reservations made by `reserve_for_order`.

        Idempotent, like its siblings: `Order.cancel` accepts any source state,
        so a cancelled order can be cancelled (and ORDER_CANCELLED fired) again.
        Releasing twice would subtract this order's units a second time and
        free holds that belong to other orders.
        """
        if StockMovement.objects.filter(
            movement_type='unreserve',
            reference=order.order_number,
        ).exists():
            return 0
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


# ── Availability, for anything that describes a product to the outside ──
# Stock lives per variant per warehouse, so "is this product available" has no
# single row to read — four call sites each rolled their own aggregate, and the
# shared feed vocabulary read `stock_status` / `is_in_stock`, neither of which
# exists on catalog.Product. It therefore answered "in stock" for everything,
# and every product page and channel feed repeated that.


def product_availability(product) -> str:  # noqa: PLR0911 — one early answer per case
    """An availability token for ``product`` — the vocabulary key, not a URL.

    One of: in_stock · out_of_stock · backorder · discontinued.
    Returns '' when this app cannot tell, so the caller keeps its own default
    rather than inheriting a guess dressed up as an answer.

    A product is in stock when ANY of its variants has stock available, or when
    a variant is set to accept backorders — that is what the cart will let a
    shopper do, and markup has to match the cart.
    """
    if product is None:
        return ''
    if str(getattr(product, 'status', '') or '') == 'archived':
        return 'discontinued'
    # The cart refuses an unpriced product (orders.CartService.add_item), so
    # the page and the feeds must not call it in stock either.
    if _is_unpriced(product):
        return 'out_of_stock'
    # The merchant said not to count this one. Nothing below can override that.
    if getattr(product, 'track_inventory', True) is False:
        return 'in_stock'
    pk = getattr(product, 'pk', None)
    if pk is None:
        return ''
    try:
        return _availability_from_stock(pk)
    except Exception:  # noqa: BLE001 — an unmigrated DB must not change the answer
        return ''


def _is_unpriced(product) -> bool:
    """No price to sell at: the product's own price is 0 and no active variant has one.

    Queried rather than read off ``product``: pages load products with
    ``.only()``, and a deferred djmoney field raises ``KeyError`` on access.
    """
    from plugins.installed.catalog.models import Product, ProductVariant

    pk = getattr(product, 'pk', None)
    if pk is None:
        return False
    try:
        own = Product.objects.filter(pk=pk).values_list('price', flat=True).first()
        if own is None or own > 0:
            return False
        return not ProductVariant.objects.filter(
            product_id=pk, is_active=True, price__gt=0
        ).exists()
    except Exception:  # noqa: BLE001 — never change the answer over a failed lookup
        return False


def _availability_from_stock(product_pk) -> str:
    from django.db.models import F, Sum

    from plugins.installed.catalog.models import ProductVariant

    variants = list(
        ProductVariant.objects.filter(product_id=product_pk, is_active=True).values_list(
            'id', 'inventory_policy'
        )
    )
    if not variants:
        # No variants means nothing to track; the product is purchasable.
        return 'in_stock'
    rows = (
        StockLevel.objects.filter(variant_id__in=[v[0] for v in variants])
        .values('variant_id')
        .annotate(qty=Sum(F('quantity') - F('reserved_quantity')))
    )
    by_variant = {row['variant_id']: (row['qty'] or 0) for row in rows}

    # A variant with NO stock rows is UNTRACKED, not depleted. Reading an empty
    # aggregate as zero is how this function first shipped, and it declared a
    # whole store out of stock: the shop had no StockLevel rows at all, so every
    # product summed to nothing and every page said sold out while the add-to-cart
    # button worked. Absence of measurement is not a measurement of absence.
    tracked = [(vid, policy) for vid, policy in variants if vid in by_variant]
    if not tracked:
        return 'in_stock'
    if any(by_variant.get(vid, 0) > 0 for vid, _policy in tracked):
        return 'in_stock'
    # An untracked sibling is still buyable even when the tracked ones are empty.
    if len(tracked) < len(variants):
        return 'in_stock'
    # Nothing on hand — but a backorder-friendly variant is still buyable.
    if any(policy == 'continue' for _vid, policy in tracked):
        return 'backorder'
    return 'out_of_stock'


def variant_availability(variant) -> str:
    """An availability token for ONE variant.

    Same rules as `product_availability`, applied to a single row: a variant
    with no stock records is untracked rather than empty, and a variant that
    accepts backorders is buyable even at zero.
    """
    from django.db.models import F, Sum

    if variant is None:
        return ''
    product = getattr(variant, 'product', None)
    if product is not None and getattr(product, 'track_inventory', True) is False:
        return 'in_stock'
    if str(getattr(product, 'status', '') or '') == 'archived':
        return 'discontinued'
    try:
        qty = StockLevel.objects.filter(variant=variant).aggregate(
            qty=Sum(F('quantity') - F('reserved_quantity'))
        )['qty']
    except Exception:  # noqa: BLE001 — an unmigrated DB must not change the answer
        return ''
    if qty is None or qty > 0:
        return 'in_stock'  # None = untracked, not empty
    return 'backorder' if getattr(variant, 'inventory_policy', '') == 'continue' else 'out_of_stock'
