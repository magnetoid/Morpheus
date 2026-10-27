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
# Long lists (dotbooks: 340 topics, 291 authors, a third of the page's HTML). The page
# carries a lazy panel's chosen options; the panel fetches the rest when it opens, from
# the same listing with PANEL_PARAM naming it (the storefront view answers that).
LAZY_FACETS = ('topic', 'author')
PANEL_PARAM = 'facet_panel'
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


def _genre(base_qs, chosen):
    from plugins.installed.book_product.models import Genre

    opts = _options(_taxonomy_rows(Genre, _scope(base_qs, chosen, 'genre')), chosen['genre'])
    names = _labels(Genre, [o['value'] for o in opts if o['count'] == 0])
    for o in opts:
        o['label'] = names.get(o['value'], o['label'])
    return _facet('genre', 'Genre', opts, searchable=len(opts) > GENRE_SEARCH_ABOVE)


def _topic(base_qs, chosen):
    from plugins.installed.book_product.models import Topic

    opts = _options(
        _taxonomy_rows(Topic, _scope(base_qs, chosen, 'topic'), min_books=TOPIC_MIN_BOOKS),
        chosen['topic'],
    )
    names = _labels(Topic, [o['value'] for o in opts if o['count'] == 0])
    for o in opts:
        o['label'] = names.get(o['value'], o['label'])
    return _facet('topic', 'Topic', opts, searchable=True)


def _author(base_qs, chosen):
    from plugins.installed.book_product.models import BookProduct

    authors = (
        BookProduct.objects.filter(product__in=_scope(base_qs, chosen, 'author'))
        .exclude(author='')
        .values('author')
        .annotate(n=Count('product', distinct=True))
        .order_by('author')
    )
    opts = _options(
        [(r['author'], r['author'], r['n']) for r in authors], chosen['author'], fold=True
    )
    return _facet('author', 'Author', opts, searchable=True)


def _format(base_qs, chosen):
    scope = _scope(base_qs, chosen, 'format')
    rows = [(v, label, scope.filter(_format_q(v)).distinct().count()) for v, label in FORMATS]
    return _facet('format', 'Format', _options(rows, chosen['format']))


def _length(base_qs, chosen):
    scope = _scope(base_qs, chosen, 'length')
    rows = [(v, label, scope.filter(_length_q(v)).count()) for v, label, _lo, _hi in LENGTHS]
    return _facet('length', 'Length', _options(rows, chosen['length']))


_BUILDERS = {
    'genre': _genre,
    'topic': _topic,
    'author': _author,
    'format': _format,
    'length': _length,
}


def _labels(model, values):
    return dict(model.objects.filter(slug__in=values).values_list('slug', 'name'))


def _lazy(key, base_qs, chosen):
    """A long facet's panel before it opens: its chosen options (labelled, without counts)
    and where the whole list lives; None when nothing in scope would fill it."""
    from django.urls import NoReverseMatch, reverse

    from plugins.installed.book_product.models import BookProduct, Topic

    values = chosen[key]
    scope = _scope(base_qs, chosen, key)
    if key == 'topic':
        names = _labels(Topic, values)
        options = [(v, names.get(v, v)) for v in values]
        fills = (
            Topic.objects.filter(is_active=True, books__product__in=scope)
            .annotate(n=Count('books', distinct=True))
            .filter(n__gte=TOPIC_MIN_BOOKS)
            .exists()
        )
        label, more, more_label = 'Topic', 'book_product:topics', 'All topics'
    else:
        stored = BookProduct.objects.exclude(author='')
        options = []
        for v in values:
            name = stored.filter(author__iexact=v).values_list('author', flat=True).first() or v
            options.append((name, name))
        fills = stored.filter(product__in=scope).exists()
        label, more, more_label = 'Author', 'book_product:authors', 'All authors'
    if not options and not fills:
        return None
    facet = _facet(
        key,
        label,
        [{'value': v, 'label': n, 'count': None, 'selected': True} for v, n in options],
        searchable=True,
    )
    try:
        more_url = reverse(more)
    except NoReverseMatch:
        more_url = ''
    return {**facet, 'lazy': True, 'more_url': more_url, 'more_label': more_label}


def describe(base_qs, chosen: dict, *, keys=FACET_KEYS, lazy=()) -> list[dict]:
    """Each facet in `keys` with its options and counts; a facet in `lazy` carries only its
    chosen options. A facet with no options is left out, a lazy one only when nothing in
    scope would fill it."""
    facets = []
    for key in keys:
        facet = _lazy(key, base_qs, chosen) if key in lazy else _BUILDERS[key](base_qs, chosen)
        if facet and (facet['options'] or facet.get('lazy')):
            facets.append(facet)
    return facets


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
    # An opened panel asks for its whole list; the page itself defers the long ones.
    panel = (params.get(PANEL_PARAM) or '').strip()
    if panel:
        described = describe(base, chosen, keys=(panel,)) if panel in FACET_KEYS else []
    else:
        described = describe(base, chosen, lazy=LAZY_FACETS)
    value['facets'] = list(value.get('facets') or []) + described
    value['sorts'] = list(value.get('sorts') or []) + list(SORTS)
    value['chosen'] = {**(value.get('chosen') or {}), **{k: v for k, v in chosen.items() if v}}
    return value
