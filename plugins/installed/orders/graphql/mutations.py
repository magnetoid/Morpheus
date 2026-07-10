"""Cart + checkout mutations exposed by the orders plugin."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import is_staff as _is_staff
from core.graphql.types import ErrorType
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.types import CartType
from plugins.installed.orders.services import CartService

# ── Inputs ─────────────────────────────────────────────────────────────────────


@strawberry.input
class AddToCartInput:
    product_id: str = strawberry.field(description='UUID of the product')
    quantity: int = strawberry.field(description='Quantity to add')
    variant_id: str | None = strawberry.field(
        default=None, description='UUID of variant (optional)'
    )
    session_key: str = strawberry.field(default='', description='Anonymous session key')


@strawberry.input
class UpdateCartItemInput:
    item_id: str
    quantity: int


@strawberry.input
class RemoveCartItemInput:
    item_id: str


@strawberry.input
class ApplyCouponInput:
    cart_id: str
    code: str


@strawberry.input
class ApplyGiftCardInput:
    cart_id: str
    code: str


@strawberry.input
class CompleteOrderInput:
    cart_id: str
    email: str
    shipping_address: AddressInput
    billing_address: AddressInput | None = None
    shipping_rate_id: str | None = None
    # Registry slug of the chosen payment gateway (stripe / manual / cod /
    # test). Optional + validated server-side: empty/unknown/disabled →
    # the default gateway (stripe). The client never picks a disabled one.
    payment_gateway: str | None = None


@strawberry.input
class SetShippingRateInput:
    cart_id: str
    shipping_rate_id: str


# ── Payloads ───────────────────────────────────────────────────────────────────


@strawberry.type
class CartPayload:
    cart: CartType | None
    errors: list[ErrorType]


@strawberry.type
class OrderPayload:
    order_number: str = ''
    payment_client_secret: str = ''
    # Redirect-based gateways (PayPal): send the shopper here to approve.
    payment_redirect_url: str = ''
    errors: list[ErrorType] = strawberry.field(default_factory=list)


# ── Mutations ──────────────────────────────────────────────────────────────────


@strawberry.type
class OrdersMutationExtension:
    @strawberry.mutation(description='Select a shipping rate for a cart (stores it on the cart).')
    def set_shipping_rate(self, input: SetShippingRateInput) -> CartPayload:
        from plugins.installed.orders.models import Cart

        try:
            cart = Cart.objects.get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')]
            )

        cart.metadata = dict(cart.metadata or {})
        cart.metadata['shipping_rate_id'] = (input.shipping_rate_id or '').strip()
        cart.save(update_fields=['metadata', 'updated_at'])
        return CartPayload(cart=cart, errors=[])

    @strawberry.mutation(description='Add an item to a cart (creates the cart if needed).')
    def add_to_cart(self, info: strawberry.Info, input: AddToCartInput) -> CartPayload:
        try:
            request = (
                info.context.get('request')
                if isinstance(info.context, dict)
                else getattr(info.context, 'request', None)
            )
            customer = getattr(request, 'user', None) if request else None
            customer = customer if (customer and customer.is_authenticated) else None
            session_key = input.session_key or (
                request.session.session_key if request and hasattr(request, 'session') else ''
            )

            cart = CartService.get_or_create_cart(session_key=session_key, customer=customer)
            currency = ''
            if request is not None and hasattr(request, 'session'):
                currency = (request.session.get('display_currency') or '').strip().upper()
            CartService.add_item(
                cart=cart,
                product_id=input.product_id,
                quantity=max(1, input.quantity),
                variant_id=input.variant_id,
                currency=currency or None,
            )
            if (
                request is not None
                and hasattr(request, 'session')
                and not request.session.get('cart_id')
            ):
                request.session['cart_id'] = str(cart.id)
            return CartPayload(cart=cart, errors=[])
        except Exception as e:  # noqa: BLE001 — surface domain failure as ErrorType
            return CartPayload(
                cart=None, errors=[ErrorType(code='ADD_TO_CART_ERROR', message=str(e))]
            )

    @strawberry.mutation(description='Update the quantity of a single line item.')
    def update_cart_item(self, input: UpdateCartItemInput) -> CartPayload:
        from plugins.installed.orders.models import CartItem

        try:
            item = CartItem.objects.select_related('cart').get(pk=input.item_id)
            qty = max(0, int(input.quantity))
            if qty == 0:
                cart = item.cart
                item.delete()
            else:
                item.quantity = qty
                item.save(update_fields=['quantity'])
                cart = item.cart
            return CartPayload(cart=cart, errors=[])
        except CartItem.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart item not found.')]
            )
        except Exception as e:  # noqa: BLE001
            return CartPayload(cart=None, errors=[ErrorType(code='UPDATE_ERROR', message=str(e))])

    @strawberry.mutation(description='Remove a single line item from a cart.')
    def remove_cart_item(self, input: RemoveCartItemInput) -> CartPayload:
        from plugins.installed.orders.models import CartItem

        try:
            item = CartItem.objects.select_related('cart').get(pk=input.item_id)
            cart = item.cart
            item.delete()
            return CartPayload(cart=cart, errors=[])
        except CartItem.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart item not found.')]
            )

    @strawberry.mutation(description='Apply a coupon code to a cart.')
    def apply_coupon(self, input: ApplyCouponInput) -> CartPayload:
        from plugins.installed.orders.models import Cart

        try:
            cart = Cart.objects.get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')]
            )

        try:
            from plugins.installed.marketing.models import Coupon

            coupon = Coupon.objects.filter(code__iexact=input.code, is_active=True).first()
            if coupon is None:
                return CartPayload(
                    cart=cart,
                    errors=[
                        ErrorType(code='INVALID_COUPON', message='Coupon not found or expired.')
                    ],
                )
            cart.coupon = coupon
            cart.save(update_fields=['coupon', 'updated_at'])
        except ImportError:
            pass  # marketing optional
        except Exception:  # noqa: BLE001 — coupon model not yet migrated
            import logging

            logging.getLogger('morpheus.orders').warning('Suppressed exception', exc_info=True)
        return CartPayload(cart=cart, errors=[])

    @strawberry.mutation(description='Remove the applied coupon from a cart.')
    def remove_coupon(self, input: ApplyCouponInput) -> CartPayload:
        from plugins.installed.orders.models import Cart

        try:
            cart = Cart.objects.get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')]
            )
        if cart.coupon_id is not None:
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])
        return CartPayload(cart=cart, errors=[])

    @strawberry.mutation(
        description='Apply a gift card to a cart. Discount is applied at order time.'
    )
    def apply_gift_card(self, input: ApplyGiftCardInput) -> CartPayload:  # noqa: PLR0911
        from plugins.installed.orders.models import Cart

        try:
            cart = Cart.objects.get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')]
            )

        code = (input.code or '').strip().upper()
        if not code:
            return CartPayload(
                cart=cart,
                errors=[ErrorType(code='INVALID_GIFT_CARD', message='Enter a gift card code.')],
            )

        try:
            from django.utils import timezone

            from plugins.installed.gift_cards.services import lookup

            card = lookup(code)
            if card is None:
                return CartPayload(
                    cart=cart,
                    errors=[ErrorType(code='INVALID_GIFT_CARD', message='Gift card not found.')],
                )
            if card.state != 'active':
                return CartPayload(
                    cart=cart,
                    errors=[
                        ErrorType(code='INVALID_GIFT_CARD', message='Gift card is not active.')
                    ],
                )
            if card.expires_at and card.expires_at < timezone.now():
                return CartPayload(
                    cart=cart,
                    errors=[ErrorType(code='INVALID_GIFT_CARD', message='Gift card has expired.')],
                )
            if card.balance.amount <= 0:
                return CartPayload(
                    cart=cart,
                    errors=[
                        ErrorType(
                            code='INVALID_GIFT_CARD', message='Gift card has no balance left.'
                        )
                    ],
                )
            cart.gift_card = card
            cart.save(update_fields=['gift_card', 'updated_at'])
        except ImportError:
            return CartPayload(
                cart=cart,
                errors=[
                    ErrorType(code='UNAVAILABLE', message='Gift cards plugin is not installed.')
                ],
            )
        except Exception as e:  # noqa: BLE001
            return CartPayload(cart=cart, errors=[ErrorType(code='APPLY_FAILED', message=str(e))])
        return CartPayload(cart=cart, errors=[])

    @strawberry.mutation(description='Remove the applied gift card from a cart.')
    def remove_gift_card(self, input: ApplyGiftCardInput) -> CartPayload:
        # `input.code` is ignored; we just need the cart_id.
        from plugins.installed.orders.models import Cart

        try:
            cart = Cart.objects.get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return CartPayload(
                cart=None, errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')]
            )
        cart.gift_card = None
        cart.save(update_fields=['gift_card', 'updated_at'])
        return CartPayload(cart=cart, errors=[])

    @strawberry.mutation(
        description='Complete checkout: create the order, fire order.placed, return the Stripe client_secret.'
    )
    def complete_order(self, info: strawberry.Info, input: CompleteOrderInput) -> OrderPayload:
        from django.db import transaction

        from plugins.installed.orders.models import Cart
        from plugins.installed.orders.services import OrderService

        try:
            cart = Cart.objects.prefetch_related(
                'items',
                'items__product',
                'items__variant',
            ).get(pk=input.cart_id)
        except Cart.DoesNotExist:
            return OrderPayload(errors=[ErrorType(code='NOT_FOUND', message='Cart not found.')])

        if not cart.items.exists():
            return OrderPayload(errors=[ErrorType(code='EMPTY_CART', message='Cart is empty.')])

        if not input.email or '@' not in input.email:
            return OrderPayload(
                errors=[ErrorType(code='INVALID_EMAIL', message='A valid email is required.')]
            )

        request = (
            info.context.get('request')
            if isinstance(info.context, dict)
            else getattr(info.context, 'request', None)
        )
        ship = _address_dict(input.shipping_address)
        bill = _address_dict(input.billing_address) if input.billing_address else ship

        try:
            affiliate_code = ''
            if request is not None:
                affiliate_code = (request.COOKIES.get('morph_aff') or '').strip()
            if affiliate_code:
                ship['affiliate_code'] = affiliate_code
        except Exception:
            import logging

            logging.getLogger('morpheus.orders').warning('Suppressed exception', exc_info=True)

        if input.shipping_rate_id:
            cart.metadata = dict(cart.metadata or {})
            cart.metadata['shipping_rate_id'] = (input.shipping_rate_id or '').strip()
            cart.save(update_fields=['metadata', 'updated_at'])

        # Atomicity contract: order creation AND payment-intent creation
        # succeed together or roll back together. The previous code
        # created the order, then created the intent outside the atomic
        # block, then swallowed any Stripe error — leaving a "real"
        # order in the database with no payment intent, no client_secret
        # the customer could confirm against. Merchants then fulfilled
        # unpaid orders (direct revenue loss) and customers saw a
        # blank checkout. Now: if Stripe can't issue an intent, the
        # order is rolled back and the customer gets a retryable error.
        try:
            from plugins.installed.payments.services.routing import (
                create_payment_intent_for,
            )

            with transaction.atomic():
                order = OrderService.create_from_cart(
                    cart=cart,
                    email=input.email,
                    shipping_address=ship,
                    billing_address=bill,
                )
                # Route to the shopper-selected gateway. Empty / unknown /
                # disabled slug → default (stripe), so the live Stripe path
                # is unchanged when no method is picked.
                pi = create_payment_intent_for(order, input.payment_gateway)
                if not pi.get('success'):
                    # Force rollback by raising; the caller-level except
                    # converts this into a CHECKOUT_FAILED user message.
                    raise RuntimeError(
                        pi.get('error') or 'Payment provider could not issue a payment intent.'
                    )
                client_secret = pi.get('client_secret') or ''
                redirect_url = pi.get('approval_url') or ''
            return OrderPayload(
                order_number=order.order_number,
                payment_client_secret=client_secret,
                payment_redirect_url=redirect_url,
                errors=[],
            )
        except Exception as e:  # noqa: BLE001
            return OrderPayload(errors=[ErrorType(code='CHECKOUT_FAILED', message=str(e)[:300])])


# ── Staff-only order admin mutations ──────────────────────────────────────────


@strawberry.type
class OrderAdminResult:
    order_number: str
    status: str
    payment_status: str
    tracking_number: str
    error: str


def _check_scope(info, required: list[str]) -> str:
    if not _is_staff(info):
        return 'Forbidden — staff only.'
    request = getattr(info.context, 'request', None) or (
        info.context.get('request') if isinstance(info.context, dict) else None
    )
    granted = getattr(request, '_morph_token_scopes_graphql', None)
    if granted is None:
        return ''
    from plugins.installed.agent_mcp.scopes import has_any

    if not has_any(granted, required):
        return f'token missing scope: needs one of {sorted(required)}'
    return ''


def _serialize_order_admin(order, *, error: str = '') -> OrderAdminResult:
    return OrderAdminResult(
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        tracking_number=order.tracking_number or '',
        error=error,
    )


def _err_admin(msg: str) -> OrderAdminResult:
    return OrderAdminResult(
        order_number='',
        status='',
        payment_status='',
        tracking_number='',
        error=msg,
    )


@strawberry.input
class MarkFulfilledInput:
    order_number: str


@strawberry.input
class MarkShippedInput:
    order_number: str
    tracking_number: str = ''


@strawberry.input
class CancelOrderInput:
    order_number: str
    reason: str = ''


@strawberry.input
class MarkRefundedInput:
    order_number: str
    reason: str = ''


@strawberry.type
class OrdersAdminMutationExtension:
    """Staff-only order admin mutations — fulfill / ship / cancel /
    mark refunded. Lives in a separate extension class so the public
    cart/checkout mutations stay obviously scoped to anonymous use.
    """

    @strawberry.mutation(
        description='Mark a paid/processing order as fulfilled. Staff-only.',
    )
    def mark_order_fulfilled(
        self,
        info: strawberry.Info,
        input: MarkFulfilledInput,
    ) -> OrderAdminResult:
        err = _check_scope(info, ['orders.write'])
        if err:
            return _err_admin(err)
        from django_fsm import TransitionNotAllowed

        from plugins.installed.orders.models import Order

        order = Order.objects.filter(order_number=input.order_number).first()
        if order is None:
            return _err_admin(f'order {input.order_number!r} not found')
        try:
            order.fulfill()
            order.save()
        except TransitionNotAllowed as e:
            return _err_admin(f'cannot fulfill from status={order.status}: {e}')
        return _serialize_order_admin(order)

    @strawberry.mutation(
        description='Mark a fulfilled order as shipped (optionally with tracking number). Staff-only.',
    )
    def mark_order_shipped(
        self,
        info: strawberry.Info,
        input: MarkShippedInput,
    ) -> OrderAdminResult:
        err = _check_scope(info, ['orders.write'])
        if err:
            return _err_admin(err)
        from django_fsm import TransitionNotAllowed

        from plugins.installed.orders.models import Order

        order = Order.objects.filter(order_number=input.order_number).first()
        if order is None:
            return _err_admin(f'order {input.order_number!r} not found')
        try:
            order.ship(tracking_number=input.tracking_number)
            order.save()
        except TransitionNotAllowed as e:
            return _err_admin(f'cannot ship from status={order.status}: {e}')
        return _serialize_order_admin(order)

    @strawberry.mutation(description='Cancel an order from any status. Staff-only.')
    def cancel_order(
        self,
        info: strawberry.Info,
        input: CancelOrderInput,
    ) -> OrderAdminResult:
        err = _check_scope(info, ['orders.cancel'])
        if err:
            return _err_admin(err)
        from django_fsm import TransitionNotAllowed

        from plugins.installed.orders.models import Order

        order = Order.objects.filter(order_number=input.order_number).first()
        if order is None:
            return _err_admin(f'order {input.order_number!r} not found')
        try:
            order.cancel(reason=input.reason)
            order.save()
        except TransitionNotAllowed as e:
            return _err_admin(f'cannot cancel from status={order.status}: {e}')
        return _serialize_order_admin(order)

    @strawberry.mutation(
        description='Flag an order as refunded — manual, for refunds processed outside Morpheus. Staff-only.',
    )
    def mark_order_refunded(
        self,
        info: strawberry.Info,
        input: MarkRefundedInput,
    ) -> OrderAdminResult:
        err = _check_scope(info, ['orders.cancel'])
        if err:
            return _err_admin(err)
        from plugins.installed.orders.models import Order

        order = Order.objects.filter(order_number=input.order_number).first()
        if order is None:
            return _err_admin(f'order {input.order_number!r} not found')
        # Bypass FSM protection — manual flag, not a real transition.
        Order.objects.filter(pk=order.pk).update(
            status='refunded',
            payment_status='refunded',
        )
        order.refresh_from_db()
        order.log_event('ORDER_REFUNDED', message=input.reason)
        return _serialize_order_admin(order)


def _address_dict(addr: AddressInput) -> dict:
    return {
        'first_name': addr.first_name or '',
        'last_name': addr.last_name or '',
        'line1': addr.line1 or '',
        'line2': addr.line2 or '',
        'city': addr.city or '',
        'state': addr.state or '',
        'postal_code': addr.postal_code or '',
        'country': addr.country or '',
        'phone': addr.phone or '',
    }
