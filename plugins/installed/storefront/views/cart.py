"""Cart views — list page + add-to-cart endpoint."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404

from api.client import internal_graphql
from morpheus.app.views import redirect, render
from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import CartItem

from ._queries import CART_QUERY

logger = logging.getLogger('morpheus.storefront')


def cart(request):
    from .checkout import _cart_totals

    data = internal_graphql(CART_QUERY, request=request)
    cart_data = (data or {}).get('cart', {}) or {}
    return render(
        request,
        'storefront/cart.html',
        {'cart': cart_data, 'totals': _cart_totals(request, cart_data)},
    )


def cart_remove(request, item_id):
    """Remove a single line from the current cart.

    POST-only. Verifies the item belongs to the requesting visitor's cart
    (by ``customer`` if authenticated, otherwise by ``session_key``) so
    nobody can delete another shopper's line by guessing a UUID. Fires
    ``REMOVE_FROM_CART`` after the row is gone — any subscriber error is
    swallowed so analytics never breaks the user-facing flow.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    qs = CartItem.objects.select_related('cart', 'product')
    if request.user.is_authenticated:
        qs = qs.filter(cart__customer=request.user)
    else:
        qs = qs.filter(
            cart__customer__isnull=True,
            cart__session_key=request.session.session_key or '',
        )

    item = get_object_or_404(qs, pk=item_id)
    cart_obj = item.cart
    product = item.product
    quantity = item.quantity
    item.delete()

    try:
        hook_registry.fire(
            MorpheusEvents.REMOVE_FROM_CART,
            cart=cart_obj,
            product=product,
            quantity=quantity,
            customer=request.user if request.user.is_authenticated else None,
        )
    except Exception:  # noqa: BLE001
        logger.exception('REMOVE_FROM_CART hook failed')

    messages.success(request, 'Removed from cart.')
    return redirect('/cart/')


def cart_update(request, item_id):
    """Set a cart line's quantity (POST `quantity`; 0 removes the line).

    Same ownership check as ``cart_remove`` — the item must belong to the
    requesting visitor's cart. Clamped to 0–99. No-JS friendly: the cart
    page's − / + stepper buttons submit this form with quantity±1.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    qs = CartItem.objects.select_related('cart', 'product')
    if request.user.is_authenticated:
        qs = qs.filter(cart__customer=request.user)
    else:
        qs = qs.filter(
            cart__customer__isnull=True,
            cart__session_key=request.session.session_key or '',
        )
    item = get_object_or_404(qs, pk=item_id)

    try:
        quantity = int((request.POST.get('quantity') or '').strip())
    except ValueError:
        quantity = item.quantity
    quantity = max(0, min(99, quantity))

    if quantity == 0:
        cart_obj, product, removed = item.cart, item.product, item.quantity
        item.delete()
        try:
            hook_registry.fire(
                MorpheusEvents.REMOVE_FROM_CART,
                cart=cart_obj,
                product=product,
                quantity=removed,
                customer=request.user if request.user.is_authenticated else None,
            )
        except Exception:  # noqa: BLE001
            logger.exception('REMOVE_FROM_CART hook failed')
        messages.success(request, 'Removed from cart.')
    elif quantity != item.quantity:
        item.quantity = quantity
        item.save(update_fields=['quantity'])

    return redirect('/cart/')


def cart_add(request, product_id):
    """Add a product to the cart.

    Returns JSON when called as ``X-Requested-With: fetch`` (the cart
    drawer drains the response into the slide-out). Falls back to a
    plain POST + redirect for users without JS.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quantity = max(1, int((request.POST.get('quantity') or '1').strip() or 1))
    variant_id = (request.POST.get('variant_id') or '').strip() or None

    is_xhr = request.headers.get(
        'X-Requested-With', ''
    ).lower() == 'fetch' or 'application/json' in request.headers.get('Accept', '')

    mutation = """
    mutation Add($input: AddToCartInput!) {
      addToCart(input: $input) {
        cart {
          id itemCount subtotal { amount currency }
          items {
            id quantity
            unitPrice { amount currency }
            totalPrice { amount currency }
            product { name slug primaryImage { url } }
            variant { name }
          }
        }
        errors { code message }
      }
    }
    """
    variables = {
        'input': {
            'productId': str(product_id),
            'quantity': quantity,
            'variantId': variant_id,
            'sessionKey': request.session.session_key or '',
        },
    }
    data = internal_graphql(mutation, variables=variables, request=request) or {}
    payload = (data or {}).get('addToCart') or {}
    errors = payload.get('errors') or []

    if not errors:
        try:
            prod = Product.objects.filter(pk=product_id).first()
            variant = ProductVariant.objects.filter(pk=variant_id).first() if variant_id else None
            if prod is not None:
                hook_registry.fire(
                    MorpheusEvents.ADD_TO_CART,
                    cart=None,
                    item=None,
                    product=prod,
                    variant=variant,
                    quantity=quantity,
                )
        except Exception:  # noqa: BLE001
            logger.exception('ADD_TO_CART hook failed')

    if is_xhr:
        if errors:
            return JsonResponse(
                {'ok': False, 'error': errors[0].get('message', 'Add failed.')},
                status=400,
            )
        return JsonResponse({'ok': True, 'cart': payload.get('cart') or {}})

    if errors:
        return redirect('/cart/')
    return redirect('/cart/')
