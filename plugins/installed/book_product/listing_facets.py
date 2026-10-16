"""The book filters on the all-books page: genre, topic, author, format, length.

Answers `LISTING_FACETS` for the storefront's product list (spec
docs/superpowers/specs/2026-10-16-dotbooks-book-filters-design.md). Values
inside one facet widen (OR); facets narrow each other (AND). Each facet's
counts are taken with every OTHER facet applied, so a count says how many books
that choice would leave.
"""

from __future__ import annotations

from django.db.models import Count, F, Q, Value
from django.db.models.functions import NullIf

FACET_KEYS = ('genre', 'topic', 'author', 'format', 'length')
FORMATS = (('print', 'Print'), ('digital', 'Digital PDF'), ('audiobook', 'Audiobook'))
# (value, label, lowest page count included, first page count excluded)
LENGTHS = (
    ('under-150', 'Under 150 pages', None, 150),
    ('150-300', '150–300 pages', 150, 300),
    ('300-500', '300–500 pages', 300, 500),
    ('500-plus', '500+ pages', 500, None),
)
TOPIC_MIN_BOOKS = 2
GENRE_SEARCH_ABOVE = 12
SORTS = (
    # A book without an author sorts last, not first ('' sorts before 'A').
    ('author', 'Author A–Z', (NullIf(F('book__author'), Value('')).asc(nulls_last=True), 'name')),
    ('shortest', 'Shortest', (F('book__page_count').asc(nulls_last=True), 'name')),
    ('longest', 'Longest', (F('book__page_count').desc(nulls_last=True), 'name')),
)


def selections(params) -> dict[str, list[str]]:
    """Each facet's chosen values from repeated query keys; blanks and repeats dropped."""
    chosen: dict[str, list[str]] = {}
    for key in FACET_KEYS:
        values: list[str] = []
        for raw in params.getlist(key) if params is not None else []:
            value = (raw or '').strip()
            if value and value not in values:
                values.append(value)
        chosen[key] = values
    return chosen


def _variant_products(**kw):
    from plugins.installed.catalog.models import ProductVariant

    return ProductVariant.objects.filter(is_active=True, **kw)


def _format_q(value: str) -> Q | None:
    audio = Q(variant_type='audiobook') | Q(name__icontains='audio')
    if value == 'audiobook':
        return Q(pk__in=_variant_products().filter(audio).values('product_id'))
    if value == 'digital':
        return Q(
            pk__in=_variant_products(variant_type='digital')
            .exclude(name__icontains='audio')
            .values('product_id')
        )
    if value == 'print':
        return Q(pk__in=_variant_products(variant_type='physical').values('product_id')) | Q(
            variants__isnull=True
        )
    return None


def _length_q(value: str) -> Q | None:
    row = next((r for r in LENGTHS if r[0] == value), None)
    if row is None:
        return None
    _value, _label, low, high = row
    cond = Q(book__page_count__isnull=False)
    if low is not None:
        cond &= Q(book__page_count__gte=low)
    if high is not None:
        cond &= Q(book__page_count__lt=high)
    return cond


def _facet_q(key: str, values: list[str]) -> Q | None:
    """The OR of a facet's values, or None when no value means anything."""
    if key == 'genre':
        return Q(book__genres__slug__in=values)
    if key == 'topic':
        return Q(book__topics__slug__in=values)
    if key == 'author':
        q = Q()
        for v in values:
            q |= Q(book__author__iexact=v)
        return q
    builder = _format_q if key == 'format' else _length_q
    parts = [p for p in (builder(v) for v in values) if p is not None]
    if not parts:
        return None
    q = parts[0]
    for p in parts[1:]:
        q |= p
    return q


def apply(qs, chosen: dict, *, skip: str | None = None):
    """Narrow `qs` by every chosen facet except `skip`."""
    for key in FACET_KEYS:
        values = chosen.get(key) or []
        if key == skip or not values:
            continue
        q = _facet_q(key, values)
        if q is not None:
            qs = qs.filter(q)
    return qs.distinct()


def _scope(base_qs, chosen, key):
    from plugins.installed.catalog.models import Product

    ids = apply(base_qs, chosen, skip=key).order_by().values('pk')
    return Product.objects.filter(pk__in=ids)


def _options(rows, selected: list[str], *, fold=False):
    """rows: [(value, label, count)] → option dicts; zero counts dropped unless selected;
    a selected value with no row is added with count 0."""
    picked = {s.lower() for s in selected} if fold else set(selected)
    out, seen = [], set()
    for value, label, count in rows:
        is_sel = (value.lower() if fold else value) in picked
        if count or is_sel:
            out.append({'value': value, 'label': label, 'count': count, 'selected': is_sel})
            seen.add(value.lower() if fold else value)
    for s in selected:
        if (s.lower() if fold else s) not in seen:
            out.append({'value': s, 'label': s, 'count': 0, 'selected': True})
    return out


def _taxonomy_rows(model, scope, *, min_books=1):
    rows = (
        model.objects.filter(is_active=True, books__product__in=scope)
        .annotate(n=Count('books', distinct=True))
        .filter(n__gte=min_books)
        .order_by('-n', 'name')
    )
    return [(t.slug, t.name, t.n) for t in rows]


def _facet(key, label, options, *, searchable=False):
    return {
        'key': key,
        'label': label,
        'searchable': searchable,
        'selected_count': sum(1 for o in options if o['selected']),
        'options': options,
    }


def describe(base_qs, chosen: dict) -> list[dict]:
    """Every facet with its options and counts; a facet with no options is left out."""
    from plugins.installed.book_product.models import BookProduct, Genre, Topic

    facets = []

    def labelled(model, values):
        names = dict(model.objects.filter(slug__in=values).values_list('slug', 'name'))
        return names

    genre_opts = _options(_taxonomy_rows(Genre, _scope(base_qs, chosen, 'genre')), chosen['genre'])
    names = labelled(Genre, [o['value'] for o in genre_opts if o['count'] == 0])
    for o in genre_opts:
        o['label'] = names.get(o['value'], o['label'])
    facets.append(
        _facet('genre', 'Genre', genre_opts, searchable=len(genre_opts) > GENRE_SEARCH_ABOVE)
    )

    topic_opts = _options(
        _taxonomy_rows(Topic, _scope(base_qs, chosen, 'topic'), min_books=TOPIC_MIN_BOOKS),
        chosen['topic'],
    )
    names = labelled(Topic, [o['value'] for o in topic_opts if o['count'] == 0])
    for o in topic_opts:
        o['label'] = names.get(o['value'], o['label'])
    facets.append(_facet('topic', 'Topic', topic_opts, searchable=True))

    authors = (
        BookProduct.objects.filter(product__in=_scope(base_qs, chosen, 'author'))
        .exclude(author='')
        .values('author')
        .annotate(n=Count('product', distinct=True))
        .order_by('author')
    )
    author_opts = _options(
        [(r['author'], r['author'], r['n']) for r in authors], chosen['author'], fold=True
    )
    facets.append(_facet('author', 'Author', author_opts, searchable=True))

    scope = _scope(base_qs, chosen, 'format')
    fmt_rows = [(v, label, scope.filter(_format_q(v)).distinct().count()) for v, label in FORMATS]
    facets.append(_facet('format', 'Format', _options(fmt_rows, chosen['format'])))

    scope = _scope(base_qs, chosen, 'length')
    len_rows = [(v, label, scope.filter(_length_q(v)).count()) for v, label, _lo, _hi in LENGTHS]
    facets.append(_facet('length', 'Length', _options(len_rows, chosen['length'])))

    return [f for f in facets if f['options']]


def answer(value: dict, params) -> dict:
    """LISTING_FACETS: narrow the listing by the book facets and describe them."""
    if not isinstance(value, dict) or value.get('queryset') is None or params is None:
        return value
    chosen = selections(params)
    base = value['queryset']
    # Cards on the page read the book, its genres and formats (cards.py): fetch
    # them with the listing, not once per card.
    value['queryset'] = (
        apply(base, chosen).select_related('book').prefetch_related('book__genres', 'variants')
    )
    value['facets'] = list(value.get('facets') or []) + describe(base, chosen)
    value['sorts'] = list(value.get('sorts') or []) + list(SORTS)
    value['chosen'] = {**(value.get('chosen') or {}), **{k: v for k, v in chosen.items() if v}}
    return value
