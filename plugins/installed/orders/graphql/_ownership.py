"""One cart-ownership predicate for the orders GraphQL surface.

Read AND write go through the same check, so the `cart`/`cartTotals` resolvers
and every cart mutation can never diverge — two ownership checks WILL drift and
the looser one becomes an IDOR (the reason the mutations shipped with none at
all: setShippingRate/updateCartItem/removeCartItem/apply*/remove*/completeOrder
looked carts up by caller-supplied id and mutated them blind).

A cart is owned by its customer (when logged in) or its anonymous session; a
`read:carts`-scoped token (agents/support) is the explicit escape hatch. The
loaders return the SAME "not found" error for a missing cart AND a cart that
isn't the caller's, so ids cannot be probed for existence.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from api.graphql_permissions import has_scope
from core.graphql.types import ErrorType

_CART_NOT_FOUND = 'Cart not found.'
_ITEM_NOT_FOUND = 'Cart item not found.'


def _request_of(info):
    ctx = info.context
    return ctx.get('request') if isinstance(ctx, dict) else getattr(ctx, 'request', None)


def may_access_cart(info, cart) -> bool:
    """True if the caller owns `cart` (or holds read:carts). Mirrors exactly the
    read check in queries._resolve_cart — keep them one function, not two."""
    request = _request_of(info)
    if cart.customer_id is not None:
        user = getattr(request, 'user', None) if request else None
        if user and getattr(user, 'is_authenticated', False) and user.pk == cart.customer_id:
            return True
    elif request is not None and getattr(request, 'session', None) is not None:
        # An anonymous cart is owned by its session; one with no session_key yet
        # is claimable by the current session (same as the read resolver).
        if not cart.session_key or cart.session_key == request.session.session_key:
            return True
    return has_scope(info, 'read:carts')


def load_owned_cart(info, cart_id):
    """(cart, None) when the caller owns it; (None, ErrorType) otherwise."""
    from plugins.installed.orders.models import Cart

    try:
        cart = Cart.objects.get(pk=cart_id)
    except (Cart.DoesNotExist, ValidationError, ValueError, TypeError):
        return None, ErrorType(code='NOT_FOUND', message=_CART_NOT_FOUND)
    if not may_access_cart(info, cart):
        return None, ErrorType(code='NOT_FOUND', message=_CART_NOT_FOUND)
    return cart, None


def load_owned_item(info, item_id):
    """(item, None) when the caller owns the item's cart; (None, ErrorType) else."""
    from plugins.installed.orders.models import CartItem

    try:
        item = CartItem.objects.select_related('cart').get(pk=item_id)
    except (CartItem.DoesNotExist, ValidationError, ValueError, TypeError):
        return None, ErrorType(code='NOT_FOUND', message=_ITEM_NOT_FOUND)
    if not may_access_cart(info, item.cart):
        return None, ErrorType(code='NOT_FOUND', message=_ITEM_NOT_FOUND)
    return item, None
