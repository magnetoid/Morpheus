"""Template helpers for surfacing BookProduct on the storefront.

The PDP `product` in context is the GraphQL-serialised dict (camelCase), so it
has no `book` relation — this tag resolves the BookProduct from the product's
slug/id. Fail-soft: returns None on any miss so a block never breaks the page.
"""

from __future__ import annotations

import re

from django import template

register = template.Library()

_SENTENCE_END = re.compile(r'[.!?](\s|$)')


@register.filter
def first_sentence(text) -> str:
    """First sentence of `text` — up to the first . ! or ?, trimmed. Used on the
    product card to show a one-line pitch under the title. Falls back to the
    whole (capped) string when there's no sentence break."""
    s = (str(text) or '').strip()
    if not s:
        return ''
    m = _SENTENCE_END.search(s)
    out = s[: m.start() + 1] if m else s
    return out.strip()[:180]


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
