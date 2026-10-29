"""Price history: what a product or variant cost, and when.

`record` runs from a save of a Product or ProductVariant (catalog/signals.py)
and appends a `PriceHistory` row whenever the price or the compare-at price
differs from the newest row, so every write path (the product form, Linda's
`products.update_price`, scheduled prices, imports, the booking listing form)
is covered without any of them knowing about it.

`lowest_prior_price` answers the EU Omnibus question for a sale: the lowest
price in the 30 days before the current reduction began. It returns None
whenever the history cannot prove the answer — the target is not on sale, the
reduction began before the store kept history, or the newest row no longer
matches the stored price (a `QuerySet.update()` skipped the save). A claim the
history cannot source is left out, never guessed.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.catalog.price_history')

WINDOW = timedelta(days=30)
_PRICE_FIELDS = {'price', 'price_currency', 'compare_at_price', 'compare_at_price_currency'}
# Enough rows to cover the window for any realistic number of changes.
_MAX_ROWS = 200


def _target(obj):
    """(product_id, variant_id) whose history `obj`'s price writes, or None.

    A variable product's own price is a placeholder (the shown price is the
    cheapest variant's), and a variant without its own price shows the
    product's, so neither has a history of its own.
    """
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415

    if isinstance(obj, ProductVariant):
        if obj.price is None:
            return None
        return obj.product_id, obj.pk
    if obj.product_type == 'variable':
        return None
    return obj.pk, None


def record(obj, *, created: bool = False, update_fields=None) -> None:
    """Append a row when `obj`'s price or compare-at price changed. Never raises."""
    if update_fields is not None and not (set(update_fields) & _PRICE_FIELDS):
        return
    # A save of an `.only()` instance writes only its loaded columns; reading a
    # deferred MoneyField would raise KeyError out of djmoney.
    if {'price', 'compare_at_price'} & set(obj.get_deferred_fields()):
        return
    try:
        target = _target(obj)
        if target is None or obj.price is None:
            return
        from plugins.installed.catalog.models import PriceHistory  # noqa: PLC0415

        product_id, variant_id = target
        cap = obj.compare_at_price
        row = (
            obj.price.amount,
            str(obj.price.currency),
            cap.amount if cap is not None else None,
        )
        with transaction.atomic():
            newest = (
                PriceHistory.objects.filter(product_id=product_id, variant_id=variant_id)
                .values_list('amount', 'currency', 'compare_at_amount')
                .first()
            )
            if newest == row:
                return
            if created:
                source = 'created'
            elif newest is None:
                source = 'initial'
            else:
                source = 'changed'
            PriceHistory.objects.create(
                product_id=product_id,
                variant_id=variant_id,
                amount=row[0],
                currency=row[1],
                compare_at_amount=row[2],
                source=source,
            )
    except Exception:  # noqa: BLE001 — a history row must never fail a product save
        logger.exception('price_history: could not record %r', obj)


def _rows(product_id, variant_id) -> list[dict]:
    from plugins.installed.catalog.models import PriceHistory  # noqa: PLC0415

    return list(
        PriceHistory.objects.filter(product_id=product_id, variant_id=variant_id).values(
            'amount', 'currency', 'compare_at_amount', 'source', 'changed_at'
        )[:_MAX_ROWS]
    )


def _on_sale(obj) -> bool:
    price, cap = obj.price, obj.compare_at_price
    return bool(price is not None and cap is not None and cap.amount > price.amount)


def lowest_prior_price(obj) -> Money | None:
    """The lowest price `obj` had in the 30 days before its current reduction.

    `obj` is a Product or a ProductVariant with its own price. None when it is
    not on sale or the history cannot prove the answer (see the module doc).
    """
    try:
        target = _target(obj)
        if target is None or not _on_sale(obj):
            return None
        return _lowest_in_window(_rows(*target), obj.price.amount, str(obj.price.currency))
    except Exception:  # noqa: BLE001 — a PDP must never fail on its price note
        logger.exception('price_history: lowest_prior_price failed for %r', obj)
        return None


def _lowest_in_window(rows: list[dict], current, currency: str) -> Money | None:
    """The lowest amount in effect during the 30 days before `current` was set.

    `rows` are newest first. A row's price is in effect from its `changed_at`
    until the next newer row's.
    """
    if not rows or rows[0]['amount'] != current or rows[0]['currency'] != currency:
        return None
    # The current price's run of rows; its oldest row is when the reduction began.
    run = 0
    while run < len(rows) and rows[run]['amount'] == current:
        run += 1
    began = rows[run - 1]
    if began['source'] != 'changed':
        # Already reduced when history began, or sold at this price since it
        # was created: nothing proves a higher price before.
        return None
    window_start = began['changed_at'] - WINDOW
    seen, covered = [], False
    for row in rows[run:]:
        if row['currency'] != currency:
            return None
        seen.append(row['amount'])
        if row['changed_at'] <= window_start:
            covered = True  # the price in effect when the window opened
            break
    # Uncovered is fine only when the oldest row is the product's creation.
    if not seen or (not covered and (len(rows) == _MAX_ROWS or rows[-1]['source'] == 'initial')):
        return None
    return Money(min(seen), currency)


def history(obj, *, limit: int = 50) -> list[dict]:
    """`obj`'s newest rows, as plain data (Linda's `products.price_history`)."""
    target = _target(obj)
    if target is None:
        return []
    return [
        {
            'price': str(r['amount']),
            'currency': r['currency'],
            'compare_at_price': str(r['compare_at_amount'])
            if r['compare_at_amount'] is not None
            else None,
            'source': r['source'],
            'changed_at': timezone.localtime(r['changed_at']).isoformat(),
        }
        for r in _rows(*target)[:limit]
    ]
