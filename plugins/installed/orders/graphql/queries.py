import strawberry
from typing import List, Optional

from api.graphql_permissions import (
    PermissionDenied,
    current_customer,
    has_scope,
    require_authenticated,
)
from plugins.installed.orders.graphql.types import CartType, OrderType, CartTotalsType
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.models import Cart, Order

_ORDER_RELATED = (
    'customer', 'channel',
)
_ORDER_PREFETCH = (
    'items', 'items__product', 'items__variant', 'events',
)
_CART_RELATED = (
    'customer', 'coupon',
)
_CART_PREFETCH = (
    'items', 'items__product', 'items__variant',
)


def _scoped_orders_qs(info: strawberry.Info):
    """Return an Order queryset scoped to what the caller is allowed to see."""
    require_authenticated(info)

    qs = (
        Order.objects
        .select_related(*_ORDER_RELATED)
        .prefetch_related(*_ORDER_PREFETCH)
    )

    # Admin / API-key with read:orders sees everything.
    if has_scope(info, 'read:orders'):
        return qs

    # Otherwise: scope to the logged-in customer.
    customer = current_customer(info)
    if customer is None:
        raise PermissionDenied("Cannot read orders without a customer context")
    return qs.filter(customer=customer)


@strawberry.type
class OrdersQueryExtension:

    @strawberry.field(description="Get an order by its order number")
    def order(self, info: strawberry.Info, order_number: str) -> Optional[OrderType]:
        try:
            return _scoped_orders_qs(info).get(order_number=order_number)
        except Order.DoesNotExist:
            return None

    @strawberry.field(description="List orders the caller is allowed to see")
    def orders(
        self,
        info: strawberry.Info,
        first: int = 50,
        order_by: str = "-placed_at",
    ) -> List[OrderType]:
        first = max(1, min(first, 100))
        qs = _scoped_orders_qs(info).order_by(order_by)
        return list(qs[:first])

    @strawberry.field(description="Get a cart by its ID or by the current session")
    def cart(
        self,
        info: strawberry.Info,
        id: Optional[strawberry.ID] = None,
    ) -> Optional[CartType]:
        request = info.context.get('request') if isinstance(info.context, dict) else getattr(info.context, 'request', None)
        qs = Cart.objects.select_related(*_CART_RELATED).prefetch_related(*_CART_PREFETCH)

        if id is not None:
            try:
                cart = qs.get(id=id)
            except Cart.DoesNotExist:
                return None
            # Carts are session-scoped: only the owning session/user may read them.
            if cart.customer_id is not None:
                user = getattr(request, 'user', None) if request else None
                if not user or not getattr(user, 'is_authenticated', False) or user.pk != cart.customer_id:
                    if not has_scope(info, 'read:carts'):
                        raise PermissionDenied("Not allowed to read this cart")
            elif request is not None and getattr(request, 'session', None) is not None:
                if cart.session_key and cart.session_key != request.session.session_key:
                    if not has_scope(info, 'read:carts'):
                        raise PermissionDenied("Not allowed to read this cart")
            return cart

        if request is not None and getattr(request, 'session', None) is not None:
            cart_id = request.session.get('cart_id')
            if cart_id:
                try:
                    return qs.get(id=cart_id)
                except Cart.DoesNotExist:
                    del request.session['cart_id']
                    return None
        return None

    @strawberry.field(description="Calculate cart totals (shipping/tax/discount) for an address")
    def cart_totals(
        self,
        info: strawberry.Info,
        cart_id: strawberry.ID,
        address: Optional[AddressInput] = None,
        shipping_rate_id: Optional[str] = None,
    ) -> Optional[CartTotalsType]:
        from plugins.installed.orders.services import OrderService
        from core.graphql.types import MoneyType

        cart = self.cart(info, id=cart_id)
        if cart is None:
            return None

        addr = {}
        if address is not None:
            addr = {
                'first_name': address.first_name or '',
                'last_name': address.last_name or '',
                'line1': address.line1 or '',
                'line2': address.line2 or '',
                'city': address.city or '',
                'state': address.state or '',
                'postal_code': address.postal_code or '',
                'country': address.country or '',
                'phone': address.phone or '',
            }

        rate_id = (shipping_rate_id or '').strip() or str((cart.metadata or {}).get('shipping_rate_id') or '')
        breakdown = OrderService.calculate_cart_breakdown(
            cart=cart,
            address=addr,
            billing_address={},
            shipping_rate_id=rate_id,
        )

        def m(x):
            if hasattr(x, 'amount'):
                return MoneyType(amount=str(x.amount), currency=str(x.currency))
            return MoneyType(amount='0', currency=str(breakdown.get('currency') or 'USD'))

        meta = breakdown.get('meta') or {}
        return CartTotalsType(
            subtotal=m(breakdown.get('subtotal')),
            shipping=m(breakdown.get('shipping')),
            tax=m(breakdown.get('tax')),
            discount=m(breakdown.get('discount')),
            total=m(breakdown.get('total')),
            shipping_rate_id=rate_id,
            shipping_rate_name=str(meta.get('shipping_rate_name') or ''),
        )
