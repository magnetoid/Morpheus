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
* `set_quantity` / `adjust` / `transfer` — every stock write a person, Linda,
  an import or a transfer makes: a movement in the audit log for each, and
  the low-stock events when stock crosses its line.
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
        """Total reservable units across the switched-on warehouses for one
        variant (the allocator takes from those only)."""
        return sum(
            sl.available_quantity
            for sl in StockLevel.objects.filter(variant=variant, warehouse__is_active=True)
        )

    @classmethod
    def is_in_stock(cls, variant, qty: int = 1) -> bool:
        return cls.available(variant) >= qty

    @classmethod
    def reserve_for_order(cls, order) -> int:
        """
        Reserve stock for every order item that points at a tracked variant.
        Idempotent: reservations are tagged in StockMovement.reference with
        the order's number, so re-running on the same order is a no-op.

        A line counts the stock of its variant, or, when it names none, of its
        product's one stock variant (``catalog.variants.stock_variant``). A
        product whose merchant switched tracking off is never counted, whatever
        stock rows it has: its pages call it in stock, so checkout must too. A
        variant that accepts backorders (``inventory_policy='continue'``) takes
        what is free and the rest is noted on the order's timeline.

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
        backordered: list[tuple] = []
        for item in order.items.select_related('variant', 'product').all():
            if item.quantity <= 0:
                continue
            variant = _line_variant(item)
            if variant is None:
                continue
            plan = plan_allocation(variant.pk, item.quantity)
            allocated = sum(a.qty for a in plan)
            if allocated < item.quantity:
                # An empty plan is ambiguous: either (a) NO StockLevel exists —
                # the variant is untracked, so skip; or (b) StockLevels exist but
                # not enough is available (fully reserved / zero on hand) — a
                # genuine stockout that MUST block the order, unless the variant
                # takes backorders. The old code skipped both, so a sold-out
                # tracked variant sailed through → oversell.
                if not StockLevel.objects.filter(variant_id=variant.pk).exists():
                    logger.warning(
                        'inventory: no StockLevel for variant %s on order %s',
                        variant.pk,
                        order.order_number,
                    )
                    continue
                if getattr(variant, 'inventory_policy', 'deny') != 'continue':
                    raise InsufficientStockError(
                        f'Short stock for variant {variant.pk}: '
                        f'wanted {item.quantity}, available {allocated}'
                    )
                backordered.append((variant, item.quantity - allocated))
            for alloc in plan:
                try:
                    with transaction.atomic():
                        sl = StockLevel.objects.select_for_update().get(pk=alloc.stock_level.pk)
                        if sl.available_quantity < alloc.qty:
                            raise InsufficientStockError(
                                f'Lost race on level {sl.pk}: wanted {alloc.qty}, '
                                f'available {sl.available_quantity}'
                            )
                        before = sl.available_quantity
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
                        _announce(sl.pk, before, sl.available_quantity)
                        movements += 1
                except DatabaseError as e:
                    logger.error(
                        'inventory: reserve failed for order=%s variant=%s level=%s: %s',
                        order.order_number,
                        variant.pk,
                        alloc.stock_level.pk,
                        e,
                        exc_info=True,
                    )
                    # FAIL CLOSED. This runs under ORDER_RESERVE_STOCK fired with
                    # raise_errors=True (orders/services.py) precisely so a
                    # reservation that cannot be confirmed aborts the order.
                    # Swallowing it here let checkout proceed believing stock was
                    # held — a silent oversell on any DB hiccup. Surfaced as
                    # InsufficientStockError so the caller's existing
                    # can't-fulfil path handles it, rather than a raw DB error.
                    raise InsufficientStockError(
                        f'Could not confirm reservation for variant {variant.pk} '
                        f'on {order.order_number}: {e}'
                    ) from e
        for variant, short in backordered:
            order.log_event(
                'backordered',
                f'{short}× {variant.sku} ordered beyond the stock on hand; '
                'it ships once it is restocked.',
            )
        return movements

    # ── Stock written by people and tools ─────────────────────────────────
    # Every write a merchant, Linda, an import or a transfer makes goes through
    # ``set_quantity`` / ``adjust`` / ``transfer``: each leaves a movement in the
    # audit log and tells the low-stock subscribers once when stock crosses the
    # line. ``inventory.adjust_stock`` used to save the level directly, so a
    # tool's change left no trace.

    @classmethod
    def set_quantity(
        cls, variant, warehouse, quantity: int, *, reason: str = '', reference: str = '', user=None
    ):
        """Make ``quantity`` the units on hand of ``variant`` in ``warehouse``
        (never below 0). A variant with no stock row there gets one, and is
        counted from then on. Returns the StockLevel."""
        return cls._write(
            variant, warehouse, absolute=quantity, reason=reason, reference=reference, user=user
        )

    @classmethod
    def adjust(
        cls, variant, warehouse, delta: int, *, reason: str = '', reference: str = '', user=None
    ):
        """Add ``delta`` units (negative removes; never below 0)."""
        return cls._write(
            variant, warehouse, delta=delta, reason=reason, reference=reference, user=user
        )

    @classmethod
    def _write(
        cls,
        variant,
        warehouse,
        *,
        absolute=None,
        delta=None,
        reason='',
        reference='',
        user=None,
    ):
        with transaction.atomic():
            level, _created = StockLevel.objects.get_or_create(variant=variant, warehouse=warehouse)
            sl = StockLevel.objects.select_for_update().get(pk=level.pk)
            target = int(absolute) if absolute is not None else sl.quantity + int(delta or 0)
            change = max(0, target) - sl.quantity
            if change == 0:
                return sl
            before = sl.available_quantity
            StockMovement.record(
                sl,
                'adjustment',
                change,
                reference=(reference or '')[:200],
                notes=reason or '',
                user=_person(user),
            )
            sl.refresh_from_db()
            _announce(sl.pk, before, sl.available_quantity)
            return sl

    @classmethod
    def transfer(
        cls, variant, source, destination, quantity: int, *, reason: str = '', user=None
    ) -> int:
        """Move ``quantity`` free units of ``variant`` from ``source`` to
        ``destination`` in one transaction: two ``transfer`` movements, or none.
        Units held for open orders stay where they are. Returns the units moved."""
        qty = int(quantity)
        if qty <= 0:
            raise ValueError('Move at least one unit.')
        if source.pk == destination.pk:
            raise ValueError('Pick two different warehouses.')
        reference = f'Transfer {source.code} → {destination.code}'[:200]
        with transaction.atomic():
            StockLevel.objects.get_or_create(variant=variant, warehouse=destination)
            levels = {
                sl.warehouse_id: sl
                for sl in StockLevel.objects.select_for_update()
                .filter(variant=variant, warehouse__in=[source, destination])
                .order_by('pk')
            }
            src, dst = levels.get(source.pk), levels[destination.pk]
            free = src.available_quantity if src is not None else 0
            if free < qty:
                raise InsufficientStockError(f'{source.name} has {free} free to move, not {qty}.')
            before = src.available_quantity
            for sl, change in ((src, -qty), (dst, qty)):
                had = sl.quantity
                sl.quantity = had + change
                sl.save(update_fields=['quantity', 'updated_at'])
                StockMovement.objects.create(
                    stock_level=sl,
                    movement_type='transfer',
                    quantity_change=change,
                    quantity_before=had,
                    quantity_after=sl.quantity,
                    reference=reference,
                    notes=reason or '',
                    created_by=_person(user),
                )
            _announce(src.pk, before, src.available_quantity)
        return qty

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
        # Sum what this order reserved on each level, as release does: two lines
        # can hold the same level (a line that names no variant and one that
        # names the product's only variant), and counting only the first
        # reservation sold too little and left the rest held forever.
        by_level: dict[str, int] = defaultdict(int)
        for mv in StockMovement.objects.filter(
            movement_type='reserve', reference=order.order_number
        ):
            by_level[str(mv.stock_level_id)] += _qty_from_note(mv.notes)
        movements = 0
        for level_id, qty in by_level.items():
            if qty <= 0:
                continue
            try:
                with transaction.atomic():
                    sl = StockLevel.objects.select_for_update().get(pk=level_id)
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
                    level_id,
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
            str(oi.id): oi
            for oi in OrderItem.objects.filter(order=return_request.order).select_related(
                'variant', 'product'
            )
        }
        movements = 0
        for entry in return_request.items or []:
            oi = items_by_id.get(str(entry.get('order_item_id', '')))
            # The variant the sale took the units from, found the way checkout
            # found it: a line that names no variant sold its product's one.
            variant = _line_variant(oi) if oi else None
            if variant is None:
                continue
            qty = int(entry.get('quantity', 0) or 0)
            if qty <= 0:
                continue
            sl = (
                StockLevel.objects.filter(variant_id=variant.pk, warehouse__is_active=True)
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


def _line_variant(item):
    """The variant whose stock an order line takes, or None when it takes none."""
    product = getattr(item, 'product', None)
    if product is not None and getattr(product, 'track_inventory', True) is False:
        return None
    if item.variant_id:
        return item.variant
    from plugins.installed.catalog.variants import stock_variant  # noqa: PLC0415

    return stock_variant(product)


def _person(user):
    """A signed-in person for ``StockMovement.created_by``, else None."""
    return user if getattr(user, 'is_authenticated', False) else None


def _announce(level_id, before: int, after: int) -> None:
    """Tell the low-stock subscribers once, after the write commits, when a
    change takes a stock row across its line: to nothing left
    (PRODUCT_OUT_OF_STOCK) or to its reorder point (PRODUCT_LOW_STOCK).

    These events had subscribers (staff notifications, Pulse, workflows) and no
    producer: the post_save receiver meant to fire them was in a module nothing
    imported, and it would have fired on every save of a low row."""
    if after >= before:
        return

    def _fire():
        from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

        sl = (
            StockLevel.objects.select_related('variant', 'variant__product', 'warehouse')
            .filter(pk=level_id)
            .first()
        )
        if sl is None:
            return
        if before > 0 >= after:
            hook_registry.fire(MorpheusEvents.PRODUCT_OUT_OF_STOCK, stock_level=sl)
        elif before > sl.reorder_point >= after:
            hook_registry.fire(MorpheusEvents.PRODUCT_LOW_STOCK, stock_level=sl)

    transaction.on_commit(_fire)


def default_warehouse(*, create: bool = False):
    """The store's default active warehouse (else its first active one). With
    ``create``, a store with none gets "Main warehouse" (code MAIN)."""
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

    found = Warehouse.objects.filter(is_active=True).order_by('-is_default', 'name').first()
    if found is not None or not create:
        return found
    main, made = Warehouse.objects.get_or_create(
        code='MAIN', defaults={'name': 'Main warehouse', 'is_default': True}
    )
    if not made and not (main.is_active and main.is_default):
        main.is_active = True
        main.is_default = True
        main.save(update_fields=['is_active', 'is_default'])
    return main


def make_default_warehouse(warehouse) -> None:
    """``warehouse`` becomes the one default (and is switched on)."""
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

    with transaction.atomic():
        for other in Warehouse.objects.filter(is_default=True).exclude(pk=warehouse.pk):
            other.is_default = False
            other.save(update_fields=['is_default'])
        warehouse.is_default = True
        warehouse.is_active = True
        warehouse.save(update_fields=['is_default', 'is_active'])


def warehouse_code(raw: str) -> str:
    """A warehouse code from what was typed or from its name: capitals, digits
    and dashes, at most 20."""
    from django.utils.text import slugify  # noqa: PLC0415

    return slugify(raw or '').upper()[:20].strip('-')


def create_warehouse(name: str, code: str = '', *, make_default: bool = False, address=None):
    """A new active warehouse. The store's first one is its default. Raises
    ValueError for a missing name or a code already taken."""
    from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

    name = (name or '').strip()[:200]
    if not name:
        raise ValueError('A warehouse needs a name.')
    code = warehouse_code(code or name)
    if not code:
        raise ValueError('A warehouse needs a code of letters or digits.')
    if Warehouse.objects.filter(code=code).exists():
        raise ValueError(f'The code {code} is taken by another warehouse.')
    first = not Warehouse.objects.filter(is_active=True).exists()
    warehouse = Warehouse.objects.create(name=name, code=code, address=address or {})
    if make_default or first:
        make_default_warehouse(warehouse)
    return warehouse


def resolve_variant(code: str, *, create: bool = False):
    """A variant by its SKU, else the stock variant of the product with that
    SKU or slug (a product sold in one form; with ``create``, made when the
    product has no variant yet). None when nothing matches or the product has
    several variants to choose from."""
    from plugins.installed.catalog.models import Product, ProductVariant  # noqa: PLC0415
    from plugins.installed.catalog.variants import (  # noqa: PLC0415
        ensure_stock_variant,
        stock_variant,
    )

    code = (code or '').strip()
    if not code:
        return None
    variant = ProductVariant.objects.select_related('product').filter(sku=code).first()
    if variant is not None:
        return variant
    product = Product.objects.filter(sku=code).first() or Product.objects.filter(slug=code).first()
    if product is None:
        return None
    return ensure_stock_variant(product) if create else stock_variant(product)


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


# ── Stock for surfaces that do not own it ────────────────────────────────


def low_stock_threshold() -> int:
    """Units at or below which a product counts as low on stock — the number the
    dashboard's low-stock tile uses (advanced e-commerce settings)."""
    from plugins.registry import app_registry

    plugin = app_registry.get('advanced_ecommerce')
    try:
        return int(plugin.get_config_value('low_stock_threshold', 5)) if plugin else 5
    except (TypeError, ValueError):
        return 5


def stock_rows():
    """Every stock row that counts: switched-on warehouses, products that count
    stock, each annotated ``free`` (on hand less held). The Stock page lists
    them; ``low_stock_levels`` is a filter of them."""
    from django.db.models import F

    from plugins.installed.inventory.models import StockLevel

    return (
        StockLevel.objects.filter(warehouse__is_active=True, variant__product__track_inventory=True)
        .annotate(free=F('quantity') - F('reserved_quantity'))
        .select_related('variant__product', 'warehouse')
    )


def low_stock_levels(limit: int = 50) -> list:
    """Stock rows whose free units (on hand minus held) are at or below
    ``low_stock_threshold()``, fewest first. The Stock page's low filter lists
    them; the dashboard home and Pulse show them."""
    return list(
        stock_rows()
        .filter(free__lte=low_stock_threshold())
        .order_by('free', 'variant__product__name')[:limit]
    )


def variant_stock_summary(variant_ids) -> dict:
    """Units the order's stock reservation could take, per variant, for the
    ``VARIANT_STOCK_SUMMARY`` filter: ``{str(variant_id): int}``, counted as
    ``allocator.plan_allocation`` counts them (active warehouses, quantity less
    reserved). A variant with no stock row anywhere is untracked — the
    reservation skips it — and is left out of the answer."""
    ids = [pk for pk in variant_ids or [] if pk]
    if not ids:
        return {}
    levels = StockLevel.objects.filter(variant_id__in=ids).select_related('warehouse')
    summary: dict = {}
    for level in levels:
        key = str(level.variant_id)
        summary.setdefault(key, 0)
        if level.warehouse.is_active:
            summary[key] += level.available_quantity
    return summary


def stock_summary(product_ids) -> dict:
    """Sellable units per product, for the ``PRODUCT_STOCK_SUMMARY`` filter.

    ``{str(product_id): {'available', 'low', 'out'}}``, summed over the active
    variants' stock rows (quantity less reserved). A product whose merchant
    switched tracking off, or whose variants have no stock rows, is untracked
    and left out of the answer — absence of a measurement is not a measurement
    of absence (``_availability_from_stock``).
    """
    from django.db.models import F, Sum

    from plugins.installed.catalog.models import Product

    ids = [pk for pk in product_ids or [] if pk]
    if not ids:
        return {}
    tracked = Product.objects.filter(pk__in=ids, track_inventory=True).values('pk')
    rows = (
        StockLevel.objects.filter(variant__product_id__in=tracked, variant__is_active=True)
        .values('variant__product_id')
        .annotate(qty=Sum(F('quantity') - F('reserved_quantity')))
    )
    threshold = low_stock_threshold()
    summary = {}
    for row in rows:
        available = max(0, int(row['qty'] or 0))
        summary[str(row['variant__product_id'])] = {
            'available': available,
            'out': available <= 0,
            'low': 0 < available <= threshold,
        }
    return summary
