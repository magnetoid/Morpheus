"""Internal model → GA4 ecommerce event payload.

Each helper returns a ``(event_name, params)`` tuple ready to feed
into ``measurement_protocol.send_event``.

Items are always built as a list of objects per the 2026 GA4
spec — ``items: [{...}]`` not ``items: {...}``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger('morpheus.tracking.events')


def _money_amount(value) -> float:
    if value is None:
        return 0.0
    try:
        if hasattr(value, 'amount'):
            return float(value.amount)
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _money_currency(value, default: str = 'USD') -> str:
    cur = getattr(value, 'currency', None)
    if cur is None:
        return default
    return str(cur)


def _product_item(
    product,
    *,
    quantity: int = 1,
    variant=None,
    list_id: str = '',
    list_name: str = '',
    index: int = 0,
) -> dict[str, Any]:
    """Shape a Product (model OR dict) into a GA4 items[] entry."""
    if isinstance(product, dict):
        name = product.get('name') or ''
        slug = product.get('slug') or ''
        sku = product.get('sku') or ''
        price = product.get('price')
        cat = product.get('category') or {}
        cat_name = cat.get('name') if isinstance(cat, dict) else getattr(cat, 'name', '')
    else:
        name = getattr(product, 'name', '') or ''
        slug = getattr(product, 'slug', '') or ''
        sku = getattr(product, 'sku', '') or ''
        price = getattr(product, 'price', None)
        cat = getattr(product, 'category', None)
        cat_name = getattr(cat, 'name', '') if cat else ''

    item: dict[str, Any] = {
        'item_id': sku or slug,
        'item_name': name,
        'price': _money_amount(price),
        'quantity': quantity,
    }
    if cat_name:
        item['item_category'] = cat_name
    if variant is not None:
        vname = getattr(variant, 'name', None) or (
            variant.get('name') if isinstance(variant, dict) else ''
        )
        vsku = getattr(variant, 'sku', None) or (
            variant.get('sku') if isinstance(variant, dict) else ''
        )
        if vname:
            item['item_variant'] = vname
        if vsku:
            item['item_id'] = vsku
    if list_id:
        item['item_list_id'] = list_id
    if list_name:
        item['item_list_name'] = list_name
    if index:
        item['index'] = index
    return item


def view_item(product) -> tuple[str, dict[str, Any]]:
    item = _product_item(product)
    return 'view_item', {
        'currency': _money_currency(
            getattr(product, 'price', None)
            if not isinstance(product, dict)
            else product.get('price')
        ),
        'value': item['price'],
        'items': [item],
    }


def view_item_list(
    *, items: list, list_id: str = '', list_name: str = ''
) -> tuple[str, dict[str, Any]]:
    payload_items = [
        _product_item(p, list_id=list_id, list_name=list_name, index=i + 1)
        for i, p in enumerate(items[:50])
    ]
    return 'view_item_list', {
        'item_list_id': list_id,
        'item_list_name': list_name,
        'items': payload_items,
    }


def add_to_cart(
    *, cart, item, product, variant=None, quantity: int = 1
) -> tuple[str, dict[str, Any]]:
    line_item = _product_item(product, quantity=quantity, variant=variant)
    return 'add_to_cart', {
        'currency': _money_currency(getattr(product, 'price', None)),
        'value': line_item['price'] * quantity,
        'items': [line_item],
    }


def remove_from_cart(*, cart, item, product, quantity: int = 1) -> tuple[str, dict[str, Any]]:
    line_item = _product_item(product, quantity=quantity)
    return 'remove_from_cart', {
        'currency': _money_currency(getattr(product, 'price', None)),
        'value': line_item['price'] * quantity,
        'items': [line_item],
    }


def begin_checkout(cart) -> tuple[str, dict[str, Any]]:
    items = []
    total = Decimal('0')
    currency = 'USD'
    try:
        for i, ci in enumerate(cart.items.all()):
            prod = getattr(ci, 'product', None) or (
                getattr(getattr(ci, 'variant', None), 'product', None)
            )
            if prod is None:
                continue
            qty = int(getattr(ci, 'quantity', 1) or 1)
            line = _product_item(
                prod, quantity=qty, variant=getattr(ci, 'variant', None), index=i + 1
            )
            items.append(line)
            total += Decimal(str(line['price'])) * qty
            currency = _money_currency(getattr(prod, 'price', None), currency)
    except Exception as exc:  # noqa: BLE001
        logger.debug('begin_checkout shape failed: %s', exc)
    return 'begin_checkout', {
        'currency': currency,
        'value': float(total),
        'items': items,
    }


def purchase(order) -> tuple[str, dict[str, Any]]:
    items = []
    try:
        for i, line in enumerate(order.items.all()):
            prod = getattr(line, 'product', None) or getattr(
                getattr(line, 'variant', None), 'product', None
            )
            if prod is None:
                continue
            qty = int(getattr(line, 'quantity', 1) or 1)
            items.append(
                _product_item(
                    prod, quantity=qty, variant=getattr(line, 'variant', None), index=i + 1
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug('purchase items shape failed: %s', exc)

    total = getattr(order, 'total', None) or getattr(order, 'grand_total', None)
    shipping = getattr(order, 'shipping_total', None) or getattr(order, 'shipping', None)
    tax = getattr(order, 'tax_total', None) or getattr(order, 'tax', None)
    coupon = ''
    if hasattr(order, 'coupon_code'):
        coupon = (order.coupon_code or '').strip()
    elif isinstance(getattr(order, 'metadata', None), dict):
        coupon = (order.metadata.get('coupon_code') or '').strip()

    params: dict[str, Any] = {
        'transaction_id': getattr(order, 'order_number', None) or str(order.pk),
        'currency': _money_currency(total),
        'value': _money_amount(total),
        'items': items,
    }
    if shipping is not None:
        params['shipping'] = _money_amount(shipping)
    if tax is not None:
        params['tax'] = _money_amount(tax)
    if coupon:
        params['coupon'] = coupon
    return 'purchase', params


def refund(*, order, amount=None) -> tuple[str, dict[str, Any]]:
    return 'refund', {
        'transaction_id': getattr(order, 'order_number', None) or str(order.pk),
        'currency': _money_currency(amount or getattr(order, 'total', None)),
        'value': _money_amount(amount if amount is not None else getattr(order, 'total', None)),
    }
