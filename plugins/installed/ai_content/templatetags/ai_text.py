"""`{% load ai_text %}`: the page's mark of text an AI wrote (EU AI Act Art. 50)."""

from __future__ import annotations

from django import template

register = template.Library()

# The product text a product page shows, of the text the product's own marks cover.
_SHOWN = ('description', 'short_description')


@register.simple_tag(takes_context=True)
def ai_text_mark(context, product) -> dict:
    """``{'fields': [...], 'label': bool, 'translated': bool}`` for a product page.

    Empty when nothing is marked. ``fields`` lists the marked text the page shows
    that has words in it: the description and short description an AI wrote, and
    any field the page shows in a translation that began as an AI draft
    (``core.i18n.services.ai_translated``). ``label`` is the merchant's choice to
    say so in words as well; ``translated`` says only the translation is the AI's,
    so the sentence says that.
    """
    from core.i18n.services import ai_translated
    from plugins.installed.ai_content.marks import marks_for, plain_text
    from plugins.installed.catalog.models import Product
    from plugins.registry import app_registry

    # The PDP hands storefront blocks the GraphQL product dict, not the model. The
    # page's head object is the row it shows in the page's language, so translation
    # marks are read from that row; the product's own marks need its id only.
    if isinstance(product, dict):
        shown = context.get('seo_object')
        pk = str(product.get('id') or '')
        if isinstance(shown, Product) and pk and str(shown.pk) == pk:
            product = shown
        else:
            product = Product(pk=pk) if pk else None
    if not isinstance(product, Product):
        return {}
    marked = [f for f in _SHOWN if f in marks_for(product)]
    fields: list[str] = []
    if marked:
        # A mark claims the product's own text, so a marked field that is empty
        # claims nothing: the merchant cleared the text and kept the box, or a
        # booking page shows the host's own text in its place.
        text = Product.objects.filter(pk=product.pk).values(*marked).first() or {}
        fields = [f for f in marked if plain_text(text.get(f) or '')]
    shown_fields = list(dict.fromkeys([*fields, *ai_translated(product)]))
    if not shown_fields:
        return {}
    plugin = app_registry.get('ai_content')
    label = bool(plugin and plugin.get_config_value('label_ai_text', False))
    return {'fields': shown_fields, 'label': label, 'translated': not fields}


@register.simple_tag(takes_context=True)
def ai_page_mark(context) -> list[str]:
    """The fields a page about one object shows in a translation an AI drafted.

    The object is the one the page's head reads (``seo_content_object``, else
    ``seo_object``). A catalog Product is left out: its page marks it under the
    description (``ai_text_mark``).
    """
    from core.i18n.services import ai_translated

    obj = context.get('seo_content_object') or context.get('seo_object')
    meta = getattr(obj, '_meta', None)
    if meta is None or meta.label_lower == 'catalog.product':
        return []
    return ai_translated(obj)
