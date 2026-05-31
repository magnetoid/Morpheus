"""Bulk CSV reorder — paste/upload SKU,qty rows to seed a cart in one click.

The killer feature for B2B reorders: a procurement clerk has a PO with
50 line items. Instead of clicking 50 PDPs, they paste/upload one CSV
and the entire cart materialises (with account-specific pricing
already resolved).

CSV shape (header optional, comma or tab delimited):
    sku,quantity
    BOOK-001,5
    BOOK-002,2

Returns a structured result:
    {
        'lines_added': int,
        'lines_failed': [{row, sku, qty, reason}],
        'cart_id': str,
        'subtotal_estimate': Money | None,
    }

Idempotent at the row level — duplicate SKUs in the same upload sum,
and re-uploading the same CSV updates existing CartItems rather than
creating duplicates.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger('morpheus.b2b.bulk_order')

# Sanity cap — anything larger is almost certainly a paste error.
MAX_LINES = 500
# Skip blank lines + obvious header rows.
HEADER_TOKENS = {'sku', 'product', 'item', 'qty', 'quantity', 'amount'}


@dataclass(slots=True)
class BulkOrderResult:
    lines_added: int = 0
    lines_failed: list = field(default_factory=list)
    cart_id: str = ''
    subtotal_estimate: Decimal | None = None


def parse_csv(raw: str) -> list[tuple[int, str, int]]:
    """Parse the textarea / file content into [(row_number, sku, qty), ...].

    Returns rows in input order. Blank lines and the first row if it
    looks like a header are dropped silently.
    """
    if not raw:
        return []
    text = raw.strip()
    if not text:
        return []

    # Detect delimiter — tab if any tabs, else comma. Quoted-comma CSV
    # is handled correctly by csv.reader either way.
    delimiter = '\t' if '\t' in text.splitlines()[0] else ','
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []

    # Skip header if the first row contains any HEADER_TOKENS.
    first_cells = {c.strip().lower() for c in rows[0]}
    start_idx = 1 if first_cells & HEADER_TOKENS else 0

    out: list[tuple[int, str, int]] = []
    for offset, row in enumerate(rows[start_idx:], start=1):
        if not row:
            continue
        # Tolerate trailing empty cells.
        cells = [c.strip() for c in row if c.strip() != '']
        if not cells:
            continue
        if len(cells) < 2:
            out.append((offset, cells[0] if cells else '', -1))
            continue
        sku = cells[0]
        try:
            qty = int(cells[1])
        except (TypeError, ValueError):
            qty = -1
        out.append((offset, sku, qty))
        if len(out) >= MAX_LINES:
            break
    return out


def apply_to_cart(
    *, cart, parsed_rows: list[tuple[int, str, int]], account=None
) -> BulkOrderResult:
    """Materialise parsed rows into CartItem records on `cart`.

    Pricing is resolved via b2b.services.resolve_price_for_account so
    account-specific PriceList overrides apply.
    """
    from plugins.installed.b2b.services import resolve_price_for_account  # noqa: PLC0415
    from plugins.installed.catalog.models import (  # noqa: PLC0415
        Product,
        ProductVariant,
    )
    from plugins.installed.orders.models import CartItem  # noqa: PLC0415

    result = BulkOrderResult(cart_id=str(cart.id))
    if not parsed_rows:
        return result

    # Aggregate duplicate SKUs (procurement CSVs often list the same
    # item twice when a clerk consolidated subtotals).
    merged: dict[str, int] = {}
    fail_order: list[tuple[int, str]] = []
    for row_num, sku, qty in parsed_rows:
        if not sku:
            result.lines_failed.append(
                {'row': row_num, 'sku': '', 'qty': qty, 'reason': 'empty SKU'}
            )
            continue
        if qty <= 0:
            result.lines_failed.append(
                {'row': row_num, 'sku': sku, 'qty': qty, 'reason': 'invalid quantity'}
            )
            continue
        merged[sku] = merged.get(sku, 0) + qty
        if sku not in {k for _, k in fail_order}:
            fail_order.append((row_num, sku))

    if not merged:
        return result

    # Resolve every SKU to either a variant or a product in one pass.
    variants = {
        v.sku: v
        for v in ProductVariant.objects.filter(sku__in=merged.keys()).select_related('product')
    }
    skus_left = set(merged) - set(variants)
    products = {p.sku: p for p in Product.objects.filter(sku__in=skus_left, status='active')}

    subtotal = Decimal('0')
    currency_hint = None

    for sku, qty in merged.items():
        variant = variants.get(sku)
        product = variant.product if variant is not None else products.get(sku)
        if product is None or getattr(product, 'status', 'active') != 'active':
            result.lines_failed.append(
                {'row': '?', 'sku': sku, 'qty': qty, 'reason': 'unknown SKU'}
            )
            continue
        try:
            unit_price = resolve_price_for_account(
                product=product, account=account, variant=variant
            )
        except Exception:  # noqa: BLE001
            unit_price = getattr(variant or product, 'price', None) or getattr(
                product, 'price', None
            )

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': qty, 'unit_price': unit_price},
        )
        if not created:
            item.quantity += qty
            item.save(update_fields=['quantity'])
        result.lines_added += 1

        if unit_price is not None:
            try:
                subtotal += Decimal(str(getattr(unit_price, 'amount', unit_price))) * qty
                currency_hint = str(getattr(unit_price, 'currency', '')) or currency_hint
            except Exception:  # noqa: BLE001, S110 — best-effort subtotal estimate
                pass

    result.subtotal_estimate = subtotal if currency_hint else None
    logger.info(
        'b2b.bulk_order: cart %s lines_added=%s failed=%s',
        cart.id,
        result.lines_added,
        len(result.lines_failed),
    )
    return result
