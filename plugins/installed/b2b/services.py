"""B2B services — quote lifecycle + price-list resolution."""

# ruff: noqa: PLC0415, UP035, UP037
# Inline imports avoid app-registry race; legacy typing.Iterable kept
# for back-compat with callers that import it from here.
from __future__ import annotations

import logging
from collections.abc import Iterable
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.b2b')


def resolve_price_for_account(*, product, account=None, variant=None):
    """Find the best price-list price for this product+account, else fall back.

    The fallback is the catalog price the storefront cart charges — the
    variant's own price first (`effective_price`). Falling back to the parent
    product priced a variable product's variants at the parent's placeholder
    (0.00), so a bulk CSV reorder put free lines in the cart.
    """
    from plugins.installed.b2b.models import PriceListItem

    list_price = variant.effective_price if variant is not None else product.price
    if account is None:
        return list_price
    qs = PriceListItem.objects.filter(
        price_list__accounts=account,
        product=product,
        variant=variant,
    )
    item = qs.first()
    if item is None and variant is None:
        item = PriceListItem.objects.filter(
            price_list__accounts=account,
            product=product,
            variant__isnull=True,
        ).first()
    return item.price if item is not None else list_price


def create_quote(
    *, account, contact, owner, lines: Iterable[dict], valid_until=None, note: str = ''
) -> 'Quote':  # noqa: F821
    """Create a Quote with line items at fixed prices."""
    from plugins.installed.b2b.models import Quote, QuoteLine

    with transaction.atomic():
        quote = Quote.objects.create(
            account=account,
            contact=contact,
            owner=owner,
            state='draft',
            valid_until=valid_until,
            note_to_customer=note,
        )
        subtotal = Decimal('0')
        currency = 'USD'
        for line in lines:
            qty = int(line.get('quantity', 1) or 1)
            unit_price = line['unit_price']  # Money
            currency = str(unit_price.currency)
            from core.money import mul

            line_total = mul(unit_price, qty)
            QuoteLine.objects.create(
                quote=quote,
                product=line.get('product'),
                variant=line.get('variant'),
                description=line.get('description', '')[:240]
                or (line.get('product').name if line.get('product') else 'Item'),
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
            subtotal += Decimal(line_total.amount)
        quote.subtotal = Money(subtotal, currency)
        quote.total = Money(subtotal, currency)
        quote.save(update_fields=['subtotal', 'total', 'updated_at'])
    return quote


def send_quote(quote) -> None:
    quote.state = 'sent'
    quote.sent_at = timezone.now()
    quote.save(update_fields=['state', 'sent_at', 'updated_at'])


def accept_quote(quote) -> 'Quote':  # noqa: F821
    if quote.state in ('accepted', 'converted'):
        return quote
    quote.state = 'accepted'
    quote.accepted_at = timezone.now()
    quote.save(update_fields=['state', 'accepted_at', 'updated_at'])
    return quote
