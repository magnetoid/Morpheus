"""`{% load catalog_prices %}`: the EU Omnibus prior-price note.

``prior_prices`` feeds the PDP block (``catalog/blocks/prior_price.html``),
which every theme renders in its ``pdp_below_price`` slot; ``prior_price``
serves a page that shows one product's price itself (the booking page). Both
read ``catalog.price_history``, so a price the history cannot prove is never
printed.
"""

from __future__ import annotations

from django import template

from plugins.installed.catalog.models import Product
from plugins.installed.catalog.price_history import lowest_prior_price

register = template.Library()


def _product(product):
    # The PDP hands storefront blocks the GraphQL product dict, not the model.
    if isinstance(product, dict):
        pk = product.get('id')
        if not pk:
            return None
        return Product.objects.filter(pk=pk).prefetch_related('variants').first()
    return product if isinstance(product, Product) else None


@register.simple_tag
def prior_prices(product) -> list[dict]:
    """One row per target on sale: ``{variant_id, price, shown}``.

    A variable product gets a row per active variant on sale, keyed by the
    variant id the PDP's picker carries; ``shown`` marks the one the picker
    selects first, so the page is right before any script runs.
    """
    if isinstance(product, dict) and not (
        product.get('compareAtPrice')
        or any(v.get('isOnSale') for v in product.get('variants') or [])
    ):
        return []  # nothing on sale: the page view pays no query for the note
    obj = _product(product)
    if obj is None:
        return []
    if obj.product_type != 'variable':
        prior = lowest_prior_price(obj)
        return [{'variant_id': '', 'price': prior, 'shown': True}] if prior else []
    rows = []
    active = [v for v in obj.variants.all() if v.is_active]
    for i, variant in enumerate(active):
        prior = lowest_prior_price(variant)
        if prior:
            rows.append({'variant_id': str(variant.pk), 'price': prior, 'shown': i == 0})
    return rows


@register.simple_tag
def prior_price(product):
    """The prior price of one product (a model), or None."""
    obj = _product(product)
    return lowest_prior_price(obj) if obj is not None else None
