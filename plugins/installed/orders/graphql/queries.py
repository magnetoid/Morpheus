import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    current_customer,
    has_scope,
    require_authenticated,
)
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.types import CartTotalsType, CartType, OrderType
from plugins.installed.orders.models import Cart, Order

_ORDER_RELATED = (
    'customer',
    'channel',
)
_ORDER_PREFETCH = (
    'items',
    'items__product',
    'items__variant',
    'events',
)
_CART_RELATED = (
    'customer',
    'coupon',
)
_CART_PREFETCH = (
    'items',
    'items__product',
    'items__variant',
)
# Allowed sort keys for the `orders` query — a raw caller string would otherwise
# reach .order_by() and FieldError (500) or span a relation (info leak / DoS).
_ORDER_SORTS = frozenset(
    {
        'placed_at',
        '-placed_at',
        'created_at',
        '-created_at',
        'total',
        '-total',
        'status',
        '-status',
    }
)


def _scoped_orders_qs(info: strawberry.Info):
    """Return an Order queryset scoped to what the caller is allowed to see."""
    require_authenticated(info)

    qs = Order.objects.select_related(*_ORDER_RELATED).prefetch_related(*_ORDER_PREFETCH)

    # Admin / API-key with read:orders sees everything.
    if has_scope(info, 'read:orders'):
        return qs

    # Otherwise: scope to the logged-in customer.
    customer = current_customer(info)
    if customer is None:
        raise PermissionDenied('Cannot read orders without a customer context')
    return qs.filter(customer=customer)


def _resolve_cart(info: strawberry.Info, id=None):
    """Permission-checked cart lookup shared by the `cart` and `cartTotals`
    resolvers. Module-level on purpose: strawberry invokes root Query
    resolvers with ``self`` = the schema's root_value (None here), so a
    sibling call like ``self.cart(...)`` crashes with
    "'NoneType' object has no attribute 'cart'" — which broke cartTotals
    in production (the checkout JS's totals refresh)."""
    request = (
        info.context.get('request')
        if isinstance(info.context, dict)
        else getattr(info.context, 'request', None)
    )
    qs = Cart.objects.select_related(*_CART_RELATED).prefetch_related(*_CART_PREFETCH)

    if id is not None:
        try:
            cart = qs.get(id=id)
        except Cart.DoesNotExist:
            return None
        # Carts are session-scoped: only the owning session/user (or a
        # read:carts token) may read them. ONE predicate, shared with every
        # cart mutation, so read and write ownership can never drift.
        from plugins.installed.orders.graphql._ownership import may_access_cart

        if not may_access_cart(info, cart):
            raise PermissionDenied('Not allowed to read this cart')
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


@strawberry.type
class OrdersQueryExtension:
    @strawberry.field(description='Get an order by its order number')
    def order(self, info: strawberry.Info, order_number: str) -> OrderType | None:
        try:
            return _scoped_orders_qs(info).get(order_number=order_number)
        except Order.DoesNotExist:
            return None

    @strawberry.field(description='List orders the caller is allowed to see')
    def orders(
        self,
        info: strawberry.Info,
        first: int = 50,
        order_by: str = '-placed_at',
    ) -> list[OrderType]:
        first = max(1, min(first, 100))
        # Whitelist the sort key: a raw caller string reaches Django's
        # .order_by(), where an unknown field is a FieldError (500) and a
        # relation span (e.g. "customer__password") is an info leak / DoS.
        order_by = order_by if order_by in _ORDER_SORTS else '-placed_at'
        qs = _scoped_orders_qs(info).order_by(order_by)
        return list(qs[:first])

    @strawberry.field(description='Get a cart by its ID or by the current session')
    def cart(
        self,
        info: strawberry.Info,
        id: strawberry.ID | None = None,
    ) -> CartType | None:
        return _resolve_cart(info, id)

    @strawberry.field(description='Calculate cart totals (shipping/tax/discount) for an address')
    def cart_totals(
        self,
        info: strawberry.Info,
        cart_id: strawberry.ID,
        address: AddressInput | None = None,
        shipping_rate_id: str | None = None,
    ) -> CartTotalsType | None:
        from core.graphql.types import MoneyType
        from plugins.installed.orders.services import OrderService

        cart = _resolve_cart(info, cart_id)
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

        rate_id = (shipping_rate_id or '').strip() or str(
            (cart.metadata or {}).get('shipping_rate_id') or ''
        )
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
