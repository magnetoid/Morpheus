"""Orders' contribution to the nightly health check (``HEALTH_CHECKS``)."""

from __future__ import annotations


class _RollBack(Exception):
    """Raised to undo the throwaway cart once it has been priced."""


def cart_pricing_check() -> dict:
    """Put a real, priced product in a cart and price it — then roll it all back.

    Exercises the add-to-cart rules and every CART_CALCULATE_BREAKDOWN handler
    (tax, shipping, discounts, tenders) without leaving a cart, an order or an
    event behind.
    """
    from django.db import transaction

    from plugins.installed.catalog.models import Product
    from plugins.installed.orders.models import Cart
    from plugins.installed.orders.services import CartService, OrderService

    name = 'A cart can be priced'
    product = Product.objects.filter(status='active', price__gt=0).order_by('pk').first()
    if product is None:
        return {'name': name, 'ok': True, 'detail': 'No priced products to test with.'}
    try:
        with transaction.atomic():
            cart = Cart.objects.create(session_key='health-check')
            CartService.add_item(cart=cart, product_id=str(product.id))
            total = OrderService.calculate_cart_breakdown(cart=cart, address={})['total']
            raise _RollBack(total)
    except _RollBack as done:
        total = done.args[0]
    except Exception as e:  # noqa: BLE001 — the failure is the finding
        return {'name': name, 'ok': False, 'detail': f'Pricing "{product.name}" failed: {e}'}
    ok = total.amount > 0
    return {
        'name': name,
        'ok': ok,
        'detail': '' if ok else f'"{product.name}" priced at {total}.',
    }
