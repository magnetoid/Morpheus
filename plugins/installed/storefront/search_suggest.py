"""What the search dropdown suggests while a shopper types (/api/quick-search/).

A suggestion is what was typed: every word starts a word of the name. The
semantic ranker that orders the full results page finds a neighbour for any
query, so the dropdown suggested the same six unrelated books for "dune" and
for "orwell"; it stays on that page, which Enter opens.

Above the products come the landing pages whose names match: the shop's own
categories and collections, and whatever other apps contribute through
`SEARCH_SUGGESTIONS` (book_product: genres, authors). Each one has products on
it, so a suggestion never leads to an empty page.
"""

from __future__ import annotations

import re

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils.translation import gettext, ngettext

PRODUCT_LIMIT = 6
PAGE_LIMIT = 4
# A word this short in a product's text is as often part of its HTML ("<span")
# as of its words, so the text tier waits for longer words.
TEXT_MIN_WORD = 4


def words(q: str) -> list[str]:
    """The query's words, lowercased; five at most."""
    return q.lower().split()[:5]


def starts_words(field: str, terms: list[str]) -> Q:
    """Every term starts a word of `field` (case-insensitive, sqlite and Postgres)."""
    q = Q()
    for term in terms:
        q &= Q(**{f'{field}__iregex': r'(^|[^a-z0-9])' + re.escape(term)})
    return q


def products(q: str, terms: list[str]) -> list:
    """Up to PRODUCT_LIMIT shoppable products, best first.

    A name that starts with the query comes first, then other names holding
    every word, then products whose text, author or SKU does.
    """
    from plugins.installed.catalog.models import Product
    from plugins.installed.catalog.search import get_backend, search
    from plugins.installed.storefront.views.catalog import _metafield_search_ids

    base = Product.objects.shoppable().prefetch_related('images')
    if get_backend() == 'typesense':
        # Typesense matches as typed, with typo tolerance: its order is the answer.
        try:
            ids = list(search(q, per_page=PRODUCT_LIMIT).product_ids)
        except Exception:  # noqa: BLE001 — fall back to the database
            ids = []
        if ids:
            by_id = {p.pk: p for p in base.filter(pk__in=ids)}
            return [by_id[i] for i in ids if i in by_id]

    rows = list(
        base.filter(starts_words('name', terms))
        .annotate(
            _rank=Case(
                When(name__istartswith=q, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by('_rank', '-is_featured', 'name')[:PRODUCT_LIMIT]
    )
    if len(rows) < PRODUCT_LIMIT:
        more = Q(sku__iexact=q) | Q(id__in=_metafield_search_ids(q))
        if min(len(t) for t in terms) >= TEXT_MIN_WORD:
            more |= starts_words('short_description', terms) | starts_words('description', terms)
        rows += list(
            base.filter(more)
            .exclude(pk__in=[p.pk for p in rows])
            .order_by('-is_featured', 'name')[: PRODUCT_LIMIT - len(rows)]
        )
    return rows


def _count_label(n: int) -> str:
    return ngettext('%(n)d product', '%(n)d products', n) % {'n': n}


def _starts_first(rows, terms: list[str]) -> list:
    """Names that start with the first word ahead of the rest, then by name."""
    return sorted(rows, key=lambda r: (not r.name.lower().startswith(terms[0]), r.name.lower()))


def catalog_groups(terms: list[str]) -> list[dict]:
    """The shop's categories and collections whose names match and hold products."""
    from plugins.installed.catalog.category_tree import in_categories
    from plugins.installed.catalog.models import Category, Collection, Product

    shoppable = Product.objects.shoppable()
    groups = []
    items = []
    for c in _starts_first(
        Category.objects.filter(starts_words('name', terms), is_active=True)[:12], terms
    ):
        n = shoppable.filter(in_categories([c])).distinct().count()
        if n:
            items.append({'name': c.name, 'url': f'/category/{c.slug}/', 'meta': _count_label(n)})
        if len(items) == PAGE_LIMIT:
            break
    if items:
        groups.append({'key': 'categories', 'label': gettext('Categories'), 'items': items})
    items = []
    for c in _starts_first(
        Collection.objects.filter(starts_words('name', terms), is_active=True)[:6], terms
    ):
        n = shoppable.filter(collections=c).count()
        if n:
            items.append({'name': c.name, 'url': f'/collection/{c.slug}/', 'meta': _count_label(n)})
        if len(items) == 2:
            break
    if items:
        groups.append({'key': 'collections', 'label': gettext('Collections'), 'items': items})
    return groups
