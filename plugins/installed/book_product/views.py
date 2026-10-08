"""Storefront facet landing pages for book attributes.

Each book attribute (publisher, series, imprint, format, language) gets a
browse page listing the books that carry that value — mirroring the existing
/author/<slug>/ page, but sourced from the BookProduct model. Auto-generated
from the field values; no taxonomy tables.

Each landing answers for what is ON it: a value carried only by withdrawn books
is not a page (404), a curated term with no books in print renders but stays
out of the index (`seo_item_count`), a big shelf is paginated (a page past the
end is a 404), and every page has a description — the merchant's, the term's
own copy, or one written from the books on the shelf.
"""

from __future__ import annotations

from django.shortcuts import redirect, render
from django.utils.text import slugify

from core.utils.pagination import paginate_or_404
from morpheus.app.views import Http404

# A shelf of 860 paperbacks rendered as one 1.5 MB page; 48 is four rows of the
# themes' book grid.
_PER_PAGE = 48

# How each kind of landing introduces its shelf when nobody wrote a description.
_LEAD = {
    'Genre': '{value} books',
    'Topic': 'Books about {value}',
    'Publisher': 'Books published by {value}',
    'Imprint': 'Books from the {value} imprint',
    'Series': 'The {value} series',
    'Format': '{value} editions',
    'Language': 'Books in {value}',
}

# The singular a taxonomy index introduces itself with.
_INDEX_NOUN = {
    'Authors': 'author',
    'Publishers': 'publisher',
    'Series': 'series',
    'Imprints': 'imprint',
    'Genres': 'genre',
    'Topics': 'topic',
}


def _active_products(books):
    return [b.product for b in books if getattr(b.product, 'status', '') == 'active']


def _shelf_description(label: str, value: str, products: list, count: int) -> str:
    """A meta description written from the books themselves.

    For a term nobody described: all 1,527 topic pages on dotbooks shipped
    without a description, so Google wrote its own snippet from the page chrome.
    Everything said here is on the page — the term and its first titles.
    """
    names = [p.name for p in products[:3] if getattr(p, 'name', '')]
    if not names:
        return ''
    lead = _LEAD.get(label, '{value}').format(value=value)
    listed = names[0] if len(names) == 1 else f'{", ".join(names[:-1])} and {names[-1]}'
    more = f' — {count} titles in all' if count > len(names) else ''
    return f'{lead}: {listed}{more}.'[:300]


def _term_description(term) -> str:
    """The merchant's meta description, else the term's own editorial copy."""
    from html import unescape  # noqa: PLC0415

    from django.utils.html import strip_tags  # noqa: PLC0415

    if term is None:
        return ''
    if (getattr(term, 'meta_description', '') or '').strip():
        return term.meta_description.strip()
    text = unescape(strip_tags(getattr(term, 'description', '') or ''))
    return ' '.join(text.split())[:300]


def _jsonld_items(products):
    """[{name, url, image}] — the ItemList the SEO graph publishes for the shelf."""
    out = []
    for p in products[:60]:
        image = ''
        primary = getattr(p, 'primary_image', None)
        if primary and getattr(primary, 'image', None):
            try:
                image = primary.image.url
            except Exception:  # noqa: BLE001 — image may have no file on disk
                image = ''
        out.append({'name': p.name, 'url': f'/products/{p.slug}/', 'image': image})
    return out


def _render(request, label, value, products, *, term=None, index_url=None):
    page_obj = paginate_or_404(products, _PER_PAGE, request)
    shelf = list(page_obj.object_list)
    count = page_obj.paginator.count
    # Per-visitor merchandising: reorder by purchase propensity (no-op without
    # consent/history/personalisation). Series keeps its reading order
    # (series_position), so it opts out.
    if label != 'Series':
        from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

        shelf = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER, value=shelf, request=request, surface='facet'
        )
    seo_title = term.meta_title if (term and term.meta_title) else f'{value} — {label}'
    # Staff admin-bar deep-link: edit this curated taxonomy term in the dashboard.
    active_edit_url = ''
    if (
        term is not None
        and label in ('Genre', 'Topic')
        and request.user.is_authenticated
        and request.user.is_staff
    ):
        from django.urls import reverse  # noqa: PLC0415

        active_edit_url = reverse(
            'book_product_dashboard:curated_edit',
            kwargs={'kind': label.lower(), 'slug': term.slug},
        )
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {
            'name': label if index_url else 'All books',
            'url': request.build_absolute_uri(index_url or '/products/'),
        },
        {'name': value, 'url': request.build_absolute_uri(request.path)},
    ]
    return render(
        request,
        'storefront/book_facet.html',
        {
            'facet_label': label,
            'active_edit_url': active_edit_url,
            'active_edit_label': f'Edit {label.lower()}' if active_edit_url else '',
            'facet_value': value,
            # When this facet kind has an index page (publisher/series/imprint),
            # link the breadcrumb label up to it (e.g. "Publisher" → /publishers/).
            'facet_index_url': index_url,
            'products': shelf,
            'page_obj': page_obj,
            'jsonld_items': _jsonld_items(shelf),
            'term': term,
            'breadcrumb_items': breadcrumb_items,
            'seo_title': seo_title,
            'seo_description': (
                _term_description(term) or _shelf_description(label, value, products, count)
            ),
            # An empty curated term renders, but the SEO layer holds it out of
            # the index; the sitemap already leaves it out.
            'seo_item_count': count,
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

    Matched among books in print only: a value carried only by withdrawn books
    is not a page, the same answer as a value no book ever carried. (It used to
    answer 200 with an empty shelf.) When `taxonomy` is given, its
    BookTaxonomyTerm (if any) supplies SEO + intro.
    """
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    in_print = BookProduct.objects.filter(product__status='active')
    values = in_print.exclude(**{field: ''}).values_list(field, flat=True).distinct()
    match = next((v for v in values if v and slugify(v) == slug), None)
    if match is None:
        raise Http404
    books = (
        in_print.filter(**{f'{field}__iexact': match})
        .select_related('product')
        .order_by(order_by, '-product__created_at')
    )
    term = None
    if taxonomy:
        from plugins.installed.book_product.models import BookTaxonomyTerm  # noqa: PLC0415

        term = BookTaxonomyTerm.objects.filter(taxonomy=taxonomy, slug=slug).first()
    index_url = _ROOT_INDEX_URL.get(taxonomy) if taxonomy else None
    return _render(request, label, match, _active_products(books), term=term, index_url=index_url)


def _value_facet(request, field, value, label, display, *, stored=None):
    """Landing page for an enum-ish book field (print_type / language).

    `stored` lists every stored spelling the page covers (a language's code and
    its written-out name); by default just `value`.
    """
    from django.db.models import Q  # noqa: PLC0415

    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    match = Q()
    for spelling in stored or {value}:
        match |= Q(**{f'{field}__iexact': spelling})
    books = (
        BookProduct.objects.filter(match)
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
    """One page per language, named by its code.

    dotbooks stored 860 books as `en` and one as `English`, so there were two
    landing pages for one shelf. A written-out name now 301s to its code, and
    the code's page lists every spelling of it.
    """
    from django.utils.translation import get_language_info  # noqa: PLC0415

    from plugins.installed.book_product.facets import (  # noqa: PLC0415
        canonical_language,
        language_spellings,
    )

    code = canonical_language(value)
    if code and code != value:
        prefix = request.path[: -len(f'/language/{value}/')]
        return redirect(f'{prefix}/language/{code}/', permanent=True)
    try:
        display = get_language_info(code)['name']
    except KeyError:
        display = value
    return _value_facet(
        request, 'language', code, 'Language', display, stored=language_spellings(code)
    )


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


def _index_description(root, label: str) -> str:
    """The merchant's index copy, else a plain line that names no store.

    The fallback read "Browse books by publishers at dot books." on every store
    that runs the book vertical.
    """
    if root is not None and (root.meta_description or '').strip():
        return root.meta_description.strip()
    return f'Browse books by {_INDEX_NOUN.get(label, label.lower())}.'


def _in_print_counts(key: str) -> dict[str, int]:
    """`{slug: books in print}` for a free-text field — one query, not one per value."""
    from django.db.models import Count  # noqa: PLC0415

    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    counts: dict[str, int] = {}
    rows = (
        BookProduct.objects.filter(product__status='active')
        .exclude(**{key: ''})
        .values(key)
        .annotate(n=Count('pk'))
    )
    for row in rows:
        slug = slugify(row[key] or '')
        if slug:
            counts[slug] = counts.get(slug, 0) + row['n']
    return counts


def _taxonomy_root(request, *, key, label):
    """An index of every value with at least one book in print.

    It listed values carried only by withdrawn books (each a link to an empty
    page) and counted books of every status.
    """
    from plugins.installed.book_product.compat import (  # noqa: PLC0415
        distinct_active_values,
        product_ids_for,
    )
    from plugins.installed.book_product.models import (  # noqa: PLC0415
        BookTaxonomyRoot,
        BookTaxonomyTerm,
    )
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    root = BookTaxonomyRoot.objects.filter(taxonomy=key).first()
    overrides = {t.slug: t for t in BookTaxonomyTerm.objects.filter(taxonomy=key)}
    prefix = _ROOT_DETAIL_PREFIX.get(key, '/')
    counted = _in_print_counts(key)
    terms = []
    seen: set[str] = set()
    for name in distinct_active_values(key):
        slug = slugify(name)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        count = counted.get(slug)
        if count is None:  # a legacy book.* metafield value — count it the slow way
            count = Product.objects.filter(
                id__in=product_ids_for(key, name), status='active'
            ).count()
        if not count:
            continue
        term = overrides.get(slug)
        terms.append(
            {
                'name': term.name if (term and term.name) else name,
                'slug': slug,
                'count': count,
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
            # Auto structured data: the index page is a CollectionPage listing
            # every term (author/publisher/…) as an ItemList.
            'jsonld_items': [
                {
                    'name': t['name'],
                    'url': t['url'],
                    'image': t['image'].url if t['image'] else '',
                }
                for t in terms
            ],
            'seo_title': root.meta_title if (root and root.meta_title) else f'{label}',
            'seo_description': _index_description(root, label),
            'seo_item_count': len(terms),
        },
    )


# --- Genre / Topic (curated multi-value taxonomies) ------------------------
# Unlike author/publisher/… (auto-discovered string fields), Genre and Topic are
# real M2M models — so they get their own listing + detail pages, reusing the
# same templates. Each TERM carries its own SEO on the model row; the INDEX page
# intro lives in BookTaxonomyRoot, same as /authors/ (keyed by BookRootTaxonomy,
# which is why genre/topic are members there but not in BookTaxonomy).


def _curated_root(request, *, model, key, label, detail_prefix):
    from django.db.models import Count, Q  # noqa: PLC0415

    from plugins.installed.book_product.models import BookTaxonomyRoot  # noqa: PLC0415

    # One annotated query, most-stocked first — not 1500 per-term COUNT()s.
    # Empty terms are excluded (their detail pages would be bare).
    rows = (
        model.objects.filter(is_active=True)
        .annotate(_n=Count('books', filter=Q(books__product__status='active')))
        .filter(_n__gt=0)
        .order_by('-_n', 'name')
    )
    terms = [
        {
            'name': obj.name,
            'slug': obj.slug,
            'count': obj._n,
            'url': f'{detail_prefix}{obj.slug}/',
            'image': obj.image or None,
        }
        for obj in rows
    ]
    root = BookTaxonomyRoot.objects.filter(taxonomy=key).first()
    return render(
        request,
        'storefront/taxonomy_root.html',
        {
            'root_label': label,
            'root': root,
            'terms': terms,
            'jsonld_items': [
                {'name': t['name'], 'url': t['url'], 'image': t['image'].url if t['image'] else ''}
                for t in terms
            ],
            'seo_title': root.meta_title if (root and root.meta_title) else f'{label}',
            'seo_description': _index_description(root, label),
            'seo_item_count': len(terms),
        },
    )


def _curated_detail(request, *, model, slug, label, index_url):
    obj = model.objects.filter(slug=slug, is_active=True).first()
    if obj is None:
        raise Http404
    books = (
        obj.books.select_related('product')
        .filter(product__status='active')
        .order_by('-product__is_featured', '-product__created_at')
    )
    return _render(request, label, obj.name, _active_products(books), term=obj, index_url=index_url)


def genres_root(request):
    from plugins.installed.book_product.models import Genre  # noqa: PLC0415

    return _curated_root(request, model=Genre, key='genre', label='Genres', detail_prefix='/genre/')


def topics_root(request):
    from plugins.installed.book_product.models import Topic  # noqa: PLC0415

    return _curated_root(request, model=Topic, key='topic', label='Topics', detail_prefix='/topic/')


def genre_detail(request, slug):
    from plugins.installed.book_product.models import Genre  # noqa: PLC0415

    return _curated_detail(request, model=Genre, slug=slug, label='Genre', index_url='/genres/')


def topic_detail(request, slug):
    from plugins.installed.book_product.models import Topic  # noqa: PLC0415

    return _curated_detail(request, model=Topic, slug=slug, label='Topic', index_url='/topics/')


def authors_root(request):
    return _taxonomy_root(request, key='author', label='Authors')


def publishers_root(request):
    return _taxonomy_root(request, key='publisher', label='Publishers')


def series_root(request):
    return _taxonomy_root(request, key='series', label='Series')


def imprints_root(request):
    return _taxonomy_root(request, key='imprint', label='Imprints')
