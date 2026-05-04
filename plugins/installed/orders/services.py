"""Order + cart services."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, Optional

from django.db import transaction
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Cart, CartItem, Order, OrderItem

logger = logging.getLogger('morpheus.orders')


class CartService:

    @classmethod
    def get_or_create_cart(cls, session_key: str = '', customer=None) -> Cart:
        if customer:
            cart, _ = Cart.objects.get_or_create(customer=customer)
        else:
            cart, _ = Cart.objects.get_or_create(session_key=session_key, customer=None)
        return cart

    @classmethod
    def add_item(
        cls, cart: Cart, product_id: str, quantity: int = 1,
        variant_id: Optional[str] = None, currency: Optional[str] = None,
    ) -> CartItem:
        """Add a line item, picking the buyer-currency override if available.

        ``currency`` is the visitor's chosen display currency (resolved upstream
        from session/?currency=). When the product or variant has a
        ``localized_prices[currency]`` override we use that; otherwise we
        fall back to the default ``MoneyField`` price.
        """
        product = Product.objects.get(id=product_id)
        variant = ProductVariant.objects.get(id=variant_id) if variant_id else None
        target = variant or product
        unit_price = _resolve_unit_price(target, currency, fallback=product)

        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, variant=variant,
            defaults={'quantity': quantity, 'unit_price': unit_price},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])
        return item


def _resolve_unit_price(target, currency: Optional[str], *, fallback) -> Money:
    """Return a ``Money`` honoring ``target.localized_prices[currency]``
    when present, else the default MoneyField price."""
    default_price = (
        target.effective_price if hasattr(target, 'effective_price') else target.price
    ) or fallback.price

    if not currency:
        return default_price

    overrides = getattr(target, 'localized_prices', None) or {}
    raw = overrides.get(currency) or overrides.get(currency.upper())
    if raw is None and target is not fallback:
        # Variant override missing — try the parent product's overrides.
        overrides = getattr(fallback, 'localized_prices', None) or {}
        raw = overrides.get(currency) or overrides.get(currency.upper())
    if raw is None:
        return default_price
    try:
        return Money(Decimal(str(raw)), currency.upper())
    except Exception:  # noqa: BLE001 — bad data shouldn't break checkout
        logger.warning('orders: malformed localized_prices entry %r=%r', currency, raw)
        return default_price


class OrderService:

    @classmethod
    @transaction.atomic
    def create_from_cart(
        cls, cart: Cart, email: str,
        shipping_address: Dict, billing_address: Dict,
    ) -> Order:
        if not cart.items.exists():
            raise ValueError('Cannot place an order from an empty cart.')

        items = list(cart.items.select_related('product', 'variant').all())
        currency = str(items[0].unit_price.currency)
        subtotal = Money(
            sum((Decimal(it.unit_price.amount) * it.quantity for it in items), Decimal('0')),
            currency,
        )

        # Run subtotal through the cart-total filter so tax / shipping /
        # promotions plug in. Each handler returns Money or a dict with
        # adjustments; we accumulate component totals to persist on the Order.
        tax_total = Money(Decimal('0'), currency)
        shipping_total = Money(Decimal('0'), currency)
        discount_total = Money(Decimal('0'), currency)
        try:
            adjusted = hook_registry.filter(
                MorpheusEvents.CART_CALCULATE_TOTAL,
                value=subtotal,
                cart=cart,
                shipping_address=shipping_address,
                billing_address=billing_address,
            )
            if isinstance(adjusted, dict):
                tax_total = adjusted.get('tax', tax_total) or tax_total
                shipping_total = adjusted.get('shipping', shipping_total) or shipping_total
                discount_total = adjusted.get('discount', discount_total) or discount_total
                final_total = adjusted.get('total', subtotal) or subtotal
            elif isinstance(adjusted, Money):
                final_total = adjusted
            else:
                final_total = subtotal
        except Exception as e:  # noqa: BLE001 — hook chain shouldn't block checkout
            logger.warning('cart.calculate_total filter error: %s', e, exc_info=True)
            final_total = subtotal

        order = Order.objects.create(
            customer=cart.customer,
            email=email,
            shipping_address=shipping_address,
            billing_address=billing_address,
            subtotal=subtotal,
            tax_total=tax_total,
            shipping_total=shipping_total,
            discount_total=discount_total,
            total=final_total,
        )

        for cart_item in items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.name,
                variant_name=cart_item.variant.name if cart_item.variant else '',
                sku=cart_item.variant.sku if cart_item.variant else cart_item.product.sku,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                total_price=cart_item.total_price,
            )

        cart.items.all().delete()

        hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=order)
        return order

    @classmethod
    def confirm_order(cls, order: Order) -> None:
        order.confirm()  # FSM transition; raises if not in `pending`
        order.save()
        hook_registry.fire(MorpheusEvents.ORDER_CONFIRMED, order=order)
