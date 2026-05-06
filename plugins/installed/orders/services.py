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

        Refuses to add inactive / archived products and zero-or-negative
        quantities — better to surface the error here than have checkout
        fail downstream.
        """
        if quantity is None or int(quantity) < 1:
            raise ValueError('Quantity must be at least 1.')
        product = Product.objects.get(id=product_id)
        if getattr(product, 'status', 'active') != 'active':
            raise ValueError('Product is not available.')
        variant = ProductVariant.objects.get(id=variant_id) if variant_id else None
        if variant is not None and not getattr(variant, 'is_active', True):
            raise ValueError('Variant is not available.')
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
    def calculate_cart_breakdown(
        cls,
        *,
        cart: Cart,
        address: Dict | None = None,
        billing_address: Dict | None = None,
        shipping_rate_id: str = '',
    ) -> dict:
        if not cart.items.exists():
            return {
                'currency': 'USD',
                'subtotal': Money(Decimal('0'), 'USD'),
                'shipping': Money(Decimal('0'), 'USD'),
                'tax': Money(Decimal('0'), 'USD'),
                'discount': Money(Decimal('0'), 'USD'),
                'total': Money(Decimal('0'), 'USD'),
                'meta': {},
            }

        items = list(cart.items.select_related('product', 'variant').all())
        currency = str(items[0].unit_price.currency)
        subtotal = Money(
            sum((Decimal(it.unit_price.amount) * it.quantity for it in items), Decimal('0')),
            currency,
        )

        breakdown = {
            'currency': currency,
            'subtotal': subtotal,
            'shipping': Money(Decimal('0'), currency),
            'tax': Money(Decimal('0'), currency),
            'discount': Money(Decimal('0'), currency),
            'total': subtotal,
            'meta': {},
        }

        coupon_code = getattr(getattr(cart, 'coupon', None), 'code', '') or ''

        try:
            adjusted = hook_registry.filter(
                MorpheusEvents.CART_CALCULATE_BREAKDOWN,
                value=breakdown,
                cart=cart,
                address=(address or {}),
                billing_address=(billing_address or {}),
                shipping_rate_id=(shipping_rate_id or ''),
                coupon=coupon_code or None,
                channel=None,
                customer=cart.customer,
            )
            if isinstance(adjusted, dict):
                breakdown = adjusted
        except Exception as e:  # noqa: BLE001
            logger.warning('cart.calculate_breakdown filter error: %s', e, exc_info=True)

        def _m(key: str) -> Money:
            v = breakdown.get(key)
            if isinstance(v, Money):
                return v
            return Money(Decimal('0'), currency)

        subtotal_m = _m('subtotal')
        shipping_m = _m('shipping')
        tax_m = _m('tax')
        discount_m = _m('discount')
        total_m = breakdown.get('total')
        if not isinstance(total_m, Money):
            total_m = subtotal_m + shipping_m + tax_m - discount_m
        if total_m.amount < 0:
            total_m = Money(Decimal('0'), currency)

        breakdown['subtotal'] = subtotal_m
        breakdown['shipping'] = shipping_m
        breakdown['tax'] = tax_m
        breakdown['discount'] = discount_m
        breakdown['total'] = total_m
        breakdown['currency'] = currency
        breakdown.setdefault('meta', {})

        return breakdown

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

        shipping_rate_id = str((cart.metadata or {}).get('shipping_rate_id') or '')
        breakdown = cls.calculate_cart_breakdown(
            cart=cart,
            address=shipping_address,
            billing_address=billing_address,
            shipping_rate_id=shipping_rate_id,
        )

        tax_total = breakdown['tax']
        shipping_total = breakdown['shipping']
        discount_total = breakdown['discount']
        final_total = breakdown['total']

        coupon_code = getattr(getattr(cart, 'coupon', None), 'code', '') or ''
        shipping_method = str((breakdown.get('meta') or {}).get('shipping_rate_name') or '')
        source = 'web'
        affiliate_code = ''
        if isinstance(shipping_address, dict):
            affiliate_code = str(shipping_address.get('affiliate_code') or '')
        if affiliate_code:
            source = f'affiliate:{affiliate_code}'

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
            coupon_code=coupon_code,
            shipping_method=shipping_method,
            source=source,
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

        try:
            meta = breakdown.get('meta') or {}

            applied_promos = meta.get('applied_promotions') or []
            if applied_promos:
                from plugins.installed.promotions.services import AppliedPromotion, record_application
                for p in applied_promos:
                    try:
                        ap = AppliedPromotion(
                            promotion_id=str(p.get('promotion_id') or ''),
                            promotion_name=str(p.get('promotion_name') or ''),
                            rule_id=str(p.get('rule_id') or '') or None,
                            discount_amount=Decimal(str(p.get('discount_amount') or '0')),
                            free_shipping=bool(p.get('free_shipping')),
                            gift_product_id=str(p.get('gift_product_id') or '') or None,
                            note=str(p.get('note') or ''),
                        )
                        record_application(
                            ap,
                            order_id=str(order.id),
                            customer_id=str(order.customer_id or ''),
                            currency=currency,
                        )
                    except Exception:  # noqa: BLE001
                        continue

            if cart.coupon_id:
                from django.db.models import F
                from plugins.installed.marketing.models import CouponUsage, Coupon
                coupon_meta = meta.get('coupon') or {}
                coupon_discount = Decimal(str(coupon_meta.get('discount_amount') or '0'))
                if coupon_discount > 0:
                    # Lock the Coupon row so two concurrent checkouts can't
                    # both bypass `usage_limit` (each would otherwise read
                    # times_used=N, both apply, both increment).
                    locked = (
                        Coupon.objects
                        .select_for_update()
                        .filter(id=cart.coupon_id)
                        .first()
                    )
                    if locked is not None and (
                        not locked.usage_limit or locked.times_used < locked.usage_limit
                    ):
                        if order.customer_id:
                            _, created = CouponUsage.objects.get_or_create(
                                coupon_id=cart.coupon_id,
                                customer_id=order.customer_id,
                                order=order,
                                defaults={'discount_amount': Money(coupon_discount, currency)},
                            )
                            if created:
                                Coupon.objects.filter(id=cart.coupon_id).update(
                                    times_used=F('times_used') + 1,
                                )
                        else:
                            Coupon.objects.filter(id=cart.coupon_id).update(
                                times_used=F('times_used') + 1,
                            )
        except Exception as e:  # noqa: BLE001
            logger.warning('orders: promotions/coupon recording failed: %s', e)

        # Redeem the applied gift card. Wrapped tightly: a race (card
        # disabled between cart-apply and order-create) must not break
        # checkout — the order stands; the merchant gets a flagged
        # warning in observability instead.
        gift_card_meta = (breakdown.get('meta') or {}).get('gift_card') or {}
        if gift_card_meta and getattr(cart, 'gift_card_id', None):
            try:
                from plugins.installed.gift_cards.services import redeem as gc_redeem
                applied_amount = Money(
                    Decimal(str(gift_card_meta.get('amount') or '0')),
                    currency,
                )
                if applied_amount.amount > 0:
                    gc_redeem(
                        code=gift_card_meta.get('code') or '',
                        amount=applied_amount,
                        reference=order.order_number,
                        actor=cart.customer,
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    'orders: gift-card redeem failed for order %s: %s — '
                    'order proceeded without gift-card discount',
                    order.order_number, e, exc_info=True,
                )

        cart.items.all().delete()
        if (
            cart.coupon_id
            or getattr(cart, 'gift_card_id', None)
            or (cart.metadata or {}).get('shipping_rate_id')
        ):
            cart.coupon = None
            cart.gift_card = None
            cart.metadata = {k: v for k, v in (cart.metadata or {}).items() if k != 'shipping_rate_id'}
            cart.save(update_fields=['coupon', 'gift_card', 'metadata', 'updated_at'])

        hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=order)
        return order

    @classmethod
    def confirm_order(cls, order: Order) -> None:
        order.confirm()  # FSM transition; raises if not in `pending`
        order.save()
        hook_registry.fire(MorpheusEvents.ORDER_CONFIRMED, order=order)
