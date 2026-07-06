"""Orders context processor — the nav-bar cart item count.

Owned by the orders plugin (it reads orders.Cart), contributed to every
storefront/dashboard template through `register_context_processor` in
`OrdersPlugin.ready()`. The kernel used to host this in
`core/context_processors.py`; it moved here so core imports no plugin model and
the count vanishes when orders is disabled (the aggregator in
`plugins/context_processors.py` skips inactive owners). ADR 0017 / arch-debt
Phase 8b.
"""

from __future__ import annotations


def cart_context(request):
    """Lightweight cart item count for the nav bar.

    Runs on every request, so resolve it in a SINGLE query: annotate the
    sum of line quantities onto the cart lookup instead of fetching the cart
    and then calling `cart.item_count` (which issues its own aggregate) — two
    queries per request collapsed to one.
    """
    from django.db.models import Sum

    count = 0
    try:
        from plugins.installed.orders.models import Cart

        qs = None
        if request.user.is_authenticated:
            qs = Cart.objects.filter(customer=request.user)
        elif request.session.session_key:
            qs = Cart.objects.filter(session_key=request.session.session_key)
        if qs is not None:
            row = qs.annotate(_n=Sum('items__quantity')).order_by('-updated_at').first()
            if row:
                count = row._n or 0
    except Exception:
        import logging

        logging.getLogger(__name__).warning('cart_context failed', exc_info=True)
    return {'cart_item_count': count}
