"""Template helpers for surfacing BookProduct on the storefront.

The PDP `product` in context is the GraphQL-serialised dict (camelCase), so it
has no `book` relation — this tag resolves the BookProduct from the product's
slug/id. Fail-soft: returns None on any miss so a block never breaks the page.
"""

from __future__ import annotations

from django import template

# first_sentence moved to core (core/templatetags/morph.py): the shared
# storefront card in every theme uses it, and a store can disable the book
# vertical, so it must not live in a book-plugin lib. Re-registered here so any
# template still doing `{% load book_extras %}{{ x|first_sentence }}` keeps
# working while book_product is active — one implementation, no drift.
from core.templatetags.morph import first_sentence

register = template.Library()
register.filter('first_sentence', first_sentence)


def _attr(product, name):
    if product is None:
        return None
    if isinstance(product, dict):
        return product.get(name)
    return getattr(product, name, None)


@register.filter
def language_name(code):
    """Human-readable local name for a language code ('fr' → 'français');
    falls back to the code itself. Used by the PDP language switcher."""
    code = (str(code or '')).strip().lower()
    if not code:
        return ''
    try:
        from django.utils.translation import get_language_info  # noqa: PLC0415

        return get_language_info(code)['name_local']
    except Exception:  # noqa: BLE001 — unknown code: show it as-is
        return code


@register.simple_tag
def book_language_editions(product):
    """All language editions of this product's work (original first), each as
    ``{language, name, slug, current}``. Empty list when the product isn't a
    book or has no linked editions — the PDP switcher self-gates on this."""
    book = book_for_product(product)
    if book is None:
        return []
    try:
        editions = book.language_editions()
    except Exception:  # noqa: BLE001 — never break a PDP render
        return []
    if len(editions) < 2:
        return []
    return [
        {
            'language': e.language or 'en',
            'name': e.product.name,
            'slug': e.product.slug,
            'current': e.pk == book.pk,
        }
        for e in editions
    ]


@register.simple_tag
def book_term_lede(taxonomy, name):
    """Return the stored description for a taxonomy term (author/publisher/…)
    matched by display name, or ''. Lets the filtered PLP show the same
    dashboard-editable copy as the term's own landing page. Fail-soft."""
    if not name:
        return ''
    try:
        from plugins.installed.book_product.models import BookTaxonomyTerm  # noqa: PLC0415

        term = (
            BookTaxonomyTerm.objects.filter(taxonomy=taxonomy, name=name)
            .exclude(description='')
            .only('description')
            .first()
        )
        return term.description if term else ''
    except Exception:  # noqa: BLE001 — never break a storefront render
        return ''


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
