"""Cart views — list page + add-to-cart endpoint."""
from __future__ import annotations

from api.client import internal_graphql
from morpheus.views import redirect, render

from ._queries import CART_QUERY


def cart(request):
    data = internal_graphql(CART_QUERY, request=request)
    return render(request, 'storefront/cart.html', {'cart': (data or {}).get('cart', {})})


def cart_add(request, product_id):
    """Add a product to the cart.

    Returns JSON when called as ``X-Requested-With: fetch`` (the cart
    drawer drains the response into the slide-out). Falls back to a
    plain POST + redirect for users without JS.
    """
    from django.http import HttpResponseNotAllowed, JsonResponse

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quantity = max(1, int((request.POST.get('quantity') or '1').strip() or 1))
    variant_id = (request.POST.get('variant_id') or '').strip() or None

    is_xhr = (
        request.headers.get('X-Requested-With', '').lower() == 'fetch'
        or 'application/json' in request.headers.get('Accept', '')
    )

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
            from core.hooks import hook_registry, MorpheusEvents
            from plugins.installed.catalog.models import Product, ProductVariant
            prod = Product.objects.filter(pk=product_id).first()
            variant = ProductVariant.objects.filter(pk=variant_id).first() if variant_id else None
            if prod is not None:
                hook_registry.fire(
                    MorpheusEvents.ADD_TO_CART,
                    cart=None, item=None,
                    product=prod, variant=variant, quantity=quantity,
                )
        except Exception:  # noqa: BLE001
            pass

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
