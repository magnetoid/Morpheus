"""Storefront price rendering — the shelf must agree with the PDP.

``PRODUCT_CALCULATE_PRICE`` (v0.38) is applied on the PDP's GraphQL resolver and
on the charge path in ``CartService.add_item``, so those two can never diverge.
The listing surfaces were missed: ``_product_card.html`` renders
``Product.display_price`` straight off the ORM row, which never runs the filter.
The moment a merchant writes a Functions pricing rule or turns on AI dynamic
pricing, the shelf showed one price while the PDP and cart showed another —
exactly the divergence the seam exists to prevent.

Applied HERE rather than inside ``Product.display_price`` deliberately: that
property is also read by product feeds, exports and the dashboard, and a
shopper-specific dynamic price has no business in a Google feed or an admin
list. This filter is the storefront read layer only.
"""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def storefront_price(context, product):
    """Return the shopper-facing price for ``product`` (``None`` if it has none).

    Accepts either an ORM ``Product`` (listing surfaces) or the GraphQL dict the
    PDP/home pass around — the dict path is already filtered upstream, so it is
    returned untouched rather than double-filtered.
    """
    if product is None:
        return None

    # GraphQL/serialised shape: already filtered at its own read layer.
    if isinstance(product, dict):
        return product.get('display_price') or product.get('price')

    price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
    if price is None:
        return None

    from core.pricing import apply_price_filter

    request = context.get('request')
    customer = getattr(request, 'user', None) if request is not None else None
    return apply_price_filter(price, product=product, customer=customer)
