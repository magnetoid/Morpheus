"""`{% load ai_text %}`: the product page's mark of AI-written text."""

from __future__ import annotations

from django import template

register = template.Library()

# The product text a product page shows.
_SHOWN = ('description', 'short_description')


@register.simple_tag
def ai_text_mark(product) -> dict:
    """``{'fields': [...], 'label': bool}`` for a product page, empty when unmarked.

    ``fields`` lists the marked text the page shows (description, short
    description) that has words in it; ``label`` is the merchant's choice to say
    so in words as well.
    """
    from plugins.installed.ai_content.marks import marks_for, plain_text
    from plugins.installed.catalog.models import Product
    from plugins.registry import app_registry

    # The PDP hands storefront blocks the GraphQL product dict, not the model; the
    # marks need only its id, so no row is loaded for an unmarked product.
    if isinstance(product, dict):
        product = Product(pk=product['id']) if product.get('id') else None
    if not isinstance(product, Product):
        return {}
    marked = [f for f in _SHOWN if f in marks_for(product)]
    if not marked:
        return {}
    # A mark claims the product's own text, so a marked field that is empty claims
    # nothing: the merchant cleared the text and kept the box, or a booking page
    # shows the host's own text in its place.
    text = Product.objects.filter(pk=product.pk).values(*marked).first() or {}
    fields = [f for f in marked if plain_text(text.get(f) or '')]
    if not fields:
        return {}
    plugin = app_registry.get('ai_content')
    label = bool(plugin and plugin.get_config_value('label_ai_text', False))
    return {'fields': fields, 'label': label}
