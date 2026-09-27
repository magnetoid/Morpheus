"""Templatetag wrapper around services.collect_trust_data.

Used in the storefront block template:
    {% load trust_signals %}
    {% trust_data product as ts %}
"""

from __future__ import annotations

from django import template

from plugins.installed.trust_signals.services import collect_trust_data

register = template.Library()


@register.simple_tag(takes_context=True)
def trust_data(context, product) -> dict:
    """Return the trust-signal dict for `product`. Empty on any failure."""
    if product is None:
        return {}

    # The PDP hands storefront blocks the GraphQL product DICT, not the
    # model — collect_trust_data needs the real row (reviews reverse FK,
    # review_count/average_rating properties), so resolve it here. Looked
    # up via the app registry (like `_order_item_model` in services.py)
    # rather than a direct import — trust_signals has no declared `requires`
    # on catalog.
    if isinstance(product, dict):
        product_id = product.get('id')
        if not product_id:
            return {}
        from django.apps import apps  # noqa: PLC0415

        try:
            product_model = apps.get_model('catalog', 'Product')
        except LookupError:
            return {}
        product = product_model.objects.filter(pk=product_id).first()
        if product is None:
            return {}

    # Per-plugin config lives on PluginConfig — pull it lazily to keep
    # this tag cheap to import.
    config = _plugin_config()
    return collect_trust_data(product, config=config)


def _plugin_config() -> dict:
    """Resolve PluginConfig['trust_signals']['config'] with sane defaults."""
    try:
        from plugins.models import PluginConfig  # noqa: PLC0415

        row = PluginConfig.objects.filter(plugin_name='trust_signals').first()
        if row and isinstance(row.config, dict):
            return row.config
    except Exception:  # noqa: BLE001, S110 — never break the PDP for a missing config
        pass
    return {
        'show_rating': True,
        'min_reviews_for_rating': 3,
        'show_verified_share': True,
        'show_recent_purchases': True,
        'recent_purchases_window_hours': 72,
        'min_recent_purchases': 3,
    }
