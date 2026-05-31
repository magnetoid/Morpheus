"""Order + cart services."""

# ruff: noqa: PLC0415, PLR0912, PLR0915, S110, S112, I001
# - PLC0415: inline imports break a circular dep between orders ↔ promotions
#   / gift_cards / audit / marketing. Refactoring is out-of-scope here.
# - PLR0912 / PLR0915: create_from_cart() is large by necessity — it's the
#   atomic boundary for the entire cart→order transition. Splitting it
#   would require staged transactions with new failure modes.
# - S110 / S112: defensive try/except/pass around audit + gift-card redeem
#   is deliberate — these must never break order creation.
from __future__ import annotations

import logging
from decimal import Decimal

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
        cls,
        cart: Cart,
        product_id: str,
        quantity: int = 1,
        variant_id: str | None = None,
        currency: str | None = None,
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

        # Real-time stock reservation (sprint priority #2).
        # Hold the units in Redis with a TTL so another customer can't
        # race to grab the last unit between cart-add and checkout.
        # Failure of the reservation layer must not break cart-add —
        # the DB-side reserve_for_order at checkout is the actual
        # correctness boundary.
        # Real-time stock reservation only fires for variants that are
        # actually inventoried. Digital + virtual variants and any
        # product where the merchant opted out of inventory tracking
        # have no StockLevel rows; running reservation against them
        # returns "0 left" and blocks the cart-add. The DB-side
        # reserve_for_order() at checkout is still the correctness
        # boundary — this is just the CRO-time hold.
        should_reserve = variant is not None and _is_inventoried(product, variant)
        if should_reserve:
            try:
                from plugins.installed.inventory.cart_reservations import (  # noqa: PLC0415
                    reserve as _reserve_stock,
                )

                result = _reserve_stock(
                    variant_id=str(variant.id),
                    cart_id=str(cart.id),
                    quantity=int(quantity),
                )
                if not result.ok:
                    raise ValueError(
                        f'Only {result.available} left in stock — others are checking out.'
                    )
            except ValueError:
                raise
            except Exception:  # noqa: BLE001 — reservation is best-effort
                logger.exception('cart_reservations: reserve raised; allowing cart-add through')

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity, 'unit_price': unit_price},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])
        return item


@transaction.atomic
def merge_carts(*, source_cart: Cart, target_cart: Cart) -> Cart:
    """Move items from ``source_cart`` into ``target_cart`` and delete the source.

    When the target already has a line with the same product+variant,
    quantities are summed (the unique_together on CartItem otherwise
    blocks a naive reparent). The source cart is deleted at the end.

    Returns the (possibly mutated) target cart.
    """
    if source_cart.pk == target_cart.pk:
        return target_cart

    for item in source_cart.items.all():
        existing = target_cart.items.filter(
            product=item.product,
            variant=item.variant,
        ).first()
        if existing is None:
            item.cart = target_cart
            item.save(update_fields=['cart'])
        else:
            existing.quantity = existing.quantity + item.quantity
            existing.save(update_fields=['quantity'])
            item.delete()

    source_cart.delete()
    return target_cart


def _is_inventoried(product, variant) -> bool:
    """True when this product/variant tracks physical stock and should
    therefore go through cart-time Redis reservation.

    Returns False (skip reservation) when:
      - the product is digital, virtual, or bundle;
      - the product or variant doesn't require shipping;
      - the variant's variant_type is digital or virtual;
      - the merchant turned track_inventory off on the product.

    The DB-side reserve_for_order at checkout is still the correctness
    boundary for everything that DOES track inventory.
    """
    if getattr(product, 'product_type', 'simple') in ('digital', 'bundle'):
        return False
    if getattr(product, 'track_inventory', True) is False:
        return False
    if getattr(product, 'requires_shipping', True) is False:
        return False
    variant_type = getattr(variant, 'variant_type', 'physical')
    if variant_type in ('digital', 'virtual'):
        return False
    return getattr(variant, 'requires_shipping', True) is not False


def _resolve_unit_price(target, currency: str | None, *, fallback) -> Money:
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
        address: dict | None = None,
        billing_address: dict | None = None,
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
        cls,
        cart: Cart,
        email: str,
        shipping_address: dict,
        billing_address: dict,
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
                from plugins.installed.promotions.services import (
                    AppliedPromotion,
                    record_application,
                )

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
                    locked = Coupon.objects.select_for_update().filter(id=cart.coupon_id).first()
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

        # Redeem the applied gift card. The cart's gift-card discount is
        # already baked into `order.total` at this point; a redeem
        # failure (card disabled / expired / insufficient balance race)
        # means the customer is about to be charged a discounted amount
        # without us actually consuming a gift card. We narrow the
        # except, write the failure to BOTH the order metadata AND the
        # audit log (not just a logger.warning that nobody reads), and
        # flag the order with `gift_card_redeem_failed=True` so the
        # checkout caller can refuse to capture and the merchant can
        # reconcile manually.
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
            except (ValueError, LookupError, ImportError) as e:
                logger.warning(
                    'orders: gift-card redeem failed for order %s: %s',
                    order.order_number,
                    e,
                    exc_info=True,
                )
                try:
                    order.metadata = order.metadata or {}
                    order.metadata['gift_card_redeem_failed'] = True
                    order.metadata['gift_card_redeem_error'] = str(e)[:200]
                    order.save(update_fields=['metadata'])
                except Exception:  # noqa: BLE001
                    pass
                try:
                    from core.audit.services import record as audit_record

                    audit_record(
                        event_type='order.gift_card_redeem_failed',
                        actor_user=getattr(cart, 'customer', None),
                        target=order,
                        metadata={
                            'order_number': order.order_number,
                            'gift_card_code': gift_card_meta.get('code') or '',
                            'error': str(e)[:500],
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass

        cart.items.all().delete()
        if (
            cart.coupon_id
            or getattr(cart, 'gift_card_id', None)
            or (cart.metadata or {}).get('shipping_rate_id')
        ):
            cart.coupon = None
            cart.gift_card = None
            cart.metadata = {
                k: v for k, v in (cart.metadata or {}).items() if k != 'shipping_rate_id'
            }
            cart.save(update_fields=['coupon', 'gift_card', 'metadata', 'updated_at'])

        hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=order)
        return order

    @classmethod
    def confirm_order(cls, order: Order) -> None:
        order.confirm()  # FSM transition; raises if not in `pending`
        order.save()
        hook_registry.fire(MorpheusEvents.ORDER_CONFIRMED, order=order)
