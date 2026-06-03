"""Template helpers for surfacing BookProduct on the storefront.

The PDP `product` in context is the GraphQL-serialised dict (camelCase), so it
has no `book` relation — this tag resolves the BookProduct from the product's
slug/id. Fail-soft: returns None on any miss so a block never breaks the page.
"""

from __future__ import annotations

from django import template

register = template.Library()


def _attr(product, name):
    if product is None:
        return None
    if isinstance(product, dict):
        return product.get(name)
    return getattr(product, name, None)


@register.simple_tag
def book_for_product(product):
    """Return the BookProduct for a storefront `product` (dict or model), or None."""
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    slug = _attr(product, 'slug')
    pid = _attr(product, 'id')
    try:
        qs = BookProduct.objects.select_related('product')
        if slug:
            obj = qs.filter(product__slug=slug).first()
            if obj is not None:
                return obj
        if pid:
            return qs.filter(product_id=pid).first()
    except Exception:  # noqa: BLE001 — never break a storefront render
        return None
    return None
