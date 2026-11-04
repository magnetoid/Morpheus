"""`{% load product_safety %}`: the safety details a product page shows."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def product_safety(product) -> dict:
    """``safety.effective`` for a product page, empty when the page has nothing to show.

    The PDP hands storefront blocks the GraphQL product dict, so the row is read by id.
    """
    from django.core.exceptions import ValidationError

    from plugins.installed.catalog.models import Product
    from plugins.installed.product_safety.safety import effective, shows_anything

    pk = product.get('id') if isinstance(product, dict) else getattr(product, 'pk', None)
    if not pk:
        return {}
    try:
        row = Product.objects.only('id', 'product_type', 'requires_shipping').filter(pk=pk).first()
    except (ValidationError, ValueError):
        return {}
    if row is None:
        return {}
    info = effective(row)
    return info if shows_anything(info) else {}
