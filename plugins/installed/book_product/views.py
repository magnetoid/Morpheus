"""Storefront facet landing pages for book attributes.

Each book attribute (publisher, series, imprint, format, language) gets a
browse page listing the books that carry that value — mirroring the existing
/author/<slug>/ page, but sourced from the BookProduct model. Auto-generated
from the field values; no taxonomy tables.
"""

from __future__ import annotations

from django.shortcuts import render
from django.utils.text import slugify

from morpheus.views import Http404


def _active_products(books):
    return [b.product for b in books if getattr(b.product, 'status', '') == 'active']


def _render(request, label, value, products, *, term=None):
    seo_title = term.meta_title if (term and term.meta_title) else f'{value} — {label} — dot books'
    return render(
        request,
        'storefront/book_facet.html',
        {
            'facet_label': label,
            'facet_value': value,
            'products': products,
            'term': term,
            'seo_title': seo_title,
            'seo_description': term.meta_description if term else '',
            'active_nav': '',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/'},
                {'label': label},
                {'label': value},
            ],
        },
    )


def _slug_facet(request, field, slug, label, *, taxonomy=None, order_by='-product__is_featured'):
    """Landing page for a free-text book field matched by slugify(value).
    When `taxonomy` is given, its BookTaxonomyTerm (if any) supplies SEO + intro."""
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    values = BookProduct.objects.exclude(**{field: ''}).values_list(field, flat=True).distinct()
    match = next((v for v in values if v and slugify(v) == slug), None)
    if match is None:
        raise Http404
    books = (
        BookProduct.objects.filter(**{f'{field}__iexact': match})
        .select_related('product')
        .order_by(order_by, '-product__created_at')
    )
    term = None
    if taxonomy:
        from plugins.installed.book_product.models import BookTaxonomyTerm  # noqa: PLC0415

        term = BookTaxonomyTerm.objects.filter(taxonomy=taxonomy, slug=slug).first()
    return _render(request, label, match, _active_products(books), term=term)


def _value_facet(request, field, value, label, display):
    """Landing page for an enum-ish book field (print_type / language)."""
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    books = (
        BookProduct.objects.filter(**{field: value})
        .select_related('product')
        .order_by('-product__is_featured', '-product__created_at')
    )
    products = _active_products(books)
    if not products:
        raise Http404
    return _render(request, label, display, products)


def publisher_detail(request, slug):
    return _slug_facet(request, 'publisher', slug, 'Publisher', taxonomy='publisher')


def imprint_detail(request, slug):
    return _slug_facet(request, 'imprint', slug, 'Imprint', taxonomy='imprint')


def series_detail(request, slug):
    # Series reads best in reading order.
    return _slug_facet(
        request, 'series', slug, 'Series', taxonomy='series', order_by='series_position'
    )


def format_detail(request, value):
    from plugins.installed.book_product.models import PrintType  # noqa: PLC0415

    return _value_facet(
        request, 'print_type', value, 'Format', dict(PrintType.choices).get(value, value)
    )


def language_detail(request, value):
    return _value_facet(request, 'language', value, 'Language', value)
