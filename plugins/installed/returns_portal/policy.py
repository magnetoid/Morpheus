"""What a customer's return may become, and what it costs (C4, v0.188.0).

The same settings the app publishes to search engines decide the form: a refund is
always offered (``refund_full`` says whether the full price comes back, not whether a
refund exists), store credit only with ``refund_store_credit`` and an account to hold
it, an exchange only with ``refund_exchange``. A return fee is ``return_shipping_fee``
under ``return_fees = fixed_fee``; the exchange fee is the merchant's own choice.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from djmoney.money import Money

#: What the customer may pick, in the form's order.
OUTCOMES = ('refund', 'store_credit', 'exchange')
OUTCOME_LABELS = {
    'refund': 'Refund',
    'store_credit': 'Store credit',
    'exchange': 'Exchange',
}


def _value(key: str, default=None):
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.config_value('returns_portal', key, default)


def _on(key: str) -> bool:
    value = _value(key, False)
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return bool(value)


def _money(raw, currency: str) -> Money:
    try:
        amount = Decimal(str(raw or 0))
    except (InvalidOperation, ValueError):
        amount = Decimal('0')
    return Money(max(amount, Decimal('0')).quantize(Decimal('0.01')), currency)


def offered_outcomes(order, *, signed_in: bool) -> list[str]:
    """The outcomes the form offers for ``order``."""
    found = ['refund']
    if _on('refund_store_credit') and signed_in and getattr(order, 'customer_id', None):
        found.append('store_credit')
    if _on('refund_exchange'):
        found.append('exchange')
    return found


def exchange_editions(item) -> list:
    """The other editions ``item`` may be exchanged for: active, for sale, of the same
    product, and not dearer than what was paid for it."""
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415
    from plugins.installed.orders.exchange import paid_unit_price  # noqa: PLC0415

    if item.product_id is None:
        return []
    paid = paid_unit_price(item).amount
    found = []
    for variant in ProductVariant.objects.filter(
        product_id=item.product_id, is_active=True
    ).exclude(pk=item.variant_id):
        price = variant.effective_price
        if variant.is_for_sale and price is not None and price.amount <= paid:
            found.append(variant)
    return found


def return_fee(order) -> Money:
    """The fee a refund or credit carries: the fixed return fee, else nothing."""
    currency = str(order.total.currency)
    if str(_value('return_fees', 'not_stated') or '') != 'fixed_fee':
        return Money(0, currency)
    return _money(_value('return_shipping_fee', 0), currency)


def exchange_fee(order) -> Money:
    """What an exchange costs: free, the return fee, or the merchant's fixed amount."""
    currency = str(order.total.currency)
    mode = str(_value('exchange_fee', 'free') or 'free')
    if mode == 'same_as_return':
        return return_fee(order)
    if mode == 'fixed':
        return _money(_value('exchange_fee_amount', 0), currency)
    return Money(0, currency)


def fee_for(order, outcome: str) -> Money:
    return exchange_fee(order) if outcome == 'exchange' else return_fee(order)


def on_return_resolution(value, return_request=None, **kwargs):
    """RETURN_RESOLUTION: the customer's choice for a return, from its portal row."""
    from plugins.installed.orders.exchange import ExchangeLine  # noqa: PLC0415
    from plugins.installed.returns_portal.models import ReturnResolution  # noqa: PLC0415

    if return_request is None:
        return value
    row = ReturnResolution.objects.filter(request=return_request).first()
    if row is None:
        return value
    quantities = {
        str(e.get('order_item_id')): int(e.get('quantity', 0) or 0)
        for e in return_request.items or []
    }
    lines = []
    if row.resolution == 'exchange':
        for choice in row.exchange_choices or []:
            key = str(choice.get('order_item_id', ''))
            variant = str(choice.get('exchange_variant_id', '') or '')
            if key and variant:
                lines.append(
                    ExchangeLine(
                        order_item_id=key, variant_id=variant, quantity=quantities.get(key, 0)
                    )
                )
    return {
        'outcome': row.resolution,
        'exchange': lines,
        'fee': fee_for(return_request.order, row.resolution),
        'label': OUTCOME_LABELS.get(row.resolution, row.resolution),
    }


def return_instructions() -> str:
    """Where to send a return and how to pack it, as the merchant wrote it."""
    return str(_value('return_instructions', '') or '').strip()
