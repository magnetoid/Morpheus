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


def _render(request, label, value, products, *, term=None, index_url=None):
    # Per-visitor merchandising: reorder by purchase propensity (no-op without
    # consent/history/personalisation). Series keeps its reading order
    # (series_position), so it opts out.
    if label != 'Series':
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        products = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER, value=products, request=request, surface='facet'
        )
    seo_title = term.meta_title if (term and term.meta_title) else f'{value} — {label} — dot books'
    return render(
        request,
        'storefront/book_facet.html',
        {
            'facet_label': label,
            'facet_value': value,
            # When this facet kind has an index page (publisher/series/imprint),
            # link the breadcrumb label up to it (e.g. "Publisher" → /publishers/).
            'facet_index_url': index_url,
            'products': products,
            'term': term,
            'seo_title': seo_title,
            'seo_description': term.meta_description if term else '',
            'active_nav': '',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/'},
                {'label': label, 'url': index_url} if index_url else {'label': label},
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
    index_url = _ROOT_INDEX_URL.get(taxonomy) if taxonomy else None
    return _render(request, label, match, _active_products(books), term=term, index_url=index_url)


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


# --- Taxonomy root listing pages -------------------------------------------
# /authors/, /publishers/, /series/, /imprints/ — one index page per taxonomy
# kind, listing every term with its book count and a link to the term's detail
# page. The editable intro / SEO / hero image comes from a BookTaxonomyRoot row
# (one per kind); per-term name/image overrides come from BookTaxonomyTerm.

# Term-detail URL prefix per kind. Author details live in the storefront app
# (/author/<slug>/); the rest are this plugin's own facet pages.
_ROOT_DETAIL_PREFIX = {
    'author': '/author/',
    'publisher': '/publisher/',
    'series': '/series/',
    'imprint': '/imprint/',
}
# The index/listing page for each kind (links a term detail back up to its index).
_ROOT_INDEX_URL = {
    'author': '/authors/',
    'publisher': '/publishers/',
    'series': '/series/',
    'imprint': '/imprints/',
}


def _taxonomy_root(request, *, key, label):
    from plugins.installed.book_product.compat import (  # noqa: PLC0415
        distinct_values,
        product_ids_for,
    )
    from plugins.installed.book_product.models import (  # noqa: PLC0415
        BookTaxonomyRoot,
        BookTaxonomyTerm,
    )

    root = BookTaxonomyRoot.objects.filter(taxonomy=key).first()
    overrides = {t.slug: t for t in BookTaxonomyTerm.objects.filter(taxonomy=key)}
    prefix = _ROOT_DETAIL_PREFIX.get(key, '/')
    terms = []
    for name in distinct_values(key):
        slug = slugify(name)
        term = overrides.get(slug)
        terms.append(
            {
                'name': term.name if (term and term.name) else name,
                'slug': slug,
                'count': len(product_ids_for(key, name)),
                'url': f'{prefix}{slug}/',
                'image': term.image if (term and term.image) else None,
            }
        )
    terms.sort(key=lambda t: t['name'].lower())
    return render(
        request,
        'storefront/taxonomy_root.html',
        {
            'root_label': label,
            'root': root,
            'terms': terms,
            'seo_title': root.meta_title if (root and root.meta_title) else f'{label} — dot books',
            'seo_description': (root.meta_description if root else '')
            or f'Browse books by {label.lower()} at dot books.',
        },
    )


def authors_root(request):
    return _taxonomy_root(request, key='author', label='Authors')


def publishers_root(request):
    return _taxonomy_root(request, key='publisher', label='Publishers')


def series_root(request):
    return _taxonomy_root(request, key='series', label='Series')


def imprints_root(request):
    return _taxonomy_root(request, key='imprint', label='Imprints')
