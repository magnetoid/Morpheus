"""`{% load product_safety %}`: the safety details a product page shows."""

from __future__ import annotations

from django import template

register = template.Library()


def _row(product):
    """The catalog row behind a PDP's GraphQL dict (or a Product), or None."""
    from django.core.exceptions import ValidationError

    from plugins.installed.catalog.models import Product

    pk = product.get('id') if isinstance(product, dict) else getattr(product, 'pk', None)
    if not pk:
        return None
    try:
        return Product.objects.only('id', 'product_type', 'requires_shipping').filter(pk=pk).first()
    except (ValidationError, ValueError):
        return None


@register.simple_tag
def product_safety(product) -> dict:
    """``safety.effective`` for a product page, empty when the page has nothing to show.

    The PDP hands storefront blocks the GraphQL product dict, so the row is read by id.
    """
    from plugins.installed.product_safety.safety import effective, shows_anything

    row = _row(product)
    if row is None:
        return {}
    info = effective(row)
    return info if shows_anything(info) else {}


@register.simple_tag
def legal_guarantee_notice(product) -> dict:
    """The EU legal guarantee notice for a goods page: ``{'lang', 'small', 'large'}``, or {}."""
    from django.templatetags.static import static

    from plugins.installed.product_safety.safety import (
        GUARANTEE_NOTICE_FILES,
        shows_guarantee_notice,
    )

    row = _row(product)
    if row is None or not shows_guarantee_notice(row):
        return {}
    small, large = GUARANTEE_NOTICE_FILES['en']
    return {'lang': 'en', 'small': static(small), 'large': static(large)}
