"""`{% load ai_text %}`: the product page's mark of AI-written text."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def ai_text_mark(product) -> dict:
    """``{'fields': [...], 'label': bool}`` for a product page, empty when unmarked.

    ``fields`` lists the marked text the page shows (description, short
    description); ``label`` is the merchant's choice to say so in words as well.
    """
    from plugins.installed.ai_content.marks import marks_for
    from plugins.installed.catalog.models import Product
    from plugins.registry import app_registry

    # The PDP hands storefront blocks the GraphQL product dict, not the model; the
    # marks need only its id, so the row is not loaded.
    if isinstance(product, dict):
        product = Product(pk=product['id']) if product.get('id') else None
    if not isinstance(product, Product):
        return {}
    fields = [f for f in ('description', 'short_description') if f in marks_for(product)]
    if not fields:
        return {}
    plugin = app_registry.get('ai_content')
    label = bool(plugin and plugin.get_config_value('label_ai_text', False))
    return {'fields': fields, 'label': label}
