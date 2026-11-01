"""Templatetag wrapper around reviews.trust.collect_trust_data.

Used in the storefront block template:
    {% load review_trust %}
    {% trust_data product as ts %}
"""

from __future__ import annotations

from django import template

from plugins.installed.reviews.trust import collect_trust_data

register = template.Library()


@register.simple_tag(takes_context=True)
def trust_data(context, product) -> dict:
    """Return the trust-signal dict for `product`. Empty on any failure."""
    if product is None:
        return {}

    # The PDP hands storefront blocks the GraphQL product DICT, not the
    # model — collect_trust_data needs the real row (reviews reverse FK,
    # review_count/average_rating properties), so resolve it here.
    if isinstance(product, dict):
        product_id = product.get('id')
        if not product_id:
            return {}
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return {}

    return collect_trust_data(product, config=_config())


def _config() -> dict:
    """The reviews app's settings, read fresh: a save in one web worker must
    reach every other one, and the plugin's own config cache is per process."""
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('reviews')
    if plugin is None:
        return {}
    plugin.invalidate_config_cache()
    return plugin.get_config()
